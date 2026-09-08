"""Project & scene state machine (MASTER_PLAN section 14, P1-T04).

Validates every transition, records state events to the DB, keeps scene state
independent of project state, and supports resume from a persistent store.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Project, Scene
from app.storage.repositories import ProjectRepo, SceneRepo, StateEventRepo

# Project state order (section 14)
PROJECT_STATES = [
    "INGESTED",
    "SCRIPT_ANALYZED",
    "STORYBOARD_DRAFTED",
    "STORYBOARD_VALIDATED",
    "STORYBOARD_APPROVED",
    "VOICE_GENERATING",
    "VOICE_READY",
    "IMAGES_GENERATING",
    "IMAGES_READY",
    "LAYERS_READY",
    "MOTION_PLANNED",
    "SCENES_RENDERING",
    "SCENES_READY",
    "FINAL_RENDERING",
    "VALIDATING",
    "COMPLETED",
]

# Scene state order (section 14)
SCENE_STATES = [
    "PLANNED",
    "VOICE_READY",
    "IMAGE_SUBMITTED",
    "IMAGE_READY",
    "LAYERS_READY",
    "MOTION_READY",
    "RENDERED",
    "VALIDATED",
]

# Error states (section 14) — terminal, not ordered.
ERROR_STATES = {"FAILED_RETRYABLE", "FAILED_PERMANENT", "CANCELLED"}

VALID_STATES = set(PROJECT_STATES) | set(SCENE_STATES) | ERROR_STATES

# Maximum number of forward steps a single transition may advance. Allowing 2
# permits skipping IMAGE_SUBMITTED (VOICE_READY -> IMAGE_READY) without
# permitting absurd jumps like INGESTED -> COMPLETED.
MAX_TRANSITION_ADVANCE = 2

# Finalization may legitimately jump across bookkeeping states after the
# composer has already verified the output artifact. The artifact gate remains
# in ProjectManager; this only permits the persisted lifecycle handoff.
FINALIZATION_STATES = {"FINAL_RENDERING", "VALIDATING", "COMPLETED"}

# Initial state a FAILED_RETRYABLE pipeline restarts from.
PROJECT_RESTART_STATE = "INGESTED"
SCENE_RESTART_STATE = "PLANNED"

# Explicit reset targets used by retry-scene. These are auditable invalidation
# edges, not ordinary forward-progress transitions.
SCENE_RETRY_STATES = {"PLANNED", "IMAGE_READY", "MOTION_READY"}


class StateMachineError(Exception):
    """Raised on invalid transition."""


def can_transition(from_state: str, to_state: str, *, scene: bool = False) -> bool:
    """True when moving from ``from_state`` to ``to_state`` is allowed.

    Forward progress may skip at most a couple of intermediate states (so
    VOICE_READY -> IMAGE_READY works), but a huge jump such as
    INGESTED -> COMPLETED is rejected. Error states are terminal except
    FAILED_RETRYABLE, which can restart the pipeline at its initial state.
    """
    if to_state in ERROR_STATES:
        # Any non-error state may fall into an error state (error->same = no-op).
        return from_state not in ERROR_STATES or from_state == to_state
    if from_state in ERROR_STATES:
        # Only FAILED_RETRYABLE may restart; permanent/cancel are terminal.
        if from_state != "FAILED_RETRYABLE":
            return False
        target_initial = SCENE_RESTART_STATE if scene else PROJECT_RESTART_STATE
        return to_state == target_initial
    if not scene and to_state in FINALIZATION_STATES:
        if to_state == "COMPLETED":
            return from_state == "VALIDATING"
        if from_state in FINALIZATION_STATES:
            ordering = PROJECT_STATES
            try:
                return ordering.index(to_state) > ordering.index(from_state)
            except ValueError:
                return False
        # A local render can start from an INGESTED project when the caller
        # supplies an already-materialized storyboard/scene fixture. Allow the
        # explicit finalization handoff; artifact validation remains upstream.
        return from_state in {
            "INGESTED", "SCRIPT_ANALYZED", "STORYBOARD_DRAFTED",
            "STORYBOARD_VALIDATED", "STORYBOARD_APPROVED", "SCENES_READY",
        }
    ordering = SCENE_STATES if scene else PROJECT_STATES
    try:
        i = ordering.index(from_state)
        j = ordering.index(to_state)
    except ValueError:
        return False
    advance = j - i
    return 1 <= advance <= MAX_TRANSITION_ADVANCE


def can_retry_scene(from_state: str, to_state: str) -> bool:
    """Return whether an explicit scene retry reset is allowed."""
    return (
        from_state in set(SCENE_STATES) | {"FAILED_RETRYABLE"}
        and to_state in SCENE_RETRY_STATES
    )


class StateMachine:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- project ---
    def transition_project(self, project_id: str, to_state: str, reason: str = "") -> Project:
        project = ProjectRepo.get(self.session, project_id)
        if project is None:
            raise StateMachineError(f"project not found: {project_id}")
        from_state = project.status
        if not can_transition(from_state, to_state, scene=False):
            raise StateMachineError(
                f"invalid project transition {from_state} -> {to_state}"
            )
        ProjectRepo.update_status(self.session, project_id, to_state)
        StateEventRepo.record(
            self.session,
            project_id=project_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )
        return project

    # --- scene ---
    def transition_scene(self, project_id: str, scene_id: str, to_state: str, reason: str = "") -> Scene:
        scene = SceneRepo.get(self.session, project_id, scene_id)
        if scene is None:
            raise StateMachineError(f"scene not found: {project_id}/{scene_id}")
        from_state = scene.status
        if not can_transition(from_state, to_state, scene=True):
            raise StateMachineError(
                f"invalid scene transition {from_state} -> {to_state} (scene {scene_id})"
            )
        SceneRepo.update_status(self.session, project_id, scene_id, to_state)
        StateEventRepo.record(
            self.session,
            project_id=project_id,
            scene_id=scene_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )
        return scene

    def retry_scene(self, project_id: str, scene_id: str, to_state: str, reason: str = "") -> Scene:
        """Apply an explicit, auditable scene retry reset."""
        scene = SceneRepo.get(self.session, project_id, scene_id)
        if scene is None:
            raise StateMachineError(f"scene not found: {project_id}/{scene_id}")
        if not can_retry_scene(scene.status, to_state):
            raise StateMachineError(
                f"invalid scene retry transition {scene.status} -> {to_state} (scene {scene_id})"
            )
        from_state = scene.status
        SceneRepo.update_status(self.session, project_id, scene_id, to_state)
        StateEventRepo.record(
            self.session,
            project_id=project_id,
            scene_id=scene_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )
        return scene

    # --- resume ---
    @staticmethod
    def pending_scenes(session: Session, project_id: str) -> list[Scene]:
        """Scenes that still need work (resume support)."""
        scenes = SceneRepo.list(session, project_id)
        return [s for s in scenes if s.status not in ("RENDERED", "VALIDATED") and s.status not in ERROR_STATES - {"FAILED_RETRYABLE"}]
