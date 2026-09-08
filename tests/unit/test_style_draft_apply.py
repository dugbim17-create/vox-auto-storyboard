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
from app.storage.repositories import ProjectRepo


def _storyboard() -> dict:
    scenes = []
    cursor = 0
    for index in range(1, 5):
        scenes.append(
            {
                "scene_id": f"scene_{index:03d}",
                "order": index,
                "script_span": {"start_char": cursor, "end_char": cursor + 5},
                "narration_text": f"Scene {index}",
                "visual_summary": f"Visual {index}",
                "image_prompt": f"Prompt {index}",
                "motion_template": "01_subject_slide_headline_pop",
                "estimated_duration_seconds": 2,
            }
        )
        cursor += 5
    return {
        "project_id": "p1",
        "summary": "Test storyboard",
        "style_anchor": {
            "visual_language": "legacy collage",
            "palette": ["red", "cream"],
            "texture": ["paper"],
            "typography": "serif",
            "continuity_rules": ["same character"],
        },
        "characters": [],
        "locations": [],
        "scenes": scenes,
    }


def _session(tmp_path: Path) -> tuple[Session, AssetStore]:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    ProjectRepo.create(session, project_id="p1", style_preset="editorial_collage")
    session.commit()
    store = AssetStore(tmp_path / "projects")
    store.init_project("p1")
    store.write_manifest("p1", "storyboard.json", _storyboard())
    return session, store


def test_save_draft_does_not_modify_applied_storyboard(tmp_path: Path) -> None:
    session, store = _session(tmp_path)
    before = json.loads(store.read_project_file("p1", "manifests/storyboard.json"))
    service = StyleProjectService(project_root=store.base, presets=load_presets())

    saved = service.save_draft(
        "p1",
        session,
        preset="editorial_collage",
        visual_language="blue cinematic collage",
        palette="navy, white",
        texture="film grain",
        typography="sans",
        negative_prompt="logo, watermark",
        continuity_rules="same wardrobe",
        motion_profile="default",
        renderer_theme={"grain": 0.1},
    )

    after = json.loads(store.read_project_file("p1", "manifests/storyboard.json"))
    assert before["style_anchor"] == after["style_anchor"]
    assert saved["draft_hash"]
    assert saved["revision"] == 1
    session.close()


def test_noop_save_preserves_revision_and_hash(tmp_path: Path) -> None:
    session, store = _session(tmp_path)
    service = StyleProjectService(project_root=store.base, presets=load_presets())
    kwargs = {
        "preset": "editorial_collage",
        "visual_language": "blue cinematic collage",
        "palette": "navy, white",
        "texture": "film grain",
        "typography": "sans",
        "negative_prompt": "logo",
        "continuity_rules": "same wardrobe",
        "motion_profile": "default",
        "renderer_theme": {"grain": 0.1},
    }
    first = service.save_draft("p1", session, **kwargs)
    second = service.save_draft("p1", session, **kwargs)
    assert second["revision"] == first["revision"]
    assert second["draft_hash"] == first["draft_hash"]
    session.close()


def test_changed_draft_increments_revision(tmp_path: Path) -> None:
    session, store = _session(tmp_path)
    service = StyleProjectService(project_root=store.base, presets=load_presets())
    first = service.save_draft(
        "p1", session, preset="editorial_collage", visual_language="A", palette="red",
        texture="paper", typography="serif", negative_prompt="", continuity_rules="",
        motion_profile="default", renderer_theme={},
    )
    second = service.save_draft(
        "p1", session, preset="editorial_collage", visual_language="B", palette="blue",
        texture="film", typography="sans", negative_prompt="logo", continuity_rules="same",
        motion_profile="default", renderer_theme={},
    )
    assert second["revision"] == first["revision"] + 1
    assert second["draft_hash"] != first["draft_hash"]
    session.close()


def test_apply_style_updates_snapshot_and_legacy_anchor(tmp_path: Path) -> None:
    session, store = _session(tmp_path)
    draft_service = StyleProjectService(project_root=store.base, presets=load_presets())
    draft = draft_service.save_draft(
        "p1", session, preset="editorial_collage", visual_language="blue cinematic collage",
        palette="navy, white", texture="film grain", typography="sans",
        negative_prompt="logo, watermark", continuity_rules="same wardrobe",
        motion_profile="calm", renderer_theme={"grain": 0.1},
    )

    applied = ApplyStyleService(project_root=store.base, presets=load_presets()).apply(
        "p1", session
    )
    storyboard = json.loads(store.read_project_file("p1", "manifests/storyboard.json"))

    assert storyboard["style_anchor"]["visual_language"] == "blue cinematic collage"
    assert storyboard["style_anchor"]["palette"] == ["navy", "white"]
    assert storyboard["style_snapshot"]["visual_hash"] == applied["visual_hash"]
    assert storyboard["style_snapshot"]["style_revision"] == draft["revision"]
    assert applied["visual_hash"]
    session.close()


def test_apply_style_rejects_project_without_storyboard(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1")
        session.commit()
        service = ApplyStyleService(project_root=tmp_path / "projects", presets=load_presets())
        try:
            service.apply("p1", session)
        except ValueError as exc:
            assert "storyboard" in str(exc)
        else:
            raise AssertionError("expected missing storyboard to fail")
