"""Final composer (Phase 7 / P7-T01).

Concatenates a list of per-scene MP4s (produced by ``LocalSceneRenderer``)
into one final MP4. If an audio track is provided, it is muxed onto the
final video. The pipeline uses FFmpeg's concat demuxer so each scene keeps
its own resolution/fps without re-encoding (the renderer already produced
``yuv420p`` H.264 clips, which are concat-safe).

Acceptance criteria:

- Concat scenes in order; missing scene raises ``FinalComposerError``.
- Optional audio track muxed via ``-c:a aac`` with ``-shortest``.
- Output probed and verified for fps + (when audio given) audio stream.
- Command is an argument list, never ``shell=True``.
- The runner is injectable so unit tests never invoke a real FFmpeg binary.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FinalComposerError(Exception):
    """Raised when the final MP4 cannot be composed or fails verification."""


@dataclass
class FinalProbe:
    """Facts verified about the composed final MP4."""

    fps: float
    width: int
    height: int
    duration_ms: int
    pix_fmt: str
    has_audio: bool

    def verify(
        self,
        *,
        expected_fps: int,
        expected_w: int,
        expected_h: int,
        expected_duration_ms: int,
        expected_audio: bool,
        tolerance_frames: int = 1,
    ) -> None:
        """Assert the probe matches expectations; raise ``FinalComposerError``."""
        if abs(self.fps - expected_fps) > 0.01:
            raise FinalComposerError(
                f"fps {self.fps:.2f} != expected {expected_fps}"
            )
        if self.width != expected_w or self.height != expected_h:
            raise FinalComposerError(
                f"resolution {self.width}x{self.height} != expected {expected_w}x{expected_h}"
            )
        tolerance_ms = int(1000.0 / expected_fps * tolerance_frames)
        if abs(self.duration_ms - expected_duration_ms) > tolerance_ms:
            raise FinalComposerError(
                f"duration {self.duration_ms}ms != expected {expected_duration_ms}ms "
                f"(±{tolerance_ms}ms)"
            )
        if self.pix_fmt != "yuv420p":
            raise FinalComposerError(f"pix_fmt {self.pix_fmt!r} != 'yuv420p'")
        if self.has_audio != expected_audio:
            expected_label = "with audio" if expected_audio else "without audio"
            actual_label = "with audio" if self.has_audio else "without audio"
            raise FinalComposerError(
                f"audio mismatch: expected {expected_label}, got {actual_label}"
            )


class FinalComposer:
    """Compose a list of scene MP4s + optional audio into a final MP4."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self._runner = runner

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def compose(
        self,
        scenes: list[Path],
        audio: Path | None,
        output: Path,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        expected_duration_ms: int | None = None,
        subtitle_path: Path | None = None,
        tolerance_frames: int = 2,
    ) -> tuple[Path, FinalProbe]:
        """Concat scenes + optional audio into ``output``. Returns (path, probe).

        ``scenes`` must be non-empty and each path must exist; otherwise a
        ``FinalComposerError`` is raised before any FFmpeg call.
        """
        scenes = [Path(s) for s in scenes]
        if not scenes:
            raise FinalComposerError("no scenes to compose")
        missing = [s for s in scenes if not s.is_file()]
        if missing:
            raise FinalComposerError(
                f"missing scene MP4(s): {[str(m) for m in missing]}"
            )
        if audio is not None:
            audio = Path(audio)
            if not audio.is_file():
                raise FinalComposerError(f"audio file not found: {audio}")

        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        if expected_duration_ms is None:
            # Derive the authoritative video timeline before building the
            # command so subtitle/container padding cannot extend the output.
            expected_duration_ms = sum(self._scene_duration_ms(s) for s in scenes)

        list_file = self._write_concat_list(scenes, output.parent)
        cmd = self._build_command(
            list_file,
            audio,
            output,
            subtitle_path=subtitle_path,
            expected_duration_ms=expected_duration_ms,
        )

        self._run_ffmpeg(cmd)

        # Probe + verify
        probe_data = self._run_probe(output)
        probe = FinalProbe(**probe_data)
        probe.verify(
            expected_fps=fps,
            expected_w=width,
            expected_h=height,
            expected_duration_ms=expected_duration_ms,
            expected_audio=audio is not None,
            tolerance_frames=tolerance_frames,
        )
        return output, probe

    # ------------------------------------------------------------------ #
    # FFmpeg
    # ------------------------------------------------------------------ #
    def _write_concat_list(self, scenes: list[Path], parent: Path) -> Path:
        """Write a concat demuxer list file (one ``file`` per scene).

        Path escaping follows FFmpeg's concat demuxer protocol: backslashes
        and single quotes inside the path are escaped (``\\`` and ``\\'``).
        """
        list_path = parent / "_concat_list.txt"
        lines = []
        for s in scenes:
            # FFmpeg concat demuxer wants forward slashes and escaped quotes.
            escaped = str(s.resolve()).replace("\\", "/").replace("'", r"\'")
            lines.append(f"file '{escaped}'")
        list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return list_path

    def _build_command(
        self, list_file: Path, audio: Path | None, output: Path,
        *, subtitle_path: Path | None = None,
        expected_duration_ms: int | None = None,
    ) -> list[str]:
        """Build the FFmpeg argument list.

        - Without audio: ``-c:v copy`` (each scene is already H.264/yuv420p).
        - With audio: ``-c:a aac``; the caller provides a track materialized to
          the canonical scene timeline, so the final video remains authoritative.
        - With subtitle: embeds SRT as a soft subtitle stream (``mov_text``).
        """
        cmd = [
            self.ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
        ]
        if audio is not None:
            cmd += ["-i", str(audio)]
        if subtitle_path is not None:
            cmd += ["-i", str(subtitle_path)]
        cmd += [
            "-c:v", "copy",
        ]
        if audio is not None:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        if subtitle_path is not None:
            cmd += ["-c:s", "mov_text"]
        # Explicit maps are required: ffmpeg otherwise may choose the SRT
        # input as the default output stream and silently omit narration.
        cmd += ["-map", "0:v:0"]
        if audio is not None:
            cmd += ["-map", "1:a:0"]
        if subtitle_path is not None:
            subtitle_input = 2 if audio is not None else 1
            cmd += ["-map", f"{subtitle_input}:s:0"]
        if audio is not None:
            cmd += ["-af", "apad"]
        cmd += ["-movflags", "+faststart"]
        if expected_duration_ms is not None:
            cmd += ["-t", f"{expected_duration_ms / 1000.0:.3f}"]
        cmd += [str(output)]
        return cmd

    def _run_ffmpeg(self, cmd: list[str]) -> None:
        runner = self._runner or subprocess.run
        proc = runner(cmd, capture_output=True, text=True)
        if getattr(proc, "returncode", 0) != 0:
            raise FinalComposerError(
                f"ffmpeg failed: {getattr(proc, 'stderr', '')}"
            )

    def _scene_duration_ms(self, path: Path) -> int:
        """Return scene duration in ms (uses the runner if injected; else ffprobe)."""
        runner = self._runner
        if runner is None:
            data = self._run_probe(path)
        else:
            # In tests the runner may be a fake; fall back to a 0 estimate.
            try:
                data = self._run_probe(path)
            except FinalComposerError:
                return 0
        return data.get("duration_ms", 0)

    # ------------------------------------------------------------------ #
    # ffprobe
    # ------------------------------------------------------------------ #
    def _run_probe(self, path: Path) -> dict:
        """Probe the composed MP4: fps/width/height/duration_ms/pix_fmt/has_audio."""
        proc = subprocess.run(
            [
                self.ffprobe_bin, "-v", "error",
                "-show_entries", "stream=r_frame_rate,width,height,pix_fmt",
                "-show_entries", "format=duration",
                "-show_streams",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise FinalComposerError(f"ffprobe rc={proc.returncode}: {proc.stderr}")
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams") or []
        stream = next((item for item in streams if item.get("codec_type") == "video"), {})
        fmt = data.get("format", {})
        # Detect any audio stream across all streams (ffprobe lists them all
        # because we asked for ``-show_streams``).
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        fps = _parse_fps(stream.get("r_frame_rate", ""))
        duration_ms = int(float(fmt.get("duration", 0)) * 1000)
        return {
            "fps": fps,
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration_ms": duration_ms,
            "pix_fmt": stream.get("pix_fmt", ""),
            "has_audio": has_audio,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _parse_fps(r_frame_rate: str) -> float:
    """Parse '30000/1001' or '30/1' into a float fps."""
    if "/" in r_frame_rate:
        num, den = r_frame_rate.split("/")
        try:
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(r_frame_rate)
    except ValueError:
        return 0.0
