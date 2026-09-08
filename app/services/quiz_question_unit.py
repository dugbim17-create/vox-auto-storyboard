"""Render one approved quiz question using measured local audio artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.quiz_renderer import QuizOfflineRenderer, QuizRenderState


class QuizQuestionUnitError(RuntimeError):
    """Raised when a deterministic question unit cannot be compiled or rendered."""


@dataclass(frozen=True)
class QuizQuestionUnitTiming:
    fps: int
    frame_duration_ms: int
    question_in_ms: int
    question_voice_start_ms: int
    question_voice_duration_ms: int
    countdown_start_ms: int
    countdown_duration_ms: int
    time_up_start_ms: int
    time_up_ms: int
    answer_reveal_start_ms: int
    answer_reveal_ms: int
    answer_voice_start_ms: int
    answer_voice_duration_ms: int
    answer_hold_ms: int
    question_out_ms: int
    duration_ms: int


@dataclass(frozen=True)
class QuizQuestionUnitResult:
    output_path: Path
    manifest_path: Path
    sha256: str
    duration_ms: int


class QuizQuestionUnitRenderer:
    def __init__(
        self,
        *,
        fps: int = 30,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        runner: Callable[..., Any] | None = None,
    ) -> None:
        if fps < 1:
            raise ValueError("fps must be positive")
        self.fps = fps
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self._runner = runner

    def compile_timing(
        self,
        *,
        question_wav: str | Path,
        answer_wav: str | Path,
        countdown_seconds: int,
        question_in_ms: int = 400,
        time_up_ms: int = 250,
        answer_reveal_ms: int = 80,
        answer_tail_ms: int = 500,
        question_out_ms: int = 350,
    ) -> QuizQuestionUnitTiming:
        if not isinstance(countdown_seconds, int) or countdown_seconds <= 0:
            raise QuizQuestionUnitError("countdown_seconds must be a positive integer")
        question_duration = self._probe_wav(question_wav, "question WAV")
        answer_duration = self._probe_wav(answer_wav, "answer WAV")
        countdown_start = question_in_ms + question_duration
        countdown_duration = countdown_seconds * 1000
        time_up_start = countdown_start + countdown_duration
        reveal_start = time_up_start + time_up_ms
        answer_voice_start = reveal_start + answer_reveal_ms
        answer_hold = max(answer_duration + answer_tail_ms, 1000)
        raw_duration = answer_voice_start + answer_hold + question_out_ms
        frame_duration = round(1000 / self.fps)
        duration = math.ceil(raw_duration / frame_duration) * frame_duration
        return QuizQuestionUnitTiming(
            fps=self.fps,
            frame_duration_ms=frame_duration,
            question_in_ms=question_in_ms,
            question_voice_start_ms=question_in_ms,
            question_voice_duration_ms=question_duration,
            countdown_start_ms=countdown_start,
            countdown_duration_ms=countdown_duration,
            time_up_start_ms=time_up_start,
            time_up_ms=time_up_ms,
            answer_reveal_start_ms=reveal_start,
            answer_reveal_ms=answer_reveal_ms,
            answer_voice_start_ms=answer_voice_start,
            answer_voice_duration_ms=answer_duration,
            answer_hold_ms=answer_hold,
            question_out_ms=question_out_ms,
            duration_ms=duration,
        )

    def render(
        self,
        *,
        quiz_document: dict[str, Any],
        question_id: str,
        question_wav: str | Path,
        answer_wav: str | Path,
        output_dir: str | Path,
        countdown_seconds: int,
        answer_sting_path: str | Path | None = None,
        bgm_path: str | Path | None = None,
        provider_calls: int = 0,
        tts_calls: int = 0,
    ) -> QuizQuestionUnitResult:
        if provider_calls < 0 or tts_calls < 0:
            raise QuizQuestionUnitError("provider/TTS call counts cannot be negative")
        question = next(
            (item for item in quiz_document.get("questions", []) if item.get("question_id") == question_id),
            None,
        )
        if question is None:
            raise QuizQuestionUnitError(f"question not found: {question_id}")
        output_dir = Path(output_dir)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        timing = self.compile_timing(
            question_wav=question_wav,
            answer_wav=answer_wav,
            countdown_seconds=countdown_seconds,
        )
        frame_renderer = QuizOfflineRenderer(width=1280, height=720, fps=self.fps)
        state_specs = [
            ("QUESTION", 0.0, timing.countdown_start_ms),
            ("COUNTDOWN", 0.5, timing.countdown_duration_ms),
            ("TIME_UP", 0.0, timing.time_up_ms),
            (
                "REVEAL",
                1.0,
                timing.duration_ms - timing.answer_reveal_start_ms,
            ),
        ]
        concat_lines = ["ffconcat version 1.0"]
        frame_paths: list[Path] = []
        for kind, progress, duration_ms in state_specs:
            frame = frame_renderer.render_frame(
                quiz_document, QuizRenderState(kind, question, progress)
            )
            path = frames_dir / f"{question_id}_{kind.lower()}.png"
            frame.save(path)
            frame_paths.append(path)
            concat_lines += [
                f"file '{path.resolve().as_posix()}'",
                f"duration {duration_ms / 1000:.6f}",
            ]
        concat_lines.append(f"file '{frame_paths[-1].resolve().as_posix()}'")
        concat_path = output_dir / "frames.ffconcat"
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        audio_path = self.build_audio_track(
            question_wav=question_wav,
            answer_wav=answer_wav,
            timing=timing,
            output_path=output_dir / "question-unit-audio.m4a",
            answer_sting_path=answer_sting_path,
            bgm_path=bgm_path,
        )
        output_path = output_dir / f"{question_id}-unit.mp4"
        partial = output_dir / f"{question_id}-unit.partial.mp4"
        self._encode_unit(concat_path, audio_path, partial, timing)
        probe = self._probe_media(partial)
        self._verify_media(probe, timing)
        partial.replace(output_path)
        sha256 = self._sha256(output_path)
        manifest = {
            "schema_version": "quiz_question_unit_v1",
            "question_id": question_id,
            "output": str(output_path.resolve()),
            "sha256": sha256,
            "bytes": output_path.stat().st_size,
            "duration_ms": probe["duration_ms"],
            "timing": asdict(timing),
            "video": probe["video"],
            "audio": probe["audio"],
            "provider_calls": provider_calls,
            "tts_calls": tts_calls,
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return QuizQuestionUnitResult(output_path, manifest_path, sha256, probe["duration_ms"])

    def build_audio_track(
        self,
        *,
        question_wav: str | Path,
        answer_wav: str | Path,
        timing: QuizQuestionUnitTiming,
        output_path: str | Path,
        answer_sting_path: str | Path | None = None,
        bgm_path: str | Path | None = None,
    ) -> Path:
        question = Path(question_wav)
        answer = Path(answer_wav)
        if not question.is_file() or not answer.is_file():
            raise QuizQuestionUnitError("question and answer WAV files are required")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [self.ffmpeg_bin, "-y", "-i", str(question), "-i", str(answer)]
        input_index = 2
        sting_index: int | None = None
        if answer_sting_path is not None:
            sting = Path(answer_sting_path)
            if not sting.is_file():
                raise QuizQuestionUnitError(f"answer sting missing: {sting}")
            cmd += ["-i", str(sting)]
            sting_index = input_index
            input_index += 1
        bgm_index: int | None = None
        if bgm_path is not None:
            bgm = Path(bgm_path)
            if not bgm.is_file():
                raise QuizQuestionUnitError(f"BGM missing: {bgm}")
            cmd += ["-i", str(bgm)]
            bgm_index = input_index
        filters = [
            f"[0:a]adelay={timing.question_voice_start_ms}|{timing.question_voice_start_ms},aresample=48000[q]",
            f"[1:a]adelay={timing.answer_voice_start_ms}|{timing.answer_voice_start_ms},aresample=48000[a]",
            "[q][a]amix=inputs=2:duration=longest:normalize=0[voice]",
        ]
        if sting_index is None:
            filters.append(
                f"sine=frequency=880:duration=0.18:sample_rate=48000,volume=-10dB,"
                f"adelay={timing.answer_reveal_start_ms}|{timing.answer_reveal_start_ms}[sting]"
            )
        else:
            filters.append(
                f"[{sting_index}:a]atrim=0:0.35,volume=-10dB,aresample=48000,"
                f"adelay={timing.answer_reveal_start_ms}|{timing.answer_reveal_start_ms}[sting]"
            )
        if bgm_index is not None:
            duration_s = timing.duration_ms / 1000
            filters.extend(
                [
                    f"[{bgm_index}:a]aloop=loop=-1:size=2e+09,atrim=0:{duration_s:.3f},"
                    "volume=-20dB,aresample=48000[bgm]",
                    "[voice]asplit=2[voice_mix][voice_sc]",
                    "[bgm][voice_sc]sidechaincompress=threshold=0.02:ratio=8:attack=50:release=300[ducked]",
                    "[voice_mix][sting][ducked]amix=inputs=3:duration=longest:normalize=0,"
                    "aformat=sample_rates=48000:channel_layouts=stereo[out]",
                ]
            )
        else:
            filters.append(
                "[voice][sting]amix=inputs=2:duration=longest:normalize=0,"
                "aformat=sample_rates=48000:channel_layouts=stereo[out]"
            )
        cmd += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{timing.duration_ms / 1000:.3f}",
            str(output),
        ]
        runner = self._runner or subprocess.run
        proc = runner(cmd, capture_output=True, text=True, timeout=120)
        if getattr(proc, "returncode", 0) != 0 or not output.is_file():
            raise QuizQuestionUnitError(
                f"question audio graph failed: {getattr(proc, 'stderr', '')[-2000:]}"
            )
        return output

    def _encode_unit(
        self,
        concat_path: Path,
        audio_path: Path,
        output_path: Path,
        timing: QuizQuestionUnitTiming,
    ) -> None:
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            f"fps={self.fps},format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-c:a",
            "copy",
            "-t",
            f"{timing.duration_ms / 1000:.3f}",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not output_path.is_file():
            raise QuizQuestionUnitError(f"question unit encode failed: {proc.stderr[-3000:]}")

    def _probe_media(self, path: Path) -> dict[str, Any]:
        proc = subprocess.run(
            [
                self.ffprobe_bin,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise QuizQuestionUnitError(f"question unit ffprobe failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        video = next(item for item in data["streams"] if item.get("codec_type") == "video")
        audio = next(item for item in data["streams"] if item.get("codec_type") == "audio")
        rate_n, rate_d = str(video.get("r_frame_rate", "0/1")).split("/")
        return {
            "duration_ms": round(float(data["format"]["duration"]) * 1000),
            "video": {
                "codec": video.get("codec_name"),
                "width": int(video.get("width", 0)),
                "height": int(video.get("height", 0)),
                "fps": float(rate_n) / float(rate_d),
                "pix_fmt": video.get("pix_fmt"),
            },
            "audio": {
                "codec": audio.get("codec_name"),
                "sample_rate": int(audio.get("sample_rate", 0)),
                "channels": int(audio.get("channels", 0)),
            },
        }

    def _verify_media(
        self, probe: dict[str, Any], timing: QuizQuestionUnitTiming
    ) -> None:
        video = probe["video"]
        audio = probe["audio"]
        if (video["width"], video["height"]) != (1280, 720):
            raise QuizQuestionUnitError("question unit resolution mismatch")
        if abs(video["fps"] - self.fps) > 0.01 or video["pix_fmt"] != "yuv420p":
            raise QuizQuestionUnitError("question unit video contract mismatch")
        if audio != {"codec": "aac", "sample_rate": 48000, "channels": 2}:
            raise QuizQuestionUnitError("question unit audio contract mismatch")
        if abs(probe["duration_ms"] - timing.duration_ms) > timing.frame_duration_ms + 1:
            raise QuizQuestionUnitError("question unit duration drift")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _probe_wav(self, path: str | Path, label: str) -> int:
        candidate = Path(path)
        if not candidate.is_file():
            raise QuizQuestionUnitError(f"{label} missing: {candidate}")
        proc = subprocess.run(
            [
                self.ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(candidate),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        try:
            duration_ms = round(float(proc.stdout.strip()) * 1000)
        except ValueError:
            duration_ms = 0
        if proc.returncode != 0 or duration_ms <= 0:
            raise QuizQuestionUnitError(f"{label} has invalid duration: {candidate}")
        return duration_ms
