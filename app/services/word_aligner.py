"""Local acoustic word alignment for narration-driven editorial timing.

The aligner never estimates boundaries from text length. It asks a local
faster-whisper model for word timestamps and accepts them only when the decoded
word sequence matches the requested narration token-for-token.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.providers.base import TTSWordTiming


class AcousticAlignmentError(RuntimeError):
    """Raised when local audio cannot prove the requested word sequence."""


class FasterWhisperWordAligner:
    """Fail-closed local word aligner backed by an already-downloaded model."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        model: Any | None = None,
        device: str = "auto",
        compute_type: str = "int8",
        language: str | None = None,
    ) -> None:
        if model is None:
            path = Path(model_path or "").expanduser()
            if not path.is_dir():
                raise AcousticAlignmentError(
                    "local faster-whisper model directory is required; automatic download is disabled"
                )
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise AcousticAlignmentError("faster-whisper is not installed") from exc
            model = WhisperModel(
                str(path),
                device=device,
                compute_type=compute_type,
                local_files_only=True,
            )
        self.model = model
        self.language = language

    def align(
        self,
        wav_path: str | Path,
        text: str,
        duration_ms: int,
    ) -> tuple[TTSWordTiming, ...]:
        path = Path(wav_path)
        if not path.is_file():
            raise AcousticAlignmentError(f"audio file not found: {path}")
        if duration_ms <= 0:
            raise AcousticAlignmentError("measured audio duration must be positive")
        expected = _display_tokens(text)
        if not expected:
            raise AcousticAlignmentError("narration contains no alignable words")

        segments, _info = self.model.transcribe(
            str(path),
            language=self.language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        measured: list[tuple[str, int, int]] = []
        for segment in segments:
            for word in getattr(segment, "words", None) or []:
                token = str(getattr(word, "word", "")).strip()
                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                if not token or start is None or end is None:
                    continue
                for split_token in _display_tokens(token):
                    measured.append(
                        (split_token, int(round(float(start) * 1000)), int(round(float(end) * 1000)))
                    )

        if [_normalize(item[0]) for item in measured] != [_normalize(item) for item in expected]:
            raise AcousticAlignmentError(
                "transcript mismatch between narration and acoustically decoded words"
            )

        timings = tuple(
            TTSWordTiming(text=expected[index], start_ms=start_ms, end_ms=end_ms)
            for index, (_decoded, start_ms, end_ms) in enumerate(measured)
        )
        previous_end = 0
        for item in timings:
            if item.start_ms < previous_end:
                raise AcousticAlignmentError("word timestamps overlap or go backwards")
            if item.end_ms > duration_ms:
                raise AcousticAlignmentError("word timestamp exceeds measured audio duration")
            previous_end = item.end_ms
        return timings


def _display_tokens(value: str) -> list[str]:
    return re.findall(r"\w+", value, flags=re.UNICODE)


def _normalize(value: str) -> str:
    return value.casefold()
