"""Tests for resume and retry-scene functionality (P9-T02, P9-T03)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import sessionmaker

import app.storage.database as db_module
from app.services.project_manager import ProjectManager, ProjectManagerError
from app.storage.asset_store import AssetStore
from app.storage.repositories import SceneRepo, StateEventRepo


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch) -> Any:
    db_path = tmp_path / "resume_test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    db_module.reset_engine()
    engine = db_module.get_engine(db_url)
    db_module.init_schema(engine)
    yield
    db_module.reset_engine()


@pytest.fixture()
def project_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "projects"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PROJECT_ROOT", str(root))
    return root


def _make_session() -> Any:
    factory = sessionmaker(
        bind=db_module.get_engine(),
        autoflush=True, expire_on_commit=False, future=True,
    )
    return factory()


def _create_project_with_scenes(
    project_root: Path,
    project_id: str = "prj_resume_test",
    scene_count: int = 3,
) -> str:
    """Create a project with fake storyboard and scene rows."""
    store = AssetStore(project_root)
    store.init_project(project_id)

    # Write storyboard.
    scenes = [
        {
            "scene_id": f"scene_{i+1:03d}",
            "order": i + 1,
            "narration_text": f"Scene {i+1}.",
            "script_span": {"start_char": i * 20, "end_char": (i + 1) * 20},
            "visual_summary": f"Visual {i+1}",
            "image_prompt": f"prompt {i+1}",
            "motion_template": "01_subject_slide_headline_pop",
            "estimated_duration_seconds": 5,
        }
        for i in range(scene_count)
    ]
    sb = {
        "summary": "Test",
        "style_anchor": {"visual_language": "editorial", "palette": [], "texture": [],
                         "typography": "sans", "continuity_rules": []},
        "characters": [],
        "locations": [],
        "scenes": scenes,
    }
    manifests = store.subdir(project_id, "manifests")
    (manifests / "storyboard.json").write_text(
        json.dumps(sb, ensure_ascii=False), encoding="utf-8"
    )

    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script text.", project_id=project_id)

        # Create scene rows.
        from app.models import Scene
        for i in range(scene_count):
            scene = Scene(
                project_id=project_id,
                scene_id=f"scene_{i+1:03d}",
                order=i + 1,
                status="PLANNED",
                narration_text=f"Scene {i+1}.",
            )
            session.add(scene)
        session.commit()

    return project_id


# ------------------------------------------------------------------ #
# P9-T02: Resume tests
# ------------------------------------------------------------------ #
class TestResume:
    def test_all_scenes_pending(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=3)
        with _make_session() as session:
            manager = ProjectManager(session, project_root=project_root)
            pending = manager.get_pending_scenes(pid)
            assert len(pending) == 3
            assert all(p["status"] == "PLANNED" for p in pending)

    def test_completed_scenes_not_pending(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=3)
        with _make_session() as session:
            # Mark scene_001 as RENDERED.
            SceneRepo.update_status(session, pid, "scene_001", "RENDERED")
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            pending = manager.get_pending_scenes(pid)
            assert len(pending) == 2
            scene_ids = [p["scene_id"] for p in pending]
            assert "scene_001" not in scene_ids

    def test_failed_retryable_is_pending(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=2)
        with _make_session() as session:
            SceneRepo.update_status(session, pid, "scene_001", "FAILED_RETRYABLE")
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            pending = manager.get_pending_scenes(pid)
            # FAILED_RETRYABLE shows as pending.
            assert len(pending) == 2

    def test_failed_permanent_not_pending(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=2)
        with _make_session() as session:
            SceneRepo.update_status(session, pid, "scene_001", "FAILED_PERMANENT")
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            pending = manager.get_pending_scenes(pid)
            # FAILED_PERMANENT is NOT pending (terminal).
            assert len(pending) == 1

    def test_nonexistent_project_raises(self, project_root: Path):
        with _make_session() as session:
            manager = ProjectManager(session, project_root=project_root)
            with pytest.raises(ProjectManagerError, match="not found"):
                manager.get_pending_scenes("prj_nonexistent")


# ------------------------------------------------------------------ #
# P9-T03: Retry-scene tests
# ------------------------------------------------------------------ #
class TestRetryScene:
    def test_retry_from_image(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=2)
        with _make_session() as session:
            # Mark scene_001 as RENDERED.
            SceneRepo.update_status(session, pid, "scene_001", "RENDERED")
            session.commit()

            manager = ProjectManager(session, project_root=project_root)
            result = manager.retry_scene(pid, "scene_001", from_stage="image")

            assert result["previous_status"] == "RENDERED"
            assert result["new_status"] == "PLANNED"
            assert result["retry_from"] == "image"

            # Check the scene is back to PLANNED.
            scene = SceneRepo.get(session, pid, "scene_001")
            assert scene.status == "PLANNED"

    def test_retry_from_render(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=1)
        with _make_session() as session:
            SceneRepo.update_status(session, pid, "scene_001", "RENDERED")
            session.commit()

            manager = ProjectManager(session, project_root=project_root)
            result = manager.retry_scene(pid, "scene_001", from_stage="render")

            assert result["new_status"] == "MOTION_READY"

    def test_retry_from_layers(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=1)
        with _make_session() as session:
            manager = ProjectManager(session, project_root=project_root)
            result = manager.retry_scene(pid, "scene_001", from_stage="layers")
            assert result["new_status"] == "IMAGE_READY"

    def test_retry_records_state_event(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=1)
        with _make_session() as session:
            manager = ProjectManager(session, project_root=project_root)
            manager.retry_scene(pid, "scene_001", from_stage="image")
            events = StateEventRepo.list(session, pid)
            retry_events = [e for e in events if "retry" in (e.reason or "")]
            assert len(retry_events) >= 1

    def test_retry_invalid_stage_raises(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=1)
        with _make_session() as session:
            manager = ProjectManager(session, project_root=project_root)
            with pytest.raises(ProjectManagerError, match="unknown retry stage"):
                manager.retry_scene(pid, "scene_001", from_stage="banana")

    def test_retry_nonexistent_scene_raises(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=1)
        with _make_session() as session:
            manager = ProjectManager(session, project_root=project_root)
            with pytest.raises(ProjectManagerError, match="scene not found"):
                manager.retry_scene(pid, "scene_999", from_stage="image")

    def test_retry_does_not_affect_other_scenes(self, project_root: Path):
        pid = _create_project_with_scenes(project_root, scene_count=3)
        with _make_session() as session:
            SceneRepo.update_status(session, pid, "scene_001", "RENDERED")
            SceneRepo.update_status(session, pid, "scene_002", "RENDERED")
            SceneRepo.update_status(session, pid, "scene_003", "RENDERED")
            session.commit()

            manager = ProjectManager(session, project_root=project_root)
            manager.retry_scene(pid, "scene_002", from_stage="image")

            s1 = SceneRepo.get(session, pid, "scene_001")
            s2 = SceneRepo.get(session, pid, "scene_002")
            s3 = SceneRepo.get(session, pid, "scene_003")
            assert s1.status == "RENDERED"  # untouched
            assert s2.status == "PLANNED"   # reset
            assert s3.status == "RENDERED"  # untouched
