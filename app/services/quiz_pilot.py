"""Durable five-question quiz pilot ledger and composer."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.quiz_renderer import QuizOfflineRenderer, QuizRenderState


class QuizPilotError(RuntimeError):
    """Raised when pilot resume/composition cannot continue safely."""


@dataclass(frozen=True)
class QuizPilotComposeResult:
    output_path: Path
    manifest_path: Path
    sha256: str
    duration_ms: int


class QuizPilotLedger:
    def __init__(self, path: Path, document: dict[str, Any]) -> None:
        self.path = path
        self.document = document

    @classmethod
    def create(
        cls,
        path: str | Path,
        question_ids: list[str],
        *,
        content_fingerprint: str | None = None,
    ) -> QuizPilotLedger:
        path = Path(path)
        if path.exists():
            return cls.load(
                path, expected_content_fingerprint=content_fingerprint
            )
        item_ids = ["intro", *question_ids, "outro"]
        document = {
            "schema_version": "quiz_pilot_ledger_v1",
            "question_ids": list(question_ids),
            "content_fingerprint": content_fingerprint,
            "items": [
                {
                    "item_id": item_id,
                    "status": "planned",
                    "render_calls": 0,
                    "dispatch_allowed": True,
                    "retry_count": 0,
                    "path": None,
                    "bytes": None,
                    "sha256": None,
                    "probe": None,
                    "error": None,
                }
                for item_id in item_ids
            ],
        }
        ledger = cls(path, document)
        ledger._save()
        return ledger

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        expected_content_fingerprint: str | None = None,
    ) -> QuizPilotLedger:
        path = Path(path)
        if not path.is_file():
            raise QuizPilotError(f"pilot ledger not found: {path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        actual = document.get("content_fingerprint")
        if expected_content_fingerprint is not None and actual != expected_content_fingerprint:
            raise QuizPilotError("pilot ledger content fingerprint mismatch")
        return cls(path, document)

    def item(self, item_id: str) -> dict[str, Any]:
        item = next(
            (row for row in self.document["items"] if row["item_id"] == item_id),
            None,
        )
        if item is None:
            raise QuizPilotError(f"unknown pilot item: {item_id}")
        return item

    def checkpoint_render(self, item_id: str) -> None:
        item = self.item(item_id)
        if not item.get("dispatch_allowed", item["render_calls"] == 0):
            raise QuizPilotError(f"pilot item already dispatched: {item_id}")
        item["render_calls"] += 1
        item["dispatch_allowed"] = False
        item["status"] = "rendering"
        self._save()

    def mark_validated(
        self, item_id: str, path: str | Path, probe: dict[str, Any]
    ) -> None:
        item = self.item(item_id)
        artifact = Path(path).resolve()
        if item["render_calls"] < 1 or item.get("dispatch_allowed", False):
            raise QuizPilotError(f"pilot item was not checkpointed: {item_id}")
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise QuizPilotError(f"pilot artifact missing: {artifact}")
        self._validate_probe(probe)
        item.update(
            {
                "status": "validated",
                "path": str(artifact),
                "bytes": artifact.stat().st_size,
                "sha256": self._sha256(artifact),
                "probe": probe,
                "error": None,
            }
        )
        self._save()

    def adopt_validated(
        self, item_id: str, path: str | Path, probe: dict[str, Any]
    ) -> None:
        item = self.item(item_id)
        if item["render_calls"] != 0:
            raise QuizPilotError(f"cannot adopt dispatched pilot item: {item_id}")
        artifact = Path(path).resolve()
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise QuizPilotError(f"pilot artifact missing: {artifact}")
        self._validate_probe(probe)
        item.update(
            {
                "status": "validated",
                "path": str(artifact),
                "bytes": artifact.stat().st_size,
                "sha256": self._sha256(artifact),
                "probe": probe,
                "error": None,
                "reused": True,
            }
        )
        self._save()

    def mark_unknown(self, item_id: str, error: str) -> None:
        item = self.item(item_id)
        item["status"] = "render_unknown"
        item["error"] = str(error)
        self._save()

    def authorize_retry(self, item_id: str, *, reason: str) -> None:
        item = self.item(item_id)
        if item["render_calls"] <= 0:
            raise QuizPilotError(f"cannot retry undispatched pilot item: {item_id}")
        item.update(
            {
                "status": "planned",
                "dispatch_allowed": True,
                "retry_count": int(item.get("retry_count", 0)) + 1,
                "error": str(reason),
                "path": None,
                "bytes": None,
                "sha256": None,
                "probe": None,
            }
        )
        self._save()

    def pending_items(self) -> list[str]:
        pending: list[str] = []
        for item in self.document["items"]:
            if item["status"] == "validated" and not self._artifact_matches(item):
                item["status"] = "artifact_invalid"
                item["error"] = "artifact hash/size mismatch"
            if item["status"] != "validated":
                pending.append(item["item_id"])
        self._save()
        return pending

    def _artifact_matches(self, item: dict[str, Any]) -> bool:
        path = Path(str(item.get("path") or ""))
        return (
            path.is_file()
            and path.stat().st_size == item.get("bytes")
            and self._sha256(path) == item.get("sha256")
        )

    @staticmethod
    def _validate_probe(probe: dict[str, Any]) -> None:
        video = probe.get("video") or {}
        audio = probe.get("audio") or {}
        if (
            video.get("codec") != "h264"
            or (video.get("width"), video.get("height")) != (1280, 720)
            or abs(float(video.get("fps", 0)) - 30) > 0.01
            or video.get("pix_fmt") != "yuv420p"
        ):
            raise QuizPilotError("pilot video probe contract mismatch")
        if audio != {"codec": "aac", "sample_rate": 48000, "channels": 2}:
            raise QuizPilotError("pilot audio probe contract mismatch")
        if int(probe.get("duration_ms", 0)) <= 0:
            raise QuizPilotError("pilot duration must be positive")

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.document, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class QuizPilotComposer:
    def __init__(
        self, *, fps: int = 30, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"
    ) -> None:
        self.fps = fps
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def render_title_clip(
        self,
        *,
        output_path: str | Path,
        title: str,
        subtitle: str,
        duration_ms: int,
        intro: bool,
    ) -> tuple[Path, dict[str, Any]]:
        if duration_ms <= 0:
            raise QuizPilotError("title clip duration must be positive")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        frame_path = output.with_suffix(".png")
        renderer = QuizOfflineRenderer(width=1280, height=720, fps=self.fps)
        state = QuizRenderState("INTRO" if intro else "OUTRO")
        document = {
            "schema_version": "quiz_project_v1",
            "title": title,
            "language": "vi",
            "question_count": 30,
            "seconds_per_question": 10,
            "theme_id": "quiz_independent_v1",
            "questions": [self._placeholder_question(index) for index in range(1, 31)],
            "intro": {"title": title, "subtitle": subtitle},
            "outro": {"title": title, "cta": subtitle},
        }
        renderer.render_frame(document, state).save(frame_path)
        partial = output.with_name(f"{output.stem}.partial{output.suffix}")
        cmd = [
            self.ffmpeg_bin, "-y",
            "-loop", "1", "-i", str(frame_path),
            "-f", "lavfi", "-i", "sine=frequency=164:sample_rate=48000",
            "-t", f"{duration_ms / 1000:.3f}",
            "-vf", f"fps={self.fps},format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "48000",
            "-movflags", "+faststart", str(partial),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not partial.is_file():
            raise QuizPilotError(f"title clip render failed: {proc.stderr[-2000:]}")
        probe = self.probe_media(partial)
        if abs(probe["duration_ms"] - duration_ms) > round(1000 / self.fps) + 1:
            raise QuizPilotError("title clip duration mismatch")
        partial.replace(output)
        return output, probe

    @staticmethod
    def _placeholder_question(index: int) -> dict[str, Any]:
        return {
            "question_id": f"placeholder_{index:03d}", "order": index,
            "type": "multiple_choice_text", "question": f"Placeholder {index}?",
            "choices": [{"id": "A", "text": "A"}, {"id": "B", "text": "B"}, {"id": "C", "text": "C"}],
            "correct_choice_id": "A", "answer_text": "A",
            "question_voice": f"Placeholder {index}?", "answer_voice": "A",
            "countdown_seconds": 10, "template_id": "text_mcq",
            "visual_asset_id": "none", "fact_sources": ["https://example.test"],
        }

    def compose_embedded_clips(
        self,
        clips: list[tuple[str, Path]],
        output_path: str | Path,
        *,
        manifest_path: str | Path,
        expected_question_ids: list[str] | None = None,
    ) -> QuizPilotComposeResult:
        question_ids = expected_question_ids or [
            "q001", "q002", "q003", "q004", "q005"
        ]
        if not question_ids or len(question_ids) != len(set(question_ids)):
            raise QuizPilotError("expected question ids must be unique and non-empty")
        expected_ids = ["intro", *question_ids, "outro"]
        if [item_id for item_id, _ in clips] != expected_ids:
            raise QuizPilotError("pilot clip order does not match expected questions")
        missing = [str(path) for _, path in clips if not Path(path).is_file()]
        if missing:
            raise QuizPilotError(f"pilot clips missing: {missing}")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        concat_path = output.parent / "pilot.ffconcat"
        concat_path.write_text(
            "ffconcat version 1.0\n"
            + "\n".join(f"file '{Path(path).resolve().as_posix()}'" for _, path in clips)
            + "\n",
            encoding="utf-8",
        )
        partial = output.with_name(f"{output.stem}.partial{output.suffix}")
        cmd = [
            self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_path), "-c", "copy", "-movflags", "+faststart", str(partial),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not partial.is_file():
            raise QuizPilotError(f"pilot concat failed: {proc.stderr[-3000:]}")
        probe = self.probe_media(partial)
        self._validate_probe_contract(probe)
        partial.replace(output)
        records = []
        for item_id, path in clips:
            candidate = Path(path).resolve()
            records.append(
                {
                    "item_id": item_id,
                    "path": str(candidate),
                    "bytes": candidate.stat().st_size,
                    "sha256": QuizPilotLedger._sha256(candidate),
                    "probe": self.probe_media(candidate),
                }
            )
        manifest = {
            "schema_version": "quiz_pilot_manifest_v1",
            "items": records,
            "question_ids": question_ids,
            "output": str(output.resolve()),
            "bytes": output.stat().st_size,
            "sha256": QuizPilotLedger._sha256(output),
            "duration_ms": probe["duration_ms"],
            "video": probe["video"],
            "audio": probe["audio"],
        }
        manifest_file = Path(manifest_path)
        manifest_file.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return QuizPilotComposeResult(
            output, manifest_file, manifest["sha256"], probe["duration_ms"]
        )

    @staticmethod
    def _validate_probe_contract(probe: dict[str, Any]) -> None:
        video = probe.get("video") or {}
        audio = probe.get("audio") or {}
        if video != {
            "codec": "h264", "width": 1280, "height": 720,
            "fps": 30.0, "pix_fmt": "yuv420p",
        }:
            raise QuizPilotError("pilot final video contract mismatch")
        if audio != {"codec": "aac", "sample_rate": 48000, "channels": 2}:
            raise QuizPilotError("pilot final audio contract mismatch")

    def probe_media(self, path: str | Path) -> dict[str, Any]:
        proc = subprocess.run(
            [self.ffprobe_bin, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise QuizPilotError(f"pilot ffprobe failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        video = next(item for item in data["streams"] if item.get("codec_type") == "video")
        audio = next(item for item in data["streams"] if item.get("codec_type") == "audio")
        num, den = str(video.get("r_frame_rate", "0/1")).split("/")
        return {
            "video": {"codec": video.get("codec_name"), "width": int(video.get("width", 0)), "height": int(video.get("height", 0)), "fps": float(num) / float(den), "pix_fmt": video.get("pix_fmt")},
            "audio": {"codec": audio.get("codec_name"), "sample_rate": int(audio.get("sample_rate", 0)), "channels": int(audio.get("channels", 0))},
            "duration_ms": round(float(data["format"]["duration"]) * 1000),
        }
