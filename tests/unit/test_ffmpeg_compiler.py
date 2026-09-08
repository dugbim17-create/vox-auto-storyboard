"""Tests for P6-T04 FFmpeg motion compiler.

Covers the acceptance criteria:

- command uses an argument list (``subprocess.run(cmd)``, no ``shell=True``);
- no ``shell=True`` anywhere in the module;
- correct Windows path escaping (spaces/backslashes pass through raw);
- filter graph test (each channel produces a compileable graph);
- a real FFmpeg run succeeds when the binary is available (skipped otherwise).
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from app.services.ffmpeg_compiler import (
    CompiledMotion,
    CompileOptions,
    MotionCompiler,
    MotionCompilerError,
    compile_plan,
)
from app.services.motion_templates import build_template
from app.services.text_layout import TextLayoutService


def plan(name="01_subject_slide_headline_pop", duration=1000, size=(640, 360), seed=1) -> dict:
    raw = build_template(name, "scene_001", duration, seed=seed, canvas_size=size)
    raw["text_animations"] = [{"text": "AUTHORED", "start_ms": 100, "end_ms": min(duration, 900)}]
    return raw


def assets(plan: dict) -> dict:
    return {layer["asset_role"]: rf"C:\projects\scene\{layer['asset_role']}.png" for layer in plan["layers"]}


# --------------------------------------------------------------------------- #
# AC: command is an argument list, no shell=True
# --------------------------------------------------------------------------- #
def test_command_is_argument_list() -> None:
    compiled = MotionCompiler(ffmpeg_bin="ffmpeg.exe").compile(
        plan(), assets=assets(plan()), output_path=r"out\scene.mp4"
    )
    assert isinstance(compiled.command, list)
    assert all(isinstance(arg, str) for arg in compiled.command)
    # starts with the binary
    assert compiled.command[0] == "ffmpeg.exe"
    assert "-filter_complex" in compiled.command


def test_no_shell_true_in_module() -> None:
    import inspect

    import app.services.ffmpeg_compiler as mod

    src = inspect.getsource(mod)
    # Strip comments and docstring lines, then require no real shell= usage.
    code_lines = [
        ln for ln in src.splitlines()
        if not ln.strip().startswith(("#", '"""', "- "))
    ]
    code = "\n".join(code_lines)
    assert "shell=True" not in code
    assert "shell = True" not in code
    assert "shell=" not in code


def test_compiled_motion_fields() -> None:
    p = plan(duration=2000)
    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="out.mp4")
    assert isinstance(compiled, CompiledMotion)
    assert compiled.scene_id == "scene_001"
    assert compiled.frame_count == 60  # 2000ms @ 30fps
    assert compiled.duration_ms == 2000
    assert compiled.filter_graph


# --------------------------------------------------------------------------- #
# AC: Windows path escaping
# --------------------------------------------------------------------------- #
def test_windows_paths_passed_raw() -> None:
    p = plan()
    win_assets = {
        "background": r"C:\Project Dir\layers\scene_001_background.png",
        "subject": r"C:\Project Dir\layers\scene_001_subject.png",
        "foreground": r"C:\Project Dir\layers\scene_001_foreground.png",
        "texture": r"C:\Project Dir\layers\scene_001_texture.png",
    }
    compiled = MotionCompiler().compile(p, assets=win_assets, output_path=r"C:\out dir\scene.mp4")
    # Every input path appears as a single argv element (no shell quoting).
    assert r"C:\Project Dir\layers\scene_001_background.png" in compiled.command
    assert r"C:\out dir\scene.mp4" in compiled.command
    # Spaces are preserved verbatim, not split.
    assert compiled.command[-1] == r"C:\out dir\scene.mp4"


# --------------------------------------------------------------------------- #
# AC: filter graph test
# --------------------------------------------------------------------------- #
def test_filter_graph_contains_expected_channels() -> None:
    p = plan("05_stat_number_count")
    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")
    g = compiled.filter_graph
    assert "scale=" in g  # scale channel
    assert "overlay=" in g  # overlay channel
    assert "drawtext=" in g  # text channel
    assert "null[final]" in g or "fade=" in g  # terminates into [final]


def test_filter_graph_scale_rotate_crop_channels() -> None:
    # A plan with scale + rotate + translate produces animated transforms.
    p = build_template("09_cutout_parallax", "scene_002", 2000, seed=2, canvas_size=(640, 360))
    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")
    g = compiled.filter_graph
    assert "scale=" in g
    assert "rotate=" in g
    assert "overlay=" in g
    assert "eval=frame" in g
    assert "crop=iw-" not in g


def test_keyframes_are_compiled_as_time_varying_expressions() -> None:
    p = build_template("01_subject_slide_headline_pop", "scene_001", 2000, seed=1, canvas_size=(640, 360))
    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")

    assert "eval=frame" in compiled.filter_graph
    assert "if(lt(t\\," in compiled.filter_graph
    assert "scale=iw*1.0000" not in compiled.filter_graph


def test_opacity_keyframes_compile_to_time_varying_alpha_fade() -> None:
    p = build_template(
        "01_subject_slide_headline_pop",
        "scene_001",
        2000,
        seed=1,
        canvas_size=(640, 360),
    )
    foreground = next(layer for layer in p["layers"] if layer["asset_role"] == "foreground")
    foreground["transform"]["opacity"] = [[0, 0.0], [500, 1.0]]

    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")

    assert "fade=t=in:st=0.000:d=0.500:alpha=1" in compiled.filter_graph
    assert "colorchannelmixer=aa=0.000000" not in compiled.filter_graph


