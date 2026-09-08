"""Transition assembly service (P8-T03).

Applies transitions between scene MP4s using FFmpeg xfade filters.

Supported transitions:
- hard_cut (default) — simple concat, 0ms overlap
- crossfade — FFmpeg xfade 'fade', default 500ms
- paper_wipe — FFmpeg xfade 'wipeleft'
- dip_to_color — FFmpeg xfade 'fadeblack'

MVP constraint: transitions use the lead_out/lead_in padding (120+220=340ms)
so narration timing is not affected.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Map internal transition names to FFmpeg xfade transition names.
_XFADE_MAP: dict[str, str] = {
    "crossfade": "fade",
    "paper_wipe": "wipeleft",
    "paper_tear": "wiperight",
    "wipe_left": "wipeleft",
    "wipe_right": "wiperight",
    "dip_to_color": "fadeblack",
}

# Default transition overlap in seconds.
DEFAULT_TRANSITION_DURATION = 0.5
# Max overlap uses the lead_in + lead_out padding.
MAX_OVERLAP_MS = 340  # 120 + 220 from MASTER_PLAN section 12.2


class TransitionError(Exception):
    """Raised when transition assembly fails."""


@dataclass
class TransitionResult:
    """Result of applying transitions."""
    output_path: Path
    transition_count: int
    total_duration_ms: int


class TransitionService:
    """Apply transitions between scene MP4s."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        runner: Callable[..., Any] | None = None,
        scene_duration_ms: int = 5000,
        scene_durations_ms: list[int] | None = None,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self._runner = runner
        self._scene_dur_ms = scene_duration_ms
        self._scene_durations_ms = list(scene_durations_ms or [])

    def apply_transitions(
        self,
        scene_paths: list[Path],
        transitions: list[str],
        output_path: Path,
        *,
        fps: int = 30,
        transition_duration: float = DEFAULT_TRANSITION_DURATION,
    ) -> TransitionResult:
        """Apply transitions between scenes and produce a single MP4.

        ``transitions`` is a list of transition names, one per scene boundary
        (len = len(scene_paths) - 1). Missing/unknown entries default to hard_cut.
        """
        scene_paths = [Path(s) for s in scene_paths]
        if not scene_paths:
            raise TransitionError("no scenes to assemble")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if len(scene_paths) == 1:
            # Single scene — just copy.
            import shutil
            shutil.copy2(str(scene_paths[0]), str(output))
            total_ms = self._duration_for(0)
            return TransitionResult(output_path=output, transition_count=0,
                                    total_duration_ms=total_ms)

        # Pad transitions list to match boundaries.
        n_boundaries = len(scene_paths) - 1
        while len(transitions) < n_boundaries:
            transitions.append("hard_cut")

        # Check if ALL transitions are hard_cut — use fast concat.
        all_hard = all(self._resolve(t) == "hard_cut" for t in transitions[:n_boundaries])
        if all_hard:
            return self._concat(scene_paths, output, fps=fps)

        # Build xfade filter chain.
        return self._xfade(scene_paths, transitions[:n_boundaries], output,
                           fps=fps, duration=transition_duration)

    # ------------------------------------------------------------------ #
    # Strategies
    # ------------------------------------------------------------------ #
    def _concat(self, scenes: list[Path], output: Path, *, fps: int) -> TransitionResult:
        """Fast concat demuxer (no transition overlap)."""
        list_file = output.parent / "_transition_concat.txt"
        lines = []
        for s in scenes:
            escaped = str(s.resolve()).replace("\\", "/").replace("'", r"\'")
            lines.append(f"file '{escaped}'")
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [
            self.ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output),
        ]
        self._run(cmd)
        total_ms = sum(self._duration_for(i) for i in range(len(scenes)))
        return TransitionResult(output_path=output, transition_count=0,
                                total_duration_ms=total_ms)

    def _xfade(
        self,
        scenes: list[Path],
        transitions: list[str],
        output: Path,
        *,
        fps: int,
        duration: float,
    ) -> TransitionResult:
        """Build xfade filter chain for scene transitions."""
        n = len(scenes)
        # Clamp duration.
        dur = min(duration, MAX_OVERLAP_MS / 1000.0)

        # Build input args.
        cmd: list[str] = [self.ffmpeg_bin, "-y"]
        for s in scenes:
            cmd += ["-i", str(s)]

        # Build filter_complex.
        # Each xfade takes two inputs and produces one output.
        filters: list[str] = []
        transition_count = 0

        for i in range(n - 1):
            xfade_name = self._resolve(transitions[i])
            if xfade_name == "hard_cut":
                # Can't mix hard_cut with xfade in same chain easily.
                # Use a 0-duration crossfade as placeholder.
                xfade_name = "fade"
                dur_i = 0.001  # near-zero
            else:
                dur_i = dur

            prior_duration_s = sum(self._duration_for(j) for j in range(i + 1)) / 1000.0
            prior_overlap_s = sum(
                min(dur, self._duration_for(j) / 1000.0) for j in range(i + 1)
            )
            offset = prior_duration_s - prior_overlap_s
            if offset < 0:
                offset = 0

            in_label = "[0:v]" if i == 0 else f"[v{i-1}]"

            out_label = f"[v{i}]"
            if i == n - 2:
                out_label = "[vout]"

            filters.append(
                f"{in_label}[{i+1}:v]xfade=transition={xfade_name}"
                f":duration={dur_i:.3f}:offset={offset:.3f}{out_label}"
            )
            transition_count += 1

        filter_str = ";".join(filters)
        cmd += ["-filter_complex", filter_str]
        cmd += ["-map", "[vout]", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        cmd += [str(output)]

        self._run(cmd)

        # Calculate total duration accounting for overlaps.
        total_overlap_ms = int(dur * 1000) * transition_count
        total_ms = sum(self._duration_for(i) for i in range(n)) - total_overlap_ms

        return TransitionResult(
            output_path=output,
            transition_count=transition_count,
            total_duration_ms=max(total_ms, 0),
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _resolve(self, name: str) -> str:
        """Resolve a transition name to an FFmpeg xfade name or 'hard_cut'."""
        name = (name or "").strip().lower()
        if name in ("hard_cut", "none", ""):
            return "hard_cut"
        return _XFADE_MAP.get(name, "hard_cut")

    def _duration_for(self, index: int) -> int:
        if index < len(self._scene_durations_ms):
            return int(self._scene_durations_ms[index])
        return self._scene_dur_ms

    def _run(self, cmd: list[str]) -> None:
        runner = self._runner or subprocess.run
        proc = runner(cmd, capture_output=True, text=True)
        if getattr(proc, "returncode", 0) != 0:
            raise TransitionError(
                f"ffmpeg failed: {getattr(proc, 'stderr', '')}"
            )
