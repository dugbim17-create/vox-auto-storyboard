"""Tests for P6-T05 local scene renderer.

Covers the acceptance criteria:

- correct FPS;
- correct resolution;
- correct duration (within ±1 frame);
- yuv420p;
- 12-template render smoke test (real ffmpeg when available).

The compiler/probe are injected with fakes for deterministic unit tests; one
integration test renders with the real FFmpeg binary when it is on PATH.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.services.ffmpeg_compiler import CompiledMotion
from app.services.motion_templates import build_template, template_names
from app.services.scene_renderer import (
    LocalSceneRenderer,
    RenderProbe,
    SceneRenderError,
    _parse_fps,
)
from app.storage.asset_store import AssetStore


def plan(name="01_subject_slide_headline_pop", duration=1000, size=(320, 180), seed=1) -> dict:
    return build_template(name, "scene_001", duration, seed=seed, canvas_size=size)


class FakeCompiler:
    """Deterministic compiler: captures assets, returns a canned command."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict, str]] = []

    def compile(self, plan, *, assets=None, output_path="") -> CompiledMotion:
        self.calls.append((plan, assets or {}, str(output_path)))
        return CompiledMotion(
            scene_id=plan["scene_id"],
            command=["ffmpeg", "-y", "-i", "x.png", "-filter_complex", "null", "-t", "1", str(output_path)],
            filter_graph="null",
            fps=30,
            width=plan.get("canvas", {}).get("width", 1920),
            height=plan.get("canvas", {}).get("height", 1080),
            duration_ms=plan.get("duration_ms", 0),
            frame_count=30,
        )


class FakeProbe:
    """Returns a canned RenderProbe and runs the same verify the real one does."""

    def __init__(self, fps=30.0, width=320, height=180, duration_ms=1000, pix_fmt="yuv420p") -> None:
        self.data = {"fps": fps, "width": width, "height": height, "duration_ms": duration_ms, "pix_fmt": pix_fmt}

    def __call__(self, path, plan):
        probe = RenderProbe(**self.data)
        canvas = plan.get("canvas", {})
        probe.verify(
            expected_fps=plan.get("fps", 30),
            expected_w=canvas.get("width", 1920),
            expected_h=canvas.get("height", 1080),
            expected_duration_ms=plan.get("duration_ms", 0),
        )
        return probe


class FakeRunner:
    def __init__(self, rc=0) -> None:
        self.rc = rc
        self.calls = 0

    def __call__(self, cmd, **kwargs):
        self.calls += 1
        # simulate ffmpeg producing its output file (last argv is the output).
        if self.rc == 0 and len(cmd) > 1:
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"fake-mp4")

        class P:
            returncode = self.rc
            stderr = "boom"
        return P()


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    store = AssetStore(root)
    store.init_project("prj")
    return root


# --------------------------------------------------------------------------- #
# RenderProbe.verify
# --------------------------------------------------------------------------- #
def test_probe_verify_ok() -> None:
    RenderProbe(fps=30.0, width=1920, height=1080, duration_ms=5320, pix_fmt="yuv420p").verify(
        expected_fps=30, expected_w=1920, expected_h=1080, expected_duration_ms=5320
    )


def test_probe_verify_bad_fps_raises() -> None:
    with pytest.raises(SceneRenderError):
        RenderProbe(fps=25.0, width=1920, height=1080, duration_ms=5320, pix_fmt="yuv420p").verify(
            expected_fps=30, expected_w=1920, expected_h=1080, expected_duration_ms=5320
        )


def test_probe_verify_bad_resolution_raises() -> None:
    with pytest.raises(SceneRenderError):
        RenderProbe(fps=30.0, width=1280, height=720, duration_ms=5320, pix_fmt="yuv420p").verify(
            expected_fps=30, expected_w=1920, expected_h=1080, expected_duration_ms=5320
        )


def test_probe_verify_bad_pix_fmt_raises() -> None:
    with pytest.raises(SceneRenderError, match="yuv420p"):
        RenderProbe(fps=30.0, width=1920, height=1080, duration_ms=5320, pix_fmt="nv12").verify(
            expected_fps=30, expected_w=1920, expected_h=1080, expected_duration_ms=5320
        )


def test_probe_verify_duration_within_tolerance() -> None:
    # 33ms = 1 frame at 30fps tolerance.
    RenderProbe(fps=30.0, width=320, height=180, duration_ms=967, pix_fmt="yuv420p").verify(
        expected_fps=30, expected_w=320, expected_h=180, expected_duration_ms=1000, tolerance_frames=1
    )
    RenderProbe(fps=30.0, width=320, height=180, duration_ms=966, pix_fmt="yuv420p").verify(
        expected_fps=30, expected_w=320, expected_h=180, expected_duration_ms=1000, tolerance_frames=1
    )
    RenderProbe(fps=30.0, width=320, height=180, duration_ms=964, pix_fmt="yuv420p").verify(
        expected_fps=30, expected_w=320, expected_h=180, expected_duration_ms=999, tolerance_frames=1
    )
    with pytest.raises(SceneRenderError):
        RenderProbe(fps=30.0, width=320, height=180, duration_ms=900, pix_fmt="yuv420p").verify(
            expected_fps=30, expected_w=320, expected_h=180, expected_duration_ms=1000, tolerance_frames=1
        )


