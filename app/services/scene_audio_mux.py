"""Scene audio mux (P8-T02).

Muxes a WAV voice track onto a silent scene MP4, producing a scene-with-audio
MP4.  The result has:

- video stream copied (no re-encode);
- audio encoded as AAC;
- duration validated: audio/video sync within ±1 frame;
- no clipping.

The muxer is also used by the final renderer to combine per-scene voices
with their rendered video clips before concatenation.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AudioMuxError(Exception):
    """Raised when audio mux or verification fails."""


@dataclass
class MuxProbe:
    """Facts verified about a muxed scene MP4."""
    video_duration_ms: int
    audio_duration_ms: int
    has_audio: bool
    audio_codec: str
    fps: float

    def verify(self, *, expected_fps: int = 30, tolerance_frames: int = 1) -> None:
        """Assert audio/video sync within tolerance."""
        if not self.has_audio:
            raise AudioMuxError("muxed file has no audio stream")
        tolerance_ms = int(1000.0 / expected_fps * tolerance_frames)
        drift = abs(self.video_duration_ms - self.audio_duration_ms)
        if drift > tolerance_ms:
            raise AudioMuxError(
                f"audio/video drift {drift}ms exceeds ±{tolerance_ms}ms "
                f"(video={self.video_duration_ms}ms, audio={self.audio_duration_ms}ms)"
            )


class SceneAudioMuxer:
    """Mux a WAV onto a silent scene MP4."""

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

    def mux(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        *,
        fps: int = 30,
        pad_audio: bool = True,
    ) -> tuple[Path, MuxProbe]:
        """Mux ``audio_path`` onto ``video_path`` → ``output_path``.

        When ``pad_audio`` is True and the audio is shorter than video,
        the audio is padded with silence to match video duration (avoids
        FFmpeg cutting the video short with ``-shortest``).

        Returns (output_path, probe).
        """
        video = Path(video_path)
        audio = Path(audio_path)
        output = Path(output_path)

        if not video.is_file():
            raise AudioMuxError(f"video not found: {video}")
        if not audio.is_file():
            raise AudioMuxError(f"audio not found: {audio}")

        output.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(video),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
        ]
        if pad_audio:
            # Keep the video duration authoritative. ``apad`` fills a short
            # narration instead of letting ``-shortest`` truncate the scene.
            cmd += ["-filter_complex", "[1:a]apad[a]", "-map", "0:v:0", "-map", "[a]"]
            video_duration_ms = self._probe_duration_ms(video)
            if video_duration_ms <= 0 and self._runner is not None:
                with suppress(Exception):
                    video_duration_ms = int(self._probe(video, fps=fps).video_duration_ms)
            if video_duration_ms <= 0:
                raise AudioMuxError(f"cannot determine video duration: {video}")
            cmd += ["-t", f"{video_duration_ms / 1000.0:.3f}"]
        else:
            cmd += ["-map", "0:v:0", "-map", "1:a:0", "-shortest"]
        cmd.append(str(output))

        self._run(cmd)

        probe = self._probe(output, fps=fps)
        probe.verify(expected_fps=fps)
        return output, probe

    def _probe_duration_ms(self, path: Path) -> int:
        proc = subprocess.run(
            [
                self.ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return 0
        with suppress(ValueError):
            return int(float(proc.stdout.strip()) * 1000)
        return 0

    def concat_audio(
        self,
        audio_paths: list[str | Path],
        output_path: str | Path,
    ) -> Path:
        """Concatenate multiple WAVs into a single audio file.

        Used to build a combined narration track from per-scene WAVs.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if not audio_paths:
            raise AudioMuxError("at least one audio path is required")
        missing = [str(Path(p)) for p in audio_paths if not Path(p).is_file()]
        if missing:
            raise AudioMuxError(f"audio not found: {', '.join(missing)}")

        if len(audio_paths) == 1:
            # Single file — just copy.
            import shutil
            shutil.copy2(str(audio_paths[0]), str(output))
            return output

        # Write concat list.
        list_file = output.parent / "_audio_concat.txt"
        lines = []
        for p in audio_paths:
            escaped = str(Path(p).resolve()).replace("\\", "/").replace("'", r"\'")
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
        return output

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _run(self, cmd: list[str]) -> None:
        runner = self._runner or subprocess.run
        proc = runner(cmd, capture_output=True, text=True)
        if getattr(proc, "returncode", 0) != 0:
            raise AudioMuxError(
                f"ffmpeg failed: {getattr(proc, 'stderr', '')}"
            )

    def _probe(self, path: Path, *, fps: int = 30) -> MuxProbe:
        """Probe muxed file for audio/video durations."""
        proc = subprocess.run(
            [
                self.ffprobe_bin, "-v", "error",
                "-show_streams",
                "-show_entries", "format=duration",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise AudioMuxError(f"ffprobe rc={proc.returncode}: {proc.stderr}")

        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams", [])

        video_dur_ms = 0
        audio_dur_ms = 0
        has_audio = False
        audio_codec = ""
        detected_fps = 30.0

        for s in streams:
            dur_s = float(s.get("duration", 0) or data.get("format", {}).get("duration", 0))
            dur_ms = int(dur_s * 1000)
            if s.get("codec_type") == "video":
                video_dur_ms = dur_ms
                rfr = s.get("r_frame_rate", "")
                if "/" in rfr:
                    n, d = rfr.split("/")
                    with suppress(ValueError, ZeroDivisionError):
                        detected_fps = float(n) / float(d)
            elif s.get("codec_type") == "audio":
                audio_dur_ms = dur_ms
                has_audio = True
                audio_codec = s.get("codec_name", "")

        probe = MuxProbe(
            video_duration_ms=video_dur_ms,
            audio_duration_ms=audio_dur_ms,
            has_audio=has_audio,
            audio_codec=audio_codec,
            fps=detected_fps,
        )
        return probe
