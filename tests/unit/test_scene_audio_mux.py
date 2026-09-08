"""Tests for scene_audio_mux (P8-T02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.scene_audio_mux import (
    AudioMuxError,
    MuxProbe,
    SceneAudioMuxer,
)


# ------------------------------------------------------------------ #
# Fakes
# ------------------------------------------------------------------ #
class FakeRunner:
    """Captures commands, writes a placeholder output file."""

    def __init__(self, rc: int = 0) -> None:
        self.rc = rc
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_: Any) -> Any:
        self.calls.append(list(cmd))
        # Write fake output to the last arg (FFmpeg convention).
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-muxed-mp4")

        class Proc:
            returncode = self.rc
            stderr = "error" if self.rc else ""
        return Proc()


# ------------------------------------------------------------------ #
# MuxProbe.verify
# ------------------------------------------------------------------ #
class TestMuxProbe:
    def test_sync_ok(self):
        probe = MuxProbe(
            video_duration_ms=5000,
            audio_duration_ms=5020,
            has_audio=True,
            audio_codec="aac",
            fps=30.0,
        )
        probe.verify(expected_fps=30)  # within 1 frame = 33ms

    def test_sync_drift_raises(self):
        probe = MuxProbe(
            video_duration_ms=5000,
            audio_duration_ms=5100,
            has_audio=True,
            audio_codec="aac",
            fps=30.0,
        )
        with pytest.raises(AudioMuxError, match="drift"):
            probe.verify(expected_fps=30)

    def test_no_audio_raises(self):
        probe = MuxProbe(
            video_duration_ms=5000,
            audio_duration_ms=0,
            has_audio=False,
            audio_codec="",
            fps=30.0,
        )
        with pytest.raises(AudioMuxError, match="no audio"):
            probe.verify()


# ------------------------------------------------------------------ #
# SceneAudioMuxer
# ------------------------------------------------------------------ #
class TestSceneAudioMuxer:
    def test_mux_calls_ffmpeg(self, tmp_path: Path):
        video = tmp_path / "scene.mp4"
        audio = tmp_path / "voice.wav"
        video.write_bytes(b"video-data")
        audio.write_bytes(b"audio-data")
        out = tmp_path / "out" / "scene_muxed.mp4"

        runner = FakeRunner()
        muxer = SceneAudioMuxer(runner=runner)
        # Override probe to return a valid result.
        muxer._probe = lambda p, fps=30: MuxProbe(  # type: ignore[assignment]
            video_duration_ms=5000, audio_duration_ms=5000,
            has_audio=True, audio_codec="aac", fps=30.0,
        )

        result_path, probe = muxer.mux(video, audio, out)
        assert result_path.is_file()
        assert probe.has_audio
        assert len(runner.calls) == 1
        cmd = runner.calls[0]
        assert "-c:v" in cmd
        assert "copy" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "apad" in " ".join(cmd)

    def test_mux_missing_video_raises(self, tmp_path: Path):
        audio = tmp_path / "voice.wav"
        audio.write_bytes(b"audio-data")
        muxer = SceneAudioMuxer(runner=FakeRunner())
        with pytest.raises(AudioMuxError, match="video not found"):
            muxer.mux(tmp_path / "missing.mp4", audio, tmp_path / "out.mp4")

    def test_mux_missing_audio_raises(self, tmp_path: Path):
        video = tmp_path / "scene.mp4"
        video.write_bytes(b"video-data")
        muxer = SceneAudioMuxer(runner=FakeRunner())
        with pytest.raises(AudioMuxError, match="audio not found"):
            muxer.mux(video, tmp_path / "missing.wav", tmp_path / "out.mp4")

    def test_mux_ffmpeg_failure(self, tmp_path: Path):
        video = tmp_path / "scene.mp4"
        audio = tmp_path / "voice.wav"
        video.write_bytes(b"video-data")
        audio.write_bytes(b"audio-data")
        muxer = SceneAudioMuxer(runner=FakeRunner(rc=1))
        muxer._probe_duration_ms = lambda _path: 1000  # type: ignore[method-assign]  # noqa: SLF001
        with pytest.raises(AudioMuxError, match="ffmpeg failed"):
            muxer.mux(video, audio, tmp_path / "out.mp4")

    def test_no_shell_true(self):
        """Verify the module never uses shell=True."""
        import inspect

        import app.services.scene_audio_mux as mod
        source = inspect.getsource(mod)
        assert "shell=True" not in source

    def test_command_is_list(self, tmp_path: Path):
        """Verify FFmpeg is called with argument list, not string."""
        video = tmp_path / "scene.mp4"
        audio = tmp_path / "voice.wav"
        video.write_bytes(b"video-data")
        audio.write_bytes(b"audio-data")
        runner = FakeRunner()
        muxer = SceneAudioMuxer(runner=runner)
        muxer._probe = lambda p, fps=30: MuxProbe(  # type: ignore[assignment]
            video_duration_ms=5000, audio_duration_ms=5000,
            has_audio=True, audio_codec="aac", fps=30.0,
        )
        muxer.mux(video, audio, tmp_path / "out.mp4")
        assert isinstance(runner.calls[0], list)

    def test_concat_audio_single(self, tmp_path: Path):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"wav-data")
        muxer = SceneAudioMuxer(runner=FakeRunner())
        out = muxer.concat_audio([wav], tmp_path / "combined.wav")
        assert out.is_file()

    def test_concat_audio_multiple(self, tmp_path: Path):
        wav1 = tmp_path / "a.wav"
        wav2 = tmp_path / "b.wav"
        wav1.write_bytes(b"wav1")
        wav2.write_bytes(b"wav2")
        runner = FakeRunner()
        muxer = SceneAudioMuxer(runner=runner)
        out = muxer.concat_audio([wav1, wav2], tmp_path / "combined.wav")
        assert out.is_file()
        assert len(runner.calls) == 1
        assert "-f" in runner.calls[0]
        assert "concat" in runner.calls[0]
