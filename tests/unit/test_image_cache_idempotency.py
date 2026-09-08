from __future__ import annotations

from pathlib import Path

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
from app.services.image_generation import ImageGenerationService, RoleImageResult
from app.storage.database import Base
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo


def test_persist_same_cached_asset_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    image = tmp_path / "image.jpg"
    image.write_bytes(b"image")
    result = RoleImageResult(
        project_id="p1",
        scene_id="s1",
        role="composite",
        path=str(image),
        provider="cliproxy_image",
        prompt_hash="prompt",
        sha256="abc",
        width=8,
        height=8,
        version=1,
        cached=True,
    )
    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1")
        SceneRepo.add(session, "p1", scene_id="s1", order=1)
        service = ImageGenerationService(object(), project_root=tmp_path)
        service._persist_asset(session, result)  # noqa: SLF001
        service._persist_asset(session, result)  # noqa: SLF001
        session.commit()
        assets = AssetRepo.list(session, "p1", "s1")
    assert len(assets) == 1
    assert assets[0].asset_id == "s1_composite_v001"
