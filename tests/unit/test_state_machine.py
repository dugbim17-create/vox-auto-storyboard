"""Tests for the P1-T04 state machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.state_machine import (
    PROJECT_STATES,
    StateMachine,
    StateMachineError,
    can_retry_scene,
    can_transition,
)
from app.storage import database
from app.storage.repositories import ProjectRepo, SceneRepo, StateEventRepo


@pytest.fixture()
def session(tmp_path: Path):
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/sm.db")
    database.init_schema(engine)
    with database.get_session_factory(engine)() as s:
        yield s
    database.reset_engine()


def test_valid_project_progression(session) -> None:
    ProjectRepo.create(session, project_id="prj_sm", title="SM")
    session.commit()
    sm = StateMachine(session)
    # Project starts at INGESTED; walk forward one state at a time.
    for state in PROJECT_STATES[1:]:
        sm.transition_project("prj_sm", state, reason="progress")
    session.commit()
    from app.storage.repositories import ProjectRepo as Repo

    assert Repo.get(session, "prj_sm").status == "COMPLETED"


def test_invalid_project_transition_rejected(session) -> None:
    ProjectRepo.create(session, project_id="prj_bad", title="B")
    session.commit()
    sm = StateMachine(session)
    with pytest.raises(StateMachineError):
        sm.transition_project("prj_bad", "COMPLETED", reason="jump")


def test_invalid_scene_backward_rejected(session) -> None:
    ProjectRepo.create(session, project_id="prj_s", title="S")
    SceneRepo.add(session, "prj_s", scene_id="scene_1", order=1, status="RENDERED")
    session.commit()
    sm = StateMachine(session)
    with pytest.raises(StateMachineError):
        sm.transition_scene("prj_s", "scene_1", "PLANNED", reason="rewind")


def test_scene_forward_progression_works(session) -> None:
    ProjectRepo.create(session, project_id="prj_f", title="F")
    SceneRepo.add(session, "prj_f", scene_id="scene_2", order=1, status="PLANNED")
    session.commit()
    sm = StateMachine(session)
    sm.transition_scene("prj_f", "scene_2", "VOICE_READY")
    sm.transition_scene("prj_f", "scene_2", "IMAGE_READY")
    session.commit()
    from app.storage.repositories import SceneRepo as SRepo

    assert SRepo.get(session, "prj_f", "scene_2").status == "IMAGE_READY"


def test_error_state_recovery_rules(session) -> None:
    ProjectRepo.create(session, project_id="prj_e", title="E")
    session.commit()
    sm = StateMachine(session)
    # A project may fall to FAILED_RETRYABLE, then reset to INGESTED.
    sm.transition_project("prj_e", "FAILED_RETRYABLE", reason="boom")
    session.commit()
    assert can_transition("FAILED_RETRYABLE", "INGESTED", scene=False)
    sm.transition_project("prj_e", "INGESTED", reason="retry")
    session.commit()
    # Permanent failure is terminal.
    with pytest.raises(StateMachineError):
        sm.transition_project("prj_e", "COMPLETED")


def test_hot_scene_does_not_affect_completed_scene(session) -> None:
    """A failed scene must not reset other scenes that already finished."""
    ProjectRepo.create(session, project_id="prj_multi", title="M")
    SceneRepo.add(session, "prj_multi", scene_id="scene_done", order=1, status="VALIDATED")
    SceneRepo.add(session, "prj_multi", scene_id="scene_broken", order=2, status="PLANNED")
    session.commit()
    sm = StateMachine(session)
    # one scene fails
    sm.transition_scene("prj_multi", "scene_broken", "FAILED_RETRYABLE", reason="oops")
    session.commit()

    from app.storage.repositories import SceneRepo as SRepo

    # the completed scene is untouched
    assert SRepo.get(session, "prj_multi", "scene_done").status == "VALIDATED"
    assert SRepo.get(session, "prj_multi", "scene_broken").status == "FAILED_RETRYABLE"


def test_resume_finds_pending_scenes(session) -> None:
    ProjectRepo.create(session, project_id="prj_res", title="R")
    SceneRepo.add(session, "prj_res", scene_id="s_done", order=1, status="VALIDATED")
    SceneRepo.add(session, "prj_res", scene_id="s_pending", order=2, status="PLANNED")
    SceneRepo.add(session, "prj_res", scene_id="s_partial", order=3, status="IMAGE_READY")
    session.commit()
    pending = [s.scene_id for s in StateMachine.pending_scenes(session, "prj_res")]
    assert "s_done" not in pending
    assert "s_pending" in pending
    assert "s_partial" in pending


def test_state_events_recorded_on_transition(session) -> None:
    ProjectRepo.create(session, project_id="prj_ev2", title="E")
    session.commit()
    sm = StateMachine(session)
    sm.transition_project("prj_ev2", "SCRIPT_ANALYZED", reason="analyzed")
    session.commit()
    events = StateEventRepo.list(session, "prj_ev2")
    assert len(events) == 1
    assert events[0].from_state == "INGESTED"
    assert events[0].to_state == "SCRIPT_ANALYZED"


def test_retry_reset_is_explicit_and_auditable(session) -> None:
    ProjectRepo.create(session, project_id="prj_retry", title="R")
    SceneRepo.add(session, "prj_retry", scene_id="scene_1", order=1, status="RENDERED")
    session.commit()

    assert can_retry_scene("RENDERED", "MOTION_READY")
    sm = StateMachine(session)
    sm.retry_scene("prj_retry", "scene_1", "MOTION_READY", reason="retry render")
    session.commit()

    scene = SceneRepo.get(session, "prj_retry", "scene_1")
    assert scene.status == "MOTION_READY"
    event = StateEventRepo.list(session, "prj_retry")[-1]
    assert event.reason == "retry render"