def test_text_event_is_visible_only_inside_its_narration_anchor_window() -> None:
    p = plan(duration=2000)
    p["text_animations"][0].update(
        {"text": "42 PERCENT", "start_ms": 960, "end_ms": 1860}
    )

    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")

    assert "text='42 PERCENT'" in compiled.filter_graph
    assert "enable='between(t\\,0.960\\,1.860)'" in compiled.filter_graph


def test_literal_percent_text_disables_ffmpeg_expansion() -> None:
    p = plan(duration=2_000)
    p["text_animations"] = [
        {"text": "42%", "start_ms": 500, "end_ms": 1_500}
    ]

    compiled = MotionCompiler().compile(p, assets=assets(p))

    assert "text='42%'" in compiled.filter_graph
    assert "expansion=none" in compiled.filter_graph


def test_camera_tracks_transform_the_composited_layer_stack() -> None:
    p = plan(duration=2000)
    p["camera"] = {
        "x": [[0, 0], [2000, 24]],
        "y": [[0, 0], [2000, -12]],
        "scale": [[0, 1.0], [2000, 1.08]],
    }

    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")

    assert "_cam_scaled]" in compiled.filter_graph
    assert "_cam]" in compiled.filter_graph
    assert "iw-640" in compiled.filter_graph
    assert "ih-360" in compiled.filter_graph


def test_editorial_grain_and_jitter_effects_are_compiled_not_ignored() -> None:
    p = plan(duration=2000)
    p["effects"] = [
        {"type": "film_grain", "amount": 0.08, "seed": 7},
        {"type": "jitter", "amount": 0.01},
    ]

    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")

    assert "noise=alls=8:allf=t+u:all_seed=7" in compiled.filter_graph
    assert "sin(n*0.700)" in compiled.filter_graph
    assert "cos(n*0.900)" in compiled.filter_graph


def test_template_jitter_amount_is_interpreted_as_pixels_not_canvas_fraction() -> None:
    p = plan()
    p["effects"] = [{"type": "jitter", "amount": 1.0}]
    compiled = MotionCompiler().compile(
        p,
        assets=assets(p),
        options=CompileOptions(width=640, height=360, fps=30),
    )

    assert "crop=638:358" in compiled.filter_graph
    assert "crop=616:336" not in compiled.filter_graph


def test_motion_is_sampled_at_editorial_cadence_then_output_at_30fps() -> None:
    p = plan(duration=2000)
    p["motion_fps"] = 12

    compiled = MotionCompiler().compile(p, assets=assets(p), output_path="o.mp4")

    assert "fps=fps=12,fps=fps=30" in compiled.filter_graph
    assert compiled.fps == 30


def test_text_layout_is_used_when_supplied() -> None:
    p = plan()
    compiler = MotionCompiler(text_layout=TextLayoutService())
    compiled = compiler.compile(p, assets=assets(p), output_path="o.mp4")

    assert "C\\:/Windows/Fonts" in compiled.filter_graph
    assert "fontsize=64" in compiled.filter_graph


def test_missing_asset_raises() -> None:
    p = plan()
    with pytest.raises(MotionCompilerError, match="asset"):
        MotionCompiler().compile(p, assets={}, output_path="o.mp4")


def test_plan_revalidated_via_schema() -> None:
    p = plan()
    # mutating the plan (removing duration) must fail at compile time.
    bad = dict(p)
    bad.pop("duration_ms", None)
    with pytest.raises(MotionCompilerError):
        MotionCompiler().compile(bad, assets=assets(p), output_path="o.mp4")


def test_compile_plan_convenience() -> None:
    p = plan()
    compiled = compile_plan(p, assets=assets(p), output_path="o.mp4")
    assert isinstance(compiled.command, list)


# --------------------------------------------------------------------------- #
# Real FFmpeg run (skipped when ffmpeg is unavailable)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_real_ffmpeg_render(tmp_path) -> None:
    from PIL import Image

    # Build tiny real PNGs and a short plan.
    w, h = 320, 180
    for role in ("background", "subject", "foreground"):
        color = (30, 60, 120, 255) if role == "background" else (200, 30, 30, 255)
        img = Image.new("RGBA", (w, h))
        img.paste(color, (0, 0, w, h))
        img.save(tmp_path / f"{role}.png")
    p = plan(duration=1000, size=(w, h))
    asset_map = {layer["asset_role"]: str(tmp_path / f"{layer['asset_role']}.png") for layer in p["layers"]}
    out = tmp_path / "out.mp4"
    compiled = MotionCompiler(ffmpeg_bin="ffmpeg").compile(p, assets=asset_map, output_path=str(out))

    proc = subprocess.run(compiled.command, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-1000:]
    assert out.is_file()
    assert out.stat().st_size > 0

    # probe: h264, yuv420p, correct fps/resolution.
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,pix_fmt,width,height,r_frame_rate",
            "-of", "default=noprint_wrappers=1", str(out),
        ],
        capture_output=True, text=True, timeout=30,
    )
    info = probe.stdout
    assert "h264" in info
    assert "yuv420p" in info
    assert "320x180" in info.replace(" ", "") or "320" in info and "180" in info
