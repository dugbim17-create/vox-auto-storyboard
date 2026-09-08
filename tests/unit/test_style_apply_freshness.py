from __future__ import annotations

import json
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
from app.services.apply_style_service import ApplyStyleService
from app.services.prompts import load_presets
from app.services.style_project_service import StyleProjectService
from app.storage.asset_store import AssetStore
from app.storage.database import Base
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo


def _storyboard(project_id: str) -> dict:
    scenes = []
    for index in range(1, 5):
        scenes.append(
            {
                "scene_id": f"scene_{index:03d}",
                "order": index,
                "script_span": {"start_char": index * 10, "end_char": index * 10 + 5},
                "narration_text": f"Scene {index}",
                "visual_summary": f"Visual {index}",
                "image_prompt": f"Prompt {index}",
                "motion_template": "01_subject_slide_headline_pop",
                "estimated_duration_seconds": 2,
            }
        )
    return {
        "project_id": project_id,
        "summary": "Test storyboard",
        "style_anchor": {
            "visual_language": "legacy collage",
            "palette": ["red"],
            "texture": ["paper"],
            "typography": "serif",
        },
        "characters": [],
        "locations": [],
        "scenes": scenes,
    }


def test_apply_reports_selected_asset_freshness_without_deleting_assets(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    project_root = tmp_path / "projects"
    store = AssetStore(project_root)
    store.init_project("p1")
    store.write_manifest("p1", "storyboard.json", _storyboard("p1"))

    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1", style_preset="editorial_collage")
        for index in range(1, 5):
            scene_id = f"scene_{index:03d}"
            SceneRepo.add(session, "p1", scene_id=scene_id, order=index)
            asset = AssetRepo.add(
                session,
                "p1",
                scene_id,
                asset_id=f"{scene_id}_composite_v001",
                role="composite",
                path=f"{scene_id}.jpg",
                version=1,
                selected=True,
                visual_style_hash=None if index == 1 else "style-A",
                cache_identity=f"identity-{index}",
            )
            SceneRepo.set_selected_image(session, "p1", scene_id, asset.asset_id)
        session.commit()

        StyleProjectService(project_root=project_root, presets=load_presets()).save_draft(
            "p1",
            session,
            preset="editorial_collage",
            visual_language="blue documentary",
            palette="navy, white",
            texture="film grain",
        )
        result = ApplyStyleService(project_root=project_root, presets=load_presets()).apply(
            "p1", session
        )

        assert result["freshness"] == {"fresh": 0, "stale": 3, "unknown": 1, "missing": 0}
        assert len(AssetRepo.list(session, "p1")) == 4
        assert all(asset.selected for asset in AssetRepo.list(session, "p1"))
        assert all(
            SceneRepo.get(session, "p1", f"scene_{index:03d}").selected_image_asset_id
            for index in range(1, 5)
        )

    storyboard = json.loads(store.read_project_file("p1", "manifests/storyboard.json"))
    assert storyboard["style_snapshot"]["visual_hash"] == result["visual_hash"]


def test_noop_apply_reports_current_style_assets_fresh(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    project_root = tmp_path / "projects"
    store = AssetStore(project_root)
    store.init_project("p1")
    store.write_manifest("p1", "storyboard.json", _storyboard("p1"))

    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1", style_preset="editorial_collage")
        for index in range(1, 5):
            SceneRepo.add(session, "p1", scene_id=f"scene_{index:03d}", order=index)
        session.commit()
        draft_service = StyleProjectService(project_root=project_root, presets=load_presets())
        draft_service.save_draft(
            "p1", session, preset="editorial_collage", visual_language="blue documentary",
            palette="navy, white", texture="film grain",
        )
        apply_service = ApplyStyleService(project_root=project_root, presets=load_presets())
        first = apply_service.apply("p1", session)
        for index in range(1, 5):
            scene_id = f"scene_{index:03d}"
            asset = AssetRepo.add(
                session, "p1", scene_id, asset_id=f"{scene_id}_composite_v001",
                role="composite", path=f"{scene_id}.jpg", version=1, selected=True,
                visual_style_hash=first["visual_hash"], cache_identity=f"identity-{index}",
            )
            SceneRepo.set_selected_image(session, "p1", scene_id, asset.asset_id)
        session.commit()
        second = apply_service.apply("p1", session)
        assert second["freshness"] == {"fresh": 4, "stale": 0, "unknown": 0, "missing": 0}
        assert second["visual_hash"] == first["visual_hash"]
