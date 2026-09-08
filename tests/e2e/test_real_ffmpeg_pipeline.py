"""Real local production-path acceptance: PNG -> scene MP4 -> WAV -> SRT -> final MP4."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app.services.ffmpeg_compiler import MotionCompiler
from app.services.final_composer import FinalComposer
from app.services.motion_templates import build_template
from app.services.scene_renderer import LocalSceneRenderer
from app.services.subtitle_generator import SceneNarration, SubtitleGenerator
from app.storage.asset_store import AssetStore

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required for real artifact acceptance",
)


def _probe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _write_wav(path: Path, duration_ms: int) -> None:
    frames = int(16000 * duration_ms / 1000)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\x00\x00" * frames)


def test_real_ffmpeg_production_path_creates_valid_artifacts(tmp_path: Path) -> None:
    from PIL import Image

    project_id = "prj_real_acceptance"
    store = AssetStore(tmp_path / "projects")
    store.init_project(project_id)
    layers = store.subdir(project_id, "layers")
    for role, color in {
        "background": (30, 60, 120, 255),
        "subject": (220, 60, 60, 255),
        "foreground": (40, 180, 120, 180),
    }.items():
        Image.new("RGBA", (320, 180), color).save(layers / f"scene_001_{role}.png")

    plan = build_template(
        "01_subject_slide_headline_pop",
        project_id,
        1000,
        seed=7,
        canvas_size=(320, 180),
    )
    scene_path, scene_probe = LocalSceneRenderer(
        compiler=MotionCompiler(ffmpeg_bin="ffmpeg"),
        project_root=tmp_path / "projects",
    ).render_scene(project_id, "scene_001", plan)
    assert scene_path.is_file() and scene_path.stat().st_size > 0
    assert scene_probe.width == 320
    assert scene_probe.height == 180
    assert scene_probe.pix_fmt == "yuv420p"

    audio_path = store.subdir(project_id, "audio") / "narration.wav"
    _write_wav(audio_path, 1000)
    srt_path = store.subdir(project_id, "final") / "subtitles.srt"
    SubtitleGenerator().generate(
        project_id,
        [SceneNarration(
            scene_id="scene_001",
            narration="A real local acceptance scene.",
            voice_duration_ms=1000,
            order=1,
        )],
        srt_path,
    )
    assert srt_path.is_file() and "A real local acceptance scene." in srt_path.read_text("utf-8")

    final_path = store.subdir(project_id, "final") / "final.mp4"
    output, final_probe = FinalComposer(ffmpeg_bin="ffmpeg", ffprobe_bin="ffprobe").compose(
        [scene_path],
        audio_path,
        final_path,
        fps=30,
        width=320,
        height=180,
        expected_duration_ms=1120,
        subtitle_path=srt_path,
    )
    assert output == final_path and output.is_file() and output.stat().st_size > 0
    assert final_probe.has_audio is True
    assert final_probe.pix_fmt == "yuv420p"

    metadata = _probe(output)
    streams = metadata["streams"]
    assert any(s.get("codec_type") == "video" and s.get("codec_name") == "h264" for s in streams)
    assert any(s.get("codec_type") == "audio" and s.get("codec_name") == "aac" for s in streams)
    assert any(s.get("codec_type") == "subtitle" for s in streams)
    assert json.loads(json.dumps(metadata))["format"]["format_name"]
