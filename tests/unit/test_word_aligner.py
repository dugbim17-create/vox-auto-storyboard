from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.word_aligner import AcousticAlignmentError, FasterWhisperWordAligner


class FakeModel:
    def __init__(self, words):
        self.words = words
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return [SimpleNamespace(words=self.words)], SimpleNamespace(language="vi")


def test_aligner_returns_measured_word_boundaries(tmp_path: Path) -> None:
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"wav")
    model = FakeModel(
        [
            SimpleNamespace(word=" Xin", start=0.10, end=0.32),
            SimpleNamespace(word=" chào", start=0.40, end=0.78),
        ]
    )

    result = FasterWhisperWordAligner(model=model).align(wav, "Xin chào", 900)

    assert [(item.text, item.start_ms, item.end_ms) for item in result] == [
        ("Xin", 100, 320),
        ("chào", 400, 780),
    ]
    assert model.calls[0][1]["word_timestamps"] is True


def test_aligner_rejects_transcript_mismatch(tmp_path: Path) -> None:
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"wav")
    model = FakeModel(
        [
            SimpleNamespace(word=" Xin", start=0.10, end=0.32),
            SimpleNamespace(word=" khác", start=0.40, end=0.78),
        ]
    )

    with pytest.raises(AcousticAlignmentError, match="transcript mismatch"):
        FasterWhisperWordAligner(model=model).align(wav, "Xin chào", 900)
