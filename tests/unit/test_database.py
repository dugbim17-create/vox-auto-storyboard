"""Tests for the P1-T02 database + repository layer (SQLite local)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from app.storage import database
from app.storage.repositories import ProjectRepo, SceneRepo, StateEventRepo, VoiceProfileRepo


@pytest.fixture()
def session(tmp_path: Path):
    """A fresh in-memory SQLite session isolated per test."""
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/test.db")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    with factory() as s:
        yield s
    database.reset_engine()


def test_schema_creates_all_tables(tmp_path: Path) -> None:
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/schema.db")
    database.init_schema(engine)
    from sqlalchemy import inspect

    tables = set(inspect(engine).get_table_names())
    expected = {
        "projects",
        "scenes",
        "assets",
        "provider_jobs",
        "render_attempts",
        "state_events",
        "voice_profiles",
    }
    assert expected <= tables
    database.reset_engine()


def test_default_engine_honors_database_url_environment(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "environment.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    database.reset_engine()

    engine = database.get_engine()
    database.init_schema(engine)

    assert target.is_file()
    assert Path(engine.url.database).resolve() == target.resolve()
    database.reset_engine()


def test_project_crud(session) -> None:
    ProjectRepo.create(session, project_id="prj_test_1", title="Example")
    session.commit()
    fetched = ProjectRepo.get(session, "prj_test_1")
    assert fetched is not None
    assert fetched.title == "Example"
    assert fetched.status == "INGESTED"

    ProjectRepo.update_status(session, "prj_test_1", "STORYBOARD_DRAFTED")
    session.commit()
    assert ProjectRepo.get(session, "prj_test_1").status == "STORYBOARD_DRAFTED"

    listed = ProjectRepo.list(session)
    assert any(p.project_id == "prj_test_1" for p in listed)


def test_scene_crud_and_ordering(session) -> None:
    ProjectRepo.create(session, project_id="prj_s", title="S")
    session.commit()
    SceneRepo.add(session, "prj_s", scene_id="scene_001", order=1, narration_text="A")
    SceneRepo.add(session, "prj_s", scene_id="scene_002", order=2, narration_text="B")
    session.commit()

    scenes = SceneRepo.list(session, "prj_s")
    assert [s.scene_id for s in scenes] == ["scene_001", "scene_002"]

    got = SceneRepo.get(session, "prj_s", "scene_001")
    assert got is not None and got.narration_text == "A"

    SceneRepo.update_status(session, "prj_s", "scene_001", "VOICE_READY")
    session.commit()
    assert SceneRepo.get(session, "prj_s", "scene_001").status == "VOICE_READY"


def test_voice_profile_upsert(session) -> None:
    VoiceProfileRepo.upsert(
        session,
        voice_profile_id="voice_vi_01",
        reference_audio_path="voices/ref.wav",
        language="vi",
        seed=42,
    )
    session.commit()
    profile = VoiceProfileRepo.get(session, "voice_vi_01")
    assert profile is not None
    assert profile.language == "vi"

    # Upsert updates instead of duplicating
    VoiceProfileRepo.upsert(session, voice_profile_id="voice_vi_01", language="en")
    session.commit()
    profiles = VoiceProfileRepo.list(session)
    assert len(profiles) == 1
    assert VoiceProfileRepo.get(session, "voice_vi_01").language == "en"


def test_state_event_records_transition(session) -> None:
    ProjectRepo.create(session, project_id="prj_ev", title="E")
    session.commit()
    StateEventRepo.record(
        session,
        project_id="prj_ev",
        from_state="INGESTED",
        to_state="SCRIPT_ANALYZED",
        reason="probe",
    )
    session.commit()
    events = StateEventRepo.list(session, "prj_ev")
    assert len(events) == 1
    assert events[0].to_state == "SCRIPT_ANALYZED"


def test_foreign_key_constraint(session) -> None:
    """A scene without its project violates FK — proves referential integrity."""
    SceneRepo.add(session, project_id="prj_missing", scene_id="scene_x", order=1)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_transaction_rollback(session) -> None:
    """Failed commit rolls back atomically; nothing persists."""
    ProjectRepo.create(session, project_id="prj_ok", title="OK")
    session.commit()

    # Introduce a violating insert inside a transaction
    SceneRepo.add(session, project_id="prj_ok", scene_id="scene_1", order=1)
    SceneRepo.add(session, project_id="prj_ghost", scene_id="scene_bad", order=1)  # FK violation
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # After rollback: good scene insert is also undone, project intact
    scenes = SceneRepo.list(session, "prj_ok")
    assert scenes == []
    assert ProjectRepo.get(session, "prj_ok") is not None
