"""Background music service (P8-T04).

Mixes an optional BGM track with voice narration using FFmpeg:
- Loop/trim BGM to match video duration
- Sidechain ducking (reduce BGM when voice plays)
- Fade in/out
- Voice must remain clear

When bgm_path is None or missing, returns voice unchanged.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BGMError(Exception):
    """Raised when BGM mixing fails."""


@dataclass
class BGMResult:
    """Result of BGM mixing."""
    output_path: Path
    duration_ms: int
    bgm_applied: bool


class BGMService:
    """Mix voice narration with background music."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self._runner = runner

    def mix(
        self,
        voice_path: str | Path,
        bgm_path: str | Path | None,
        output_path: str | Path,
        *,
        duration_ms: int = 0,
        voice_duck_db: float = -12,
        bgm_volume_db: float = -18,
        fade_in_ms: int = 2000,
        fade_out_ms: int = 3000,
    ) -> BGMResult:
        """Mix voice + BGM → output.

        ``voice_duck_db`` controls how much BGM is reduced during voice.
        ``bgm_volume_db`` is the base BGM volume.
        ``fade_in_ms``/``fade_out_ms`` apply fade effects to BGM.

        When ``bgm_path`` is None or doesn't exist, copies voice unchanged.
        """
        voice = Path(voice_path)
        output = Path(output_path)

        if not voice.is_file():
            raise BGMError(f"voice not found: {voice}")

        # No BGM → pass-through.
        if bgm_path is None or not Path(bgm_path).is_file():
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(voice), str(output))
            return BGMResult(output_path=output, duration_ms=duration_ms,
                             bgm_applied=False)

        bgm = Path(bgm_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        dur_s = duration_ms / 1000.0 if duration_ms > 0 else 0
        fade_in_s = fade_in_ms / 1000.0
        fade_out_s = fade_out_ms / 1000.0

        # Build filter_complex:
        # [1] BGM → loop if needed → trim → volume → fade → sidechain compress with voice
        # [0] voice stays at 0dB
        # Then amix both streams.
        filters: list[str] = []

        # BGM chain: loop, trim, volume, fade.
        bgm_chain = "[1:a]aloop=loop=-1:size=2e+09"
        if dur_s > 0:
            bgm_chain += f",atrim=0:{dur_s:.3f}"
        bgm_chain += f",volume={bgm_volume_db}dB"
        bgm_chain += f",afade=t=in:d={fade_in_s:.2f}"
        if dur_s > 0 and dur_s > fade_out_s:
            fade_start = dur_s - fade_out_s
            bgm_chain += f",afade=t=out:st={fade_start:.2f}:d={fade_out_s:.2f}"
        bgm_chain += "[bgm]"
        filters.append(bgm_chain)

        # Sidechain compress: duck BGM when voice is present.
        filters.append(
            "[bgm][0:a]sidechaincompress="
            "threshold=0.02:ratio=8:attack=50:release=300"
            ":level_sc=1[ducked]"
        )

        # Mix voice + ducked BGM.
        filters.append("[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2[out]")

        filter_str = ";".join(filters)

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(voice),
            "-i", str(bgm),
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-c:a", "aac", "-b:a", "192k",
            str(output),
        ]

        self._run(cmd)
        return BGMResult(output_path=output, duration_ms=duration_ms,
                         bgm_applied=True)

    def _run(self, cmd: list[str]) -> None:
        runner = self._runner or subprocess.run
        proc = runner(cmd, capture_output=True, text=True)
        if getattr(proc, "returncode", 0) != 0:
            raise BGMError(
                f"ffmpeg failed: {getattr(proc, 'stderr', '')}"
            )
