from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.local_media_workflow import (
    DurableMediaQueue,
    LocalMediaWorkflow,
    LocalPublishPackager,
    MediaWorkflowError,
)
from app.storage.database import Base
from app.storage.repositories import ProjectRepo


def _session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    ProjectRepo.create(session, project_id="prj_media", title="Media project")
    session.commit()
    return session


def _probe(path: Path) -> dict:
    if path.suffix.lower() in {".wav", ".mp3", ".m4a"}:
        return {
            "kind": "audio",
            "duration_ms": 12000,
            "codec": "aac",
            "sample_rate": 48000,
            "channels": 2,
        }
    return {
        "kind": "video",
        "duration_ms": 15000,
        "codec": "h264",
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "pix_fmt": "yuv420p",
        "has_audio": True,
    }


def test_import_music_and_video_are_project_owned_content_addressed(tmp_path: Path) -> None:
    session = _session(tmp_path)
    music = tmp_path / "source.mp3"
    video = tmp_path / "source.mp4"
    music.write_bytes(b"music-fixture")
    video.write_bytes(b"video-fixture")
    workflow = LocalMediaWorkflow(project_root=tmp_path / "projects", probe=_probe)

    first_music = workflow.import_music("prj_media", music)
    again_music = workflow.import_music("prj_media", music)
    imported_video = workflow.import_video("prj_media", video)

    assert first_music.path == again_music.path
    assert first_music.sha256 == again_music.sha256
    assert first_music.path.is_file()
    assert imported_video.path.is_file()
    assert first_music.path.parent.name == "audio"
    assert imported_video.path.parent.name == "scenes"
    assert first_music.media["kind"] == "audio"
    assert imported_video.media["kind"] == "video"
    assert first_music.source_path == str(music.resolve())
    session.close()


def test_import_rejects_missing_or_wrong_media_kind(tmp_path: Path) -> None:
    workflow = LocalMediaWorkflow(project_root=tmp_path / "projects", probe=_probe)
    with pytest.raises(MediaWorkflowError, match="not found"):
        workflow.import_music("prj_media", tmp_path / "missing.mp3")
    video = tmp_path / "wrong.mp4"
    video.write_bytes(b"video")
    with pytest.raises(MediaWorkflowError, match="expected audio"):
        workflow.import_music("prj_media", video)


def test_durable_queue_survives_restart_and_recovers_running(tmp_path: Path) -> None:
    session = _session(tmp_path)
    queue = DurableMediaQueue(session)
    job = queue.enqueue(
        project_id="prj_media",
        action="import_music",
        payload={"source_path": "C:/fixture/music.mp3"},
    )
    queue.mark_running(job.job_id)
    session.commit()
    session.close()

    session2 = _session_existing(tmp_path)
    recovered = DurableMediaQueue(session2).recover_interrupted()
    rows = DurableMediaQueue(session2).list(project_id="prj_media")

    assert recovered == 1
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].attempts == 1
    assert "recovered after restart" in rows[0].error
    session2.close()


def _session_existing(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return factory()


def test_queue_executes_allowlisted_local_action_and_persists_result(tmp_path: Path) -> None:
    session = _session(tmp_path)
    music = tmp_path / "music.mp3"
    music.write_bytes(b"music-fixture")
    workflow = LocalMediaWorkflow(project_root=tmp_path / "projects", probe=_probe)
    queue = DurableMediaQueue(session)
    job = queue.enqueue(
        project_id="prj_media",
        action="import_music",
        payload={"source_path": str(music)},
    )

    completed = queue.execute_next(workflow=workflow)
    session.commit()

    assert completed is not None
    assert completed.job_id == job.job_id
    assert completed.status == "succeeded"
    result = json.loads(completed.result_json)
    assert Path(result["path"]).is_file()
    assert result["media"]["kind"] == "audio"

    bad = queue.enqueue(project_id="prj_media", action="run_shell", payload={})
    failed = queue.execute_next(workflow=workflow)
    assert failed is not None and failed.job_id == bad.job_id
    assert failed.status == "failed"
    assert "unsupported queue action" in failed.error
    session.close()


def test_publish_local_copies_validated_final_and_writes_manifest(tmp_path: Path) -> None:
    final = tmp_path / "final.mp4"
    final.write_bytes(b"validated-final")
    packager = LocalPublishPackager(project_root=tmp_path / "projects", probe=_probe)

    result = packager.prepare("prj_media", final)

    assert result.video_path.is_file()
    assert result.manifest_path.is_file()
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["project_id"] == "prj_media"
    assert payload["sha256"] == result.sha256
    assert payload["media"]["codec"] == "h264"
    assert payload["network_calls"] == 0
    assert result.video_path.read_bytes() == final.read_bytes()
