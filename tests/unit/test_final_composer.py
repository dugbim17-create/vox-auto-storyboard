"""Tests for P7-T01 FinalComposer.

Covers:

- no scenes -> raises;
- missing scene file -> raises before ffmpeg;
- fake-runner captures the concat demuxer command (with + without audio);
- FinalProbe.verify happy path + each failure mode;
- _parse_fps edge cases.

The runner is injected so no real FFmpeg binary is invoked in unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.final_composer import (
    FinalComposer,
    FinalComposerError,
    FinalProbe,
    _parse_fps,
)


# --------------------------------------------------------------------------- #
# Fake runner / probe
# --------------------------------------------------------------------------- #
class FakeRunner:
    """Captures every command and returns rc=0. Writes a tiny fake file."""

    def __init__(self, rc: int = 0, audio: bool = False) -> None:
        self.rc = rc
        self.audio = audio
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **_):
        self.calls.append(list(cmd))
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-mp4")

        class P:
            returncode = self.rc
            stderr = "boom"
        return P()


class FakeProbe:
    """Returns a canned FinalProbe data dict; skips real ffprobe."""

    def __init__(self, fps=30.0, width=1920, height=1080, duration_ms=2000,
                 pix_fmt="yuv420p", audio=False) -> None:
        self.data = {
            "fps": fps, "width": width, "height": height, "duration_ms": duration_ms,
            "pix_fmt": pix_fmt, "has_audio": audio,
        }

    def __call__(self, _composer: FinalComposer, _path: Path) -> dict:
        return self.data


# --------------------------------------------------------------------------- #
# FinalProbe.verify
# --------------------------------------------------------------------------- #
def test_probe_verify_ok() -> None:
    FinalProbe(fps=30.0, width=1920, height=1080, duration_ms=5320,
               pix_fmt="yuv420p", has_audio=True).verify(
        expected_fps=30, expected_w=1920, expected_h=1080,
        expected_duration_ms=5320, expected_audio=True,
    )


def test_probe_verify_bad_fps() -> None:
    with pytest.raises(FinalComposerError, match="fps"):
        FinalProbe(fps=25.0, width=1920, height=1080, duration_ms=5320,
                   pix_fmt="yuv420p", has_audio=False).verify(
            expected_fps=30, expected_w=1920, expected_h=1080,
            expected_duration_ms=5320, expected_audio=False,
        )


def test_probe_verify_bad_resolution() -> None:
    with pytest.raises(FinalComposerError, match="resolution"):
        FinalProbe(fps=30.0, width=1280, height=720, duration_ms=5320,
                   pix_fmt="yuv420p", has_audio=False).verify(
            expected_fps=30, expected_w=1920, expected_h=1080,
            expected_duration_ms=5320, expected_audio=False,
        )


def test_probe_verify_bad_pix_fmt() -> None:
    with pytest.raises(FinalComposerError, match="yuv420p"):
        FinalProbe(fps=30.0, width=1920, height=1080, duration_ms=5320,
                   pix_fmt="nv12", has_audio=False).verify(
            expected_fps=30, expected_w=1920, expected_h=1080,
            expected_duration_ms=5320, expected_audio=False,
        )


def test_probe_verify_duration_tolerance() -> None:
    # 33ms = 1 frame at 30fps tolerance.
    FinalProbe(fps=30.0, width=1920, height=1080, duration_ms=967,
               pix_fmt="yuv420p", has_audio=False).verify(
        expected_fps=30, expected_w=1920, expected_h=1080,
        expected_duration_ms=1000, expected_audio=False, tolerance_frames=1,
    )
    with pytest.raises(FinalComposerError, match="duration"):
        FinalProbe(fps=30.0, width=1920, height=1080, duration_ms=900,
                   pix_fmt="yuv420p", has_audio=False).verify(
            expected_fps=30, expected_w=1920, expected_h=1080,
            expected_duration_ms=1000, expected_audio=False, tolerance_frames=1,
        )


def test_probe_verify_audio_mismatch() -> None:
    with pytest.raises(FinalComposerError, match="audio mismatch"):
        FinalProbe(fps=30.0, width=1920, height=1080, duration_ms=1000,
                   pix_fmt="yuv420p", has_audio=True).verify(
            expected_fps=30, expected_w=1920, expected_h=1080,
            expected_duration_ms=1000, expected_audio=False,
        )


# --------------------------------------------------------------------------- #
# _parse_fps
# --------------------------------------------------------------------------- #
def test_parse_fps() -> None:
    assert _parse_fps("30/1") == 30.0
    assert _parse_fps("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert _parse_fps("25") == 25.0
    assert _parse_fps("garbage") == 0.0
    assert _parse_fps("") == 0.0


# --------------------------------------------------------------------------- #
# FinalComposer.compose
# --------------------------------------------------------------------------- #
def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def test_compose_no_scenes_raises(tmp_path: Path) -> None:
    composer = FinalComposer(runner=FakeRunner())
    with pytest.raises(FinalComposerError, match="no scenes"):
        composer.compose([], None, tmp_path / "final.mp4")


def test_compose_missing_scene_raises(tmp_path: Path) -> None:
    composer = FinalComposer(runner=FakeRunner())
    missing = tmp_path / "scene_001.mp4"
    with pytest.raises(FinalComposerError, match="missing scene"):
        composer.compose([missing], None, tmp_path / "final.mp4")


def test_compose_missing_audio_raises(tmp_path: Path) -> None:
    composer = FinalComposer(runner=FakeRunner())
    scene = _touch(tmp_path / "scenes" / "scene_001.mp4")
    with pytest.raises(FinalComposerError, match="audio"):
        composer.compose([scene], tmp_path / "no.wav", tmp_path / "final.mp4")


def test_compose_no_audio_command(tmp_path: Path) -> None:
    scene = _touch(tmp_path / "scenes" / "scene_001.mp4")
    runner = FakeRunner()
    composer = FinalComposer(runner=runner)

    def _fake_probe(_p):
        return FakeProbe(audio=False)(composer, _p)
    composer._run_probe = _fake_probe  # type: ignore[assignment]

    out, probe = composer.compose([scene], None, tmp_path / "final.mp4")
    assert out.is_file()
    assert not probe.has_audio
    cmd = runner.calls[0]
    assert "-c:v" in cmd and "copy" in cmd
    assert "-c:a" not in cmd
    # No audio input
    assert sum(1 for x in cmd if x == "-i") == 1


def test_compose_with_audio_command(tmp_path: Path) -> None:
    scene = _touch(tmp_path / "scenes" / "scene_001.mp4")
    audio = _touch(tmp_path / "audio" / "narration.wav")
    runner = FakeRunner()
    composer = FinalComposer(runner=runner)

    def _fake_probe(_p):
        return FakeProbe(width=320, height=180, duration_ms=1000, audio=True)(
            composer, _p
        )
    composer._run_probe = _fake_probe  # type: ignore[assignment]

    out, probe = composer.compose(
        [scene], audio, tmp_path / "final.mp4",
        fps=30, width=320, height=180, expected_duration_ms=1000,
    )
    assert out.is_file()
    assert probe.has_audio
    cmd = runner.calls[0]
    assert "-c:a" in cmd and "aac" in cmd
    assert "-shortest" not in cmd
    # Two inputs (concat list + audio)
    assert sum(1 for x in cmd if x == "-i") == 2


def test_compose_writes_concat_list(tmp_path: Path) -> None:
    scenes = [
        _touch(tmp_path / "scenes" / "scene_001.mp4"),
        _touch(tmp_path / "scenes" / "scene_002.mp4"),
    ]
    runner = FakeRunner()
    composer = FinalComposer(runner=runner)

    def _fake_probe(_p):
        return FakeProbe(width=320, height=180)(composer, _p)
    composer._run_probe = _fake_probe  # type: ignore[assignment]

    # Pass expected_duration_ms explicitly to avoid summing per-scene probes
    # (which return the same canned value for every path under the fake).
    composer.compose(
        scenes, None, tmp_path / "final.mp4",
        width=320, height=180, expected_duration_ms=2000,
    )
    list_file = tmp_path / "_concat_list.txt"
    assert list_file.is_file()
    lines = list_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line, scene in zip(lines, scenes, strict=True):
        assert line.startswith("file '")
        assert line.endswith(".mp4'")
        assert scene.name in line


def test_compose_ffmpeg_failure_propagates(tmp_path: Path) -> None:
    scene = _touch(tmp_path / "scenes" / "scene_001.mp4")
    runner = FakeRunner(rc=1)
    composer = FinalComposer(runner=runner)
    with pytest.raises(FinalComposerError, match="ffmpeg failed"):
        composer.compose([scene], None, tmp_path / "final.mp4")


def test_compose_uses_concat_demuxer(tmp_path: Path) -> None:
    scene = _touch(tmp_path / "scenes" / "scene_001.mp4")
    runner = FakeRunner()
    composer = FinalComposer(runner=runner)

    def _fake_probe(_p):
        return FakeProbe()(composer, _p)
    composer._run_probe = _fake_probe  # type: ignore[assignment]

    composer.compose([scene], None, tmp_path / "final.mp4", width=1920, height=1080)
    cmd = runner.calls[0]
    # Concat demuxer + safe 0
    assert "-f" in cmd and "concat" in cmd
    assert "-safe" in cmd and "0" in cmd


def test_compose_creates_output_dir(tmp_path: Path) -> None:
    scene = _touch(tmp_path / "scenes" / "scene_001.mp4")
    runner = FakeRunner()
    composer = FinalComposer(runner=runner)

    def _fake_probe(_p):
        return FakeProbe()(composer, _p)
    composer._run_probe = _fake_probe  # type: ignore[assignment]

    nested = tmp_path / "deep" / "nested" / "final.mp4"
    out, _ = composer.compose([scene], None, nested, width=1920, height=1080)
    assert out == nested
    assert out.is_file()
