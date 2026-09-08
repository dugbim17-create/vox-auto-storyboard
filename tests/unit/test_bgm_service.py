"""Tests for bgm_service (P8-T04)."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from app.services.bgm_service import BGMError, BGMService


class FakeRunner:
    def __init__(self, rc: int = 0) -> None:
        self.rc = rc
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_: Any) -> Any:
        self.calls.append(list(cmd))
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-mixed-audio")

        class P:
            returncode = self.rc
            stderr = ""
        return P()


class TestMixProducesOutput:
    def test_mix_creates_file(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        bgm = tmp_path / "bgm.mp3"
        voice.write_bytes(b"voice-data")
        bgm.write_bytes(b"bgm-data")
        runner = FakeRunner()
        svc = BGMService(runner=runner)
        result = svc.mix(voice, bgm, tmp_path / "out.wav", duration_ms=30000)
        assert result.output_path.is_file()
        assert result.bgm_applied is True
        assert len(runner.calls) == 1


class TestNoBGM:
    def test_no_bgm_returns_voice_unchanged(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        voice.write_bytes(b"voice-data")
        svc = BGMService(runner=FakeRunner())
        result = svc.mix(voice, None, tmp_path / "out.wav", duration_ms=5000)
        assert result.bgm_applied is False
        assert result.output_path.is_file()
        # Content should be copied from voice.
        assert result.output_path.read_bytes() == b"voice-data"


class TestBGMMissingFile:
    def test_bgm_missing_file_skips(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        voice.write_bytes(b"voice-data")
        svc = BGMService(runner=FakeRunner())
        result = svc.mix(voice, tmp_path / "nonexistent.mp3",
                         tmp_path / "out.wav", duration_ms=5000)
        assert result.bgm_applied is False


class TestCommandHasSidechainFilter:
    def test_sidechaincompress_in_command(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        bgm = tmp_path / "bgm.mp3"
        voice.write_bytes(b"voice")
        bgm.write_bytes(b"bgm")
        runner = FakeRunner()
        svc = BGMService(runner=runner)
        svc.mix(voice, bgm, tmp_path / "out.wav", duration_ms=30000)
        cmd_str = " ".join(runner.calls[0])
        assert "sidechaincompress" in cmd_str


class TestFadeInOut:
    def test_fade_in_out_in_command(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        bgm = tmp_path / "bgm.mp3"
        voice.write_bytes(b"voice")
        bgm.write_bytes(b"bgm")
        runner = FakeRunner()
        svc = BGMService(runner=runner)
        svc.mix(voice, bgm, tmp_path / "out.wav", duration_ms=30000,
                fade_in_ms=2000, fade_out_ms=3000)
        cmd_str = " ".join(runner.calls[0])
        assert "afade=t=in" in cmd_str
        assert "afade=t=out" in cmd_str


class TestLoopTrim:
    def test_loop_trim_in_command(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        bgm = tmp_path / "bgm.mp3"
        voice.write_bytes(b"voice")
        bgm.write_bytes(b"bgm")
        runner = FakeRunner()
        svc = BGMService(runner=runner)
        svc.mix(voice, bgm, tmp_path / "out.wav", duration_ms=60000)
        cmd_str = " ".join(runner.calls[0])
        assert "aloop" in cmd_str
        assert "atrim" in cmd_str


class TestSafety:
    def test_no_shell_true(self):
        import app.services.bgm_service as mod
        source = inspect.getsource(mod)
        assert "shell=True" not in source

    def test_command_is_list(self, tmp_path: Path):
        voice = tmp_path / "voice.wav"
        bgm = tmp_path / "bgm.mp3"
        voice.write_bytes(b"voice")
        bgm.write_bytes(b"bgm")
        runner = FakeRunner()
        svc = BGMService(runner=runner)
        svc.mix(voice, bgm, tmp_path / "out.wav", duration_ms=5000)
        assert isinstance(runner.calls[0], list)


class TestVoiceMissing:
    def test_voice_not_found_raises(self, tmp_path: Path):
        svc = BGMService(runner=FakeRunner())
        with pytest.raises(BGMError, match="voice not found"):
            svc.mix(tmp_path / "missing.wav", None, tmp_path / "out.wav")
