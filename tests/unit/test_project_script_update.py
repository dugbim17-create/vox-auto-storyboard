from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (  # noqa: F401
    Asset,
    Project,
    ProviderJob,
    RenderAttempt,
    Scene,
    StateEvent,
    VoiceProfile,
)
from app.services.project_manager import ProjectManager, ProjectManagerError, sha256_text
from app.storage.database import Base


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_save_script_updates_database_and_project_input_file(tmp_path: Path) -> None:
    with _session() as session:
        manager = ProjectManager(session, project_root=tmp_path)
        project, _ = manager.create_project("old script", title="Demo")

        updated = manager.save_script(project["project_id"], "new durable script")

        assert updated["script_text"] == "new durable script"
        assert updated["script_hash"] == sha256_text("new durable script")
        script_file = tmp_path / project["project_id"] / "input" / "script.txt"
        assert script_file.read_text(encoding="utf-8") == "new durable script"
        assert manager.get_project(project["project_id"])["script_text"] == "new durable script"


def test_save_script_rejects_empty_text(tmp_path: Path) -> None:
    with _session() as session:
        manager = ProjectManager(session, project_root=tmp_path)
        project, _ = manager.create_project("original")
        with pytest.raises(ProjectManagerError, match="script is empty"):
            manager.save_script(project["project_id"], "  ")
