"""Project-owned local media import, durable queue, and local publish package."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaQueueJob
from app.storage.asset_store import AssetStore

Probe = Callable[[Path], dict[str, Any]]


class MediaWorkflowError(RuntimeError):
    """Raised when local media cannot be validated or materialized."""


@dataclass(frozen=True)
class ImportedMedia:
    path: Path
    sha256: str
    source_path: str
    media: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(frozen=True)
class PublishPackage:
    video_path: Path
    manifest_path: Path
    sha256: str
    media: dict[str, Any]


class LocalMediaWorkflow:
    """Import validated local audio/video into canonical project storage."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        probe: Probe | None = None,
    ) -> None:
        self.store = AssetStore(project_root)
        self._probe = probe or probe_media

    def import_music(self, project_id: str, source: str | Path) -> ImportedMedia:
        return self._import(project_id, source, expected_kind="audio", subdir="audio")

    def import_video(self, project_id: str, source: str | Path) -> ImportedMedia:
        return self._import(project_id, source, expected_kind="video", subdir="scenes")

    def execute(self, action: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        source = str(payload.get("source_path") or "")
        if action == "import_music":
            return self.import_music(project_id, source).to_dict()
        if action == "import_video":
            return self.import_video(project_id, source).to_dict()
        raise MediaWorkflowError(f"unsupported queue action: {action}")

    def _import(
        self,
        project_id: str,
        source: str | Path,
        *,
        expected_kind: str,
        subdir: str,
    ) -> ImportedMedia:
        path = Path(source).expanduser()
        if not path.is_file():
            raise MediaWorkflowError(f"media not found: {path}")
        media = self._probe(path)
        if str(media.get("kind") or "") != expected_kind:
            raise MediaWorkflowError(
                f"expected {expected_kind}, got {media.get('kind') or 'unknown'}: {path}"
            )
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        ext = path.suffix.lower() or (".m4a" if expected_kind == "audio" else ".mp4")
        target = self.store.subdir(project_id, subdir) / f"imported_{digest[:16]}{ext}"
        if target.is_file():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise MediaWorkflowError(f"canonical media hash mismatch: {target}")
        else:
            self.store.atomic_write_bytes(target, data)
        manifest = {
            "kind": expected_kind,
            "source_path": str(path.resolve()),
            "canonical_path": str(target),
            "sha256": digest,
            "media": media,
        }
        self.store.write_manifest(project_id, f"import_{expected_kind}_{digest[:16]}.json", manifest)
        return ImportedMedia(
            path=target,
            sha256=digest,
            source_path=str(path.resolve()),
            media=media,
        )


class DurableMediaQueue:
    """Sequential durable queue for allowlisted local-only media actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(
        self,
        *,
        project_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> MediaQueueJob:
        row = MediaQueueJob(
            job_id=f"media_{uuid.uuid4().hex}",
            project_id=project_id,
            action=action,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            status="pending",
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list(self, *, project_id: str | None = None) -> list[MediaQueueJob]:
        stmt = select(MediaQueueJob)
        if project_id:
            stmt = stmt.where(MediaQueueJob.project_id == project_id)
        stmt = stmt.order_by(MediaQueueJob.created_at, MediaQueueJob.job_id)
        return list(self.session.scalars(stmt))

    def mark_running(self, job_id: str) -> MediaQueueJob:
        row = self._get(job_id)
        row.status = "running"
        row.attempts += 1
        row.error = ""
        row.updated_at = datetime.now(UTC)
        self.session.flush()
        return row

    def recover_interrupted(self) -> int:
        rows = list(
            self.session.scalars(
                select(MediaQueueJob).where(MediaQueueJob.status == "running")
            )
        )
        for row in rows:
            row.status = "pending"
            row.error = "recovered after restart"
            row.updated_at = datetime.now(UTC)
        self.session.flush()
        return len(rows)

    def execute_next(self, *, workflow: LocalMediaWorkflow) -> MediaQueueJob | None:
        row = self.session.scalars(
            select(MediaQueueJob)
            .where(MediaQueueJob.status == "pending")
            .order_by(MediaQueueJob.created_at, MediaQueueJob.job_id)
            .limit(1)
        ).first()
        if row is None:
            return None
        self.mark_running(row.job_id)
        try:
            payload = json.loads(row.payload_json or "{}")
            result = workflow.execute(row.action, row.project_id, payload)
            row.result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
            row.status = "succeeded"
            row.error = ""
        except Exception as exc:  # noqa: BLE001
            row.status = "failed"
            row.error = f"{type(exc).__name__}: {exc}"
        row.updated_at = datetime.now(UTC)
        self.session.flush()
        return row

    def _get(self, job_id: str) -> MediaQueueJob:
        row = self.session.get(MediaQueueJob, job_id)
        if row is None:
            raise MediaWorkflowError(f"queue job not found: {job_id}")
        return row


class LocalPublishPackager:
    """Prepare a validated, project-owned local delivery folder; never upload."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        probe: Probe | None = None,
    ) -> None:
        self.store = AssetStore(project_root)
        self._probe = probe or probe_media

    def prepare(self, project_id: str, source: str | Path) -> PublishPackage:
        path = Path(source).expanduser()
        if not path.is_file():
            raise MediaWorkflowError(f"final video not found: {path}")
        media = self._probe(path)
        if str(media.get("kind") or "") != "video":
            raise MediaWorkflowError(f"expected video, got {media.get('kind') or 'unknown'}")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        publish_dir = self.store.subdir(project_id, "final") / "publish_local"
        publish_dir.mkdir(parents=True, exist_ok=True)
        target = publish_dir / f"{project_id}_{digest[:12]}.mp4"
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise MediaWorkflowError(f"publish target hash mismatch: {target}")
        if not target.is_file():
            self.store.atomic_write_bytes(target, data)
        payload = {
            "project_id": project_id,
            "source_path": str(path.resolve()),
            "video_path": str(target),
            "sha256": digest,
            "media": media,
            "network_calls": 0,
            "prepared_at": datetime.now(UTC).isoformat(),
        }
        manifest_path = publish_dir / "publish_manifest.json"
        self.store.atomic_write_text(
            manifest_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        return PublishPackage(
            video_path=target,
            manifest_path=manifest_path,
            sha256=digest,
            media=media,
        )


def probe_media(path: str | Path) -> dict[str, Any]:
    """Return normalized FFprobe facts for one local audio/video file."""
    source = Path(path)
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise MediaWorkflowError(f"ffprobe failed: {proc.stderr.strip()}")
    payload = json.loads(proc.stdout or "{}")
    streams = payload.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    duration_ms = int(float((payload.get("format") or {}).get("duration") or 0) * 1000)
    if video is not None:
        return {
            "kind": "video",
            "duration_ms": duration_ms,
            "codec": str(video.get("codec_name") or ""),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "fps": _parse_rate(str(video.get("r_frame_rate") or "")),
            "pix_fmt": str(video.get("pix_fmt") or ""),
            "has_audio": audio is not None,
        }
    if audio is not None:
        return {
            "kind": "audio",
            "duration_ms": duration_ms,
            "codec": str(audio.get("codec_name") or ""),
            "sample_rate": int(audio.get("sample_rate") or 0),
            "channels": int(audio.get("channels") or 0),
        }
    raise MediaWorkflowError(f"no audio/video stream: {source}")


def _parse_rate(value: str) -> float:
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0
