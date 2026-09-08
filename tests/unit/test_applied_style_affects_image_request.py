from __future__ import annotations

from app.services.scene_image_prompt import SceneImagePromptBuilder


def _storyboard() -> dict:
    return {
        "style_anchor": {
            "visual_language": "legacy collage",
            "palette": ["red"],
            "texture": ["paper"],
            "typography": "serif",
            "continuity_rules": ["same wardrobe"],
        },
        "characters": [],
        "locations": [],
        "scenes": [
            {
                "scene_id": "scene_001",
                "image_prompt": "a person near a window",
                "negative_constraints": ["blur"],
            }
        ],
    }


def test_versioned_applied_snapshot_overrides_legacy_anchor() -> None:
    storyboard = _storyboard()
    storyboard["style_snapshot"] = {
        "schema_version": 1,
        "style_revision": 2,
        "preset": "vox_documentary",
        "visual_language": "blue cinematic documentary",
        "palette": ["navy", "white"],
        "texture": ["film grain"],
        "typography": "sans",
        "negative_prompt": ["logo", "watermark"],
        "continuity_rules": ["same wardrobe"],
        "motion_profile": "calm",
        "renderer_theme": {},
    }

    plan = SceneImagePromptBuilder().build_role(storyboard, "scene_001", "composite")
    request = SceneImagePromptBuilder().to_request(plan)

    assert "blue cinematic documentary" in request.prompt
    assert "navy" in request.prompt
    assert "film grain" in request.prompt
    assert "legacy collage" not in request.prompt
    assert "logo" in request.negative_prompt
    assert "watermark" in request.negative_prompt


def test_draft_only_metadata_does_not_change_applied_prompt() -> None:
    storyboard = _storyboard()
    before = SceneImagePromptBuilder().build_role(storyboard, "scene_001", "composite")
    storyboard["style_draft"] = {
        "visual_language": "unapplied blue style",
        "palette": ["blue"],
    }
    after = SceneImagePromptBuilder().build_role(storyboard, "scene_001", "composite")
    assert before.prompt == after.prompt
    assert before.negative_constraints == after.negative_constraints


def test_same_snapshot_produces_deterministic_request() -> None:
    storyboard = _storyboard()
    first = SceneImagePromptBuilder().build_role(storyboard, "scene_001", "composite")
    second = SceneImagePromptBuilder().build_role(storyboard, "scene_001", "composite")
    assert SceneImagePromptBuilder().to_request(first) == SceneImagePromptBuilder().to_request(second)


def test_legacy_storyboard_remains_backward_compatible() -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "background")
    assert "legacy collage" in plan.prompt
    assert "red" in plan.prompt
    assert "paper" in plan.prompt


def test_applied_snapshot_negative_prompt_merges_scene_constraints() -> None:
    storyboard = _storyboard()
    storyboard["style_snapshot"] = {
        "schema_version": 1,
        "style_revision": 1,
        "preset": "editorial_collage",
        "visual_language": "editorial",
        "palette": ["black"],
        "texture": ["paper"],
        "typography": "serif",
        "negative_prompt": ["logo"],
        "continuity_rules": [],
        "motion_profile": "default",
        "renderer_theme": {},
    }
    plan = SceneImagePromptBuilder().build_role(storyboard, "scene_001", "background")
    assert plan.negative_constraints == ("blur", "logo")
