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
from app.services.image_generation import ImageGenerationService, role_cache_key
from app.storage.database import Base
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo


def test_cache_identity_is_full_sha256_and_namespaces_scene_role_style() -> None:
    common = {
        "prompt": "same prompt",
        "seed": 7,
        "aspect": "16:9",
        "provider": "cliproxy_image",
        "model": "gpt-image-2",
        "visual_style_hash": "style-A",
    }
    first = role_cache_key(
        **common,
        project_id="project-A",
        scene_id="scene_001",
        role="composite",
    )
    assert len(first) == 64
    assert first != role_cache_key(
        **common,
        project_id="project-B",
        scene_id="scene_001",
        role="composite",
    )
    assert first != role_cache_key(
        **common,
        project_id="project-A",
        scene_id="scene_002",
        role="composite",
    )
    assert first != role_cache_key(
        **common,
        project_id="project-A",
        scene_id="scene_001",
        role="background",
    )
    assert first != role_cache_key(
        **{**common, "visual_style_hash": "style-B"},
        project_id="project-A",
        scene_id="scene_001",
        role="composite",
    )


def test_selection_prefers_current_style_even_when_older_version(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1")
        SceneRepo.add(session, "p1", scene_id="s1", order=1)
        style_a = AssetRepo.add(
            session,
            "p1",
            "s1",
            asset_id="s1_composite_v001",
            role="composite",
            path="a.jpg",
            version=1,
            visual_style_hash="style-A",
            cache_identity="identity-A",
            selected=False,
        )
        style_b = AssetRepo.add(
            session,
            "p1",
            "s1",
            asset_id="s1_composite_v002",
            role="composite",
            path="b.jpg",
            version=2,
            visual_style_hash="style-B",
            cache_identity="identity-B",
            selected=True,
        )
        SceneRepo.set_selected_image(session, "p1", "s1", style_b.asset_id)
        session.commit()

        selected_id = ImageGenerationService(object())._select_candidate(  # noqa: SLF001
            session,
            "p1",
            "s1",
            visual_style_hash="style-A",
        )
        session.commit()

        assert selected_id == style_a.asset_id
        assert style_a.selected is True
        assert style_b.selected is False
        assert SceneRepo.get(session, "p1", "s1").selected_image_asset_id == style_a.asset_id


def test_fallback_provider_model_is_part_of_provenance_and_identity(tmp_path: Path) -> None:
    class Provider:
        provider_name = "antigravity_image"
        model = "fallback-model"

    service = ImageGenerationService(
        object(),
        model="primary-model",
        project_root=tmp_path,
    )
    plan = type(
        "Plan",
        (),
        {
            "prompt": "prompt",
            "negative_constraints": (),
            "reference_images": (),
            "role": "composite",
        },
    )()
    fallback_identity = service._cache_key(  # noqa: SLF001
        plan,
        "antigravity_image",
        project_id="p1",
        scene_id="s1",
        model=Provider.model,
        visual_style_hash="style-A",
    )
    primary_identity = service._cache_key(  # noqa: SLF001
        plan,
        "cliproxy_image",
        project_id="p1",
        scene_id="s1",
        model="primary-model",
        visual_style_hash="style-A",
    )
    assert fallback_identity != primary_identity
