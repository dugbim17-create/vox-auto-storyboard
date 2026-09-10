from pathlib import Path

import pytest

from app.services.quiz_voice_registry import (
    PiperVoiceError,
    resolve_requested_voice,
    resolve_voice_assets,
)


def test_exact_locale_resolution_requires_model_and_config(tmp_path: Path) -> None:
    locale_dir = tmp_path / "de-DE"
    locale_dir.mkdir()
    model = locale_dir / "de_DE-thorsten-high.onnx"
    config = locale_dir / "de_DE-thorsten-high.onnx.json"
    model.write_bytes(b"model")
    config.write_text('{"language":{"code":"de_DE"}}', encoding="utf-8")
    resolved = resolve_voice_assets(tmp_path, locale="de-DE", voice_id="de_DE-thorsten-high")
    assert resolved["model_path"] == model.resolve()
    assert resolved["config_path"] == config.resolve()


def test_wrong_locale_never_falls_back() -> None:
    with pytest.raises(PiperVoiceError, match="locale mismatch"):
        resolve_requested_voice(locale="de-DE", requested_voice="en_US-ryan-high", strict=True)


def test_unknown_locale_is_explicitly_blocked() -> None:
    with pytest.raises(PiperVoiceError, match="No Piper voice"):
        resolve_requested_voice(locale="ja-JP", requested_voice=None, strict=True)
