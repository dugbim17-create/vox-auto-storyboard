from __future__ import annotations

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
from app.storage.database import Base
from app.storage.repositories import ProjectRepo, SceneRepo


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_scene_prompt_update_persists_and_reads_back() -> None:
    with _session() as session:
        ProjectRepo.create(session, project_id="p1", title="Demo")
        SceneRepo.add(session, "p1", scene_id="s1", order=1, image_prompt="old")
        session.commit()

        updated = SceneRepo.update_image_prompt(session, "p1", "s1", "cinematic portrait")
        session.commit()

        assert updated is not None
        assert SceneRepo.get(session, "p1", "s1").image_prompt == "cinematic portrait"


def test_scene_selected_asset_update_persists() -> None:
    with _session() as session:
        ProjectRepo.create(session, project_id="p1", title="Demo")
        SceneRepo.add(session, "p1", scene_id="s1", order=1)
        session.commit()

        updated = SceneRepo.set_selected_image(session, "p1", "s1", "asset-7")
        session.commit()

        assert updated is not None
        assert SceneRepo.get(session, "p1", "s1").selected_image_asset_id == "asset-7"