# --------------------------------------------------------------------------- #
# Renderer with injected fakes
# --------------------------------------------------------------------------- #
def test_renderer_writes_to_scenes_dir(project_root) -> None:
    compiler = FakeCompiler()
    renderer = LocalSceneRenderer(
        compiler=compiler, project_root=project_root, runner=FakeRunner(rc=0)
    )
    renderer._probe = FakeProbe()  # inject canned probe

    out, probe = renderer.render_scene("prj", "scene_001", plan())
    assert out.name == "scene_001.mp4"
    assert (project_root / "prj" / "scenes" / "scene_001.mp4").is_file()
    assert probe.pix_fmt == "yuv420p"


def test_renderer_compiler_receives_plan_and_assets(project_root) -> None:
    compiler = FakeCompiler()
    renderer = LocalSceneRenderer(compiler=compiler, project_root=project_root, runner=FakeRunner(rc=0))
    renderer._probe = FakeProbe()
    p = plan()
    assets = {layer["asset_role"]: str(project_root / "prj" / "layers" / f"scene_001_{layer['asset_role']}.png") for layer in p["layers"]}

    renderer.render_scene("prj", "scene_001", p, assets=assets)
    assert len(compiler.calls) == 1
    received_plan, received_assets, out = compiler.calls[0]
    assert received_plan == p
    assert received_assets == assets
    assert out.endswith("scene_001.mp4")


def test_renderer_default_assets_from_layers_dir(project_root) -> None:
    from PIL import Image

    # Write layer files matching default naming.
    p = plan()
    for layer in p["layers"]:
        role = layer["asset_role"]
        img = Image.new("RGBA", (320, 180))
        img.paste((30, 60, 120, 255), (0, 0, 320, 180))
        img.save(project_root / "prj" / "layers" / f"scene_001_{role}.png")

    compiler = FakeCompiler()
    renderer = LocalSceneRenderer(compiler=compiler, project_root=project_root, runner=FakeRunner(rc=0))
    renderer._probe = FakeProbe()
    renderer.render_scene("prj", "scene_001", p)
    _received_plan, received_assets, _ = compiler.calls[0]
    for layer in p["layers"]:
        role = layer["asset_role"]
        assert received_assets.get(role, "").endswith(f"scene_001_{role}.png")


def test_renderer_propagates_ffmpeg_failure(project_root) -> None:
    renderer = LocalSceneRenderer(
        compiler=FakeCompiler(), project_root=project_root, runner=FakeRunner(rc=1)
    )
    renderer._probe = FakeProbe()
    with pytest.raises(SceneRenderError, match="ffmpeg failed"):
        renderer.render_scene("prj", "scene_001", plan())


def test_renderer_probe_mismatch_raises(project_root) -> None:
    compiler = FakeCompiler()
    renderer = LocalSceneRenderer(compiler=compiler, project_root=project_root, runner=FakeRunner(rc=0))
    # probe reports wrong fps -> verify raises.
    renderer._probe = FakeProbe(fps=25.0)
    with pytest.raises(SceneRenderError, match="fps"):
        renderer.render_scene("prj", "scene_001", plan())


# --------------------------------------------------------------------------- #
# _parse_fps helper
# --------------------------------------------------------------------------- #
def test_parse_fps() -> None:
    assert _parse_fps("30/1") == 30.0
    assert _parse_fps("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert _parse_fps("25") == 25.0
    assert _parse_fps("garbage") == 0.0
    assert _parse_fps("") == 0.0


# --------------------------------------------------------------------------- #
# Real FFmpeg integration (12-template smoke, when ffmpeg is available)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="ffmpeg/ffprobe not on PATH")
def _write_layer_assets(root: Path, scene: str, p: dict) -> None:
    """Write default-named layer PNGs for a plan under a project root."""
    from PIL import Image

    layers_dir = root / "prj" / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    for layer in p["layers"]:
        role = layer["asset_role"]
        img = Image.new("RGBA", (320, 180))
        color = (30, 60, 120, 255) if role == "background" else (200, 30, 30, 255)
        img.paste(color, (0, 0, 320, 180))
        img.save(layers_dir / f"{scene}_{role}.png")


def test_real_render_single_scene(project_root) -> None:
    p = plan(duration=800, size=(320, 180))
    _write_layer_assets(project_root, "scene_001", p)

    renderer = LocalSceneRenderer(project_root=project_root)
    out, probe = renderer.render_scene("prj", "scene_001", p)
    assert out.is_file()
    assert probe.fps == 30
    assert probe.pix_fmt == "yuv420p"
    assert probe.width == 320 and probe.height == 180
    assert abs(probe.duration_ms - 800) <= 33


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="ffmpeg/ffprobe not on PATH")
def test_real_render_12_template_smoke(project_root) -> None:
    renderer = LocalSceneRenderer(project_root=project_root)
    for i, name in enumerate(template_names()):
        scene = f"scene_{i:03d}"
        p = build_template(name, scene, 800, seed=1, canvas_size=(320, 180))
        _write_layer_assets(project_root, scene, p)
        out, probe = renderer.render_scene("prj", scene, p)
        assert out.is_file(), name
        assert probe.pix_fmt == "yuv420p", name
        assert abs(probe.duration_ms - 800) <= 33, name
