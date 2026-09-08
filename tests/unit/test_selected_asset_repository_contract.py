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
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session):
    ProjectRepo.create(session, project_id="p1", title="Demo")
    SceneRepo.add(session, "p1", scene_id="s1", order=1)
    asset = AssetRepo.add(
        session,
        "p1",
        "s1",
        asset_id="s1_composite_v001",
        role="composite",
        path="image.jpg",
        selected=True,
    )
    SceneRepo.set_selected_image(session, "p1", "s1", asset.asset_id)
    session.commit()
    return asset


def test_selected_asset_resolves_by_logical_asset_id() -> None:
    with _session() as session:
        asset = _seed(session)
        selected = AssetRepo.get_selected_for_scene(session, "p1", "s1")
        assert selected is not None
        assert selected.id == asset.id
        assert selected.asset_id == "s1_composite_v001"


def test_mark_scene_stale_clears_selected_reference() -> None:
    with _session() as session:
        _seed(session)
        AssetRepo.mark_scene_stale(session, "p1", "s1")
        session.commit()
        assert SceneRepo.get(session, "p1", "s1").selected_image_asset_id is None
        assert AssetRepo.get_selected_for_scene(session, "p1", "s1") is None
