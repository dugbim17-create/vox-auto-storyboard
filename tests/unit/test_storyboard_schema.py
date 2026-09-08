"""Tests for P2-T03 Storyboard JSON Schema.

Covers the acceptance criteria:

- valid fixture passes;
- invalid fixture fails;
- scene count rule (4..20) is enforced.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.storyboard import (
    MAX_SCENES,
    MIN_SCENES,
    StoryboardValidationError,
    get_schema,
    is_valid_storyboard,
    validate_storyboard,
)


def make_scene(order: int, *, scene_id: str | None = None) -> dict[str, Any]:
    return {
        "scene_id": scene_id or f"scene_{order:03d}",
        "order": order,
        "script_span": {
            "start_char": (order - 1) * 100,
            "end_char": order * 100,
        },
        "narration_text": f"Narration for scene {order}.",
        "purpose": "hook" if order == 1 else "body",
        "estimated_duration_seconds": 5.0,
        "visual_summary": f"Visual summary of scene {order}.",
        "image_prompt": f"Detailed image prompt for scene {order}.",
        "negative_constraints": ["no text", "no watermark"],
        "motion_prompt": "subtle zoom",
        "motion_template": "subject_enter_headline_pop",
        "transition_out": "paper_wipe",
    }


def make_storyboard(scene_count: int = 5) -> dict[str, Any]:
    return {
        "project_id": "prj_test",
        "summary": "A short ad about coffee.",
        "target_duration_seconds": 30,
        "style_anchor": {
            "visual_language": "editorial paper collage",
            "palette": ["off-white", "black", "red accent"],
            "texture": ["paper grain", "halftone"],
            "typography": "bold editorial sans",
            "continuity_rules": ["keep the red accent on product"],
        },
        "characters": [
            {
                "character_id": "char_001",
                "name": "Barista",
                "description": "Young barista in an apron.",
            }
        ],
        "locations": [
            {
                "location_id": "loc_001",
                "name": "Cafe",
                "description": "Small warm cafe with wooden tables.",
            }
        ],
        "scenes": [make_scene(i) for i in range(1, scene_count + 1)],
    }


# --------------------------------------------------------------------------- #
# Valid fixtures
# --------------------------------------------------------------------------- #
def test_valid_fixture_passes() -> None:
    storyboard = make_storyboard(5)
    validate_storyboard(storyboard)  # should not raise
    assert is_valid_storyboard(storyboard)


def test_schema_requires_core_fields() -> None:
    schema = get_schema()
    required = set(schema["required"])
    assert {"summary", "style_anchor", "characters", "locations", "scenes"} <= required


def test_schema_min_max_scene_bounds() -> None:
    schema = get_schema()
    scenes = schema["properties"]["scenes"]
    assert scenes["minItems"] == MIN_SCENES
    assert scenes["maxItems"] == MAX_SCENES


# --------------------------------------------------------------------------- #
# Invalid fixtures
# --------------------------------------------------------------------------- #
def test_missing_summary_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["summary"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)
    assert not is_valid_storyboard(storyboard)


def test_missing_scenes_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["scenes"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_missing_style_anchor_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["style_anchor"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_scene_missing_narration_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["scenes"][0]["narration_text"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_scene_missing_motion_template_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["scenes"][0]["motion_template"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_scene_missing_image_prompt_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["scenes"][0]["image_prompt"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_scene_missing_duration_fails() -> None:
    storyboard = make_storyboard(5)
    del storyboard["scenes"][0]["estimated_duration_seconds"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_character_without_name_fails() -> None:
    storyboard = make_storyboard(5)
    storyboard["characters"] = [{"character_id": "c1"}]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_character_without_id_allowed() -> None:
    # Schema requires only `name`; character_id is auto-generated by the pipeline.
    storyboard = make_storyboard(5)
    storyboard["characters"] = [{"name": "Barista"}]
    validate_storyboard(storyboard)


# --------------------------------------------------------------------------- #
# Scene count rule
# --------------------------------------------------------------------------- #
def test_scene_count_too_few_fails() -> None:
    storyboard = make_storyboard(MIN_SCENES - 1)
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_scene_count_too_many_fails() -> None:
    storyboard = make_storyboard(MAX_SCENES + 1)
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_scene_count_minimum_ok() -> None:
    storyboard = make_storyboard(MIN_SCENES)
    validate_storyboard(storyboard)


def test_scene_count_maximum_ok() -> None:
    storyboard = make_storyboard(MAX_SCENES)
    validate_storyboard(storyboard)


# --------------------------------------------------------------------------- #
# Workflow rules (section 17.1)
# --------------------------------------------------------------------------- #
def test_duplicate_scene_ids_fail() -> None:
    storyboard = make_storyboard(5)
    storyboard["scenes"][1]["scene_id"] = storyboard["scenes"][0]["scene_id"]
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_non_contiguous_order_fails() -> None:
    storyboard = make_storyboard(5)
    storyboard["scenes"][2]["order"] = 99
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


def test_overlapping_script_span_fails() -> None:
    storyboard = make_storyboard(5)
    # Make scene 2's span start inside scene 1's span.
    storyboard["scenes"][1]["script_span"] = {
        "start_char": 50,
        "end_char": 150,
    }
    with pytest.raises(StoryboardValidationError):
        validate_storyboard(storyboard)


# --------------------------------------------------------------------------- #
# Structured optional fields (LLM may emit objects)
# --------------------------------------------------------------------------- #
def test_motion_prompt_as_object_allowed() -> None:
    storyboard = make_storyboard(5)
    storyboard["scenes"][0]["motion_prompt"] = {
        "background_camera": "slow pan",
        "subject": "slide in",
        "foreground_effect": "word pop",
    }
    validate_storyboard(storyboard)


def test_transition_out_as_object_allowed() -> None:
    storyboard = make_storyboard(5)
    storyboard["scenes"][0]["transition_out"] = {
        "type": "paper_tear_wipe",
        "duration_seconds": 0.6,
    }
    validate_storyboard(storyboard)


def test_continuity_rules_as_string_allowed() -> None:
    storyboard = make_storyboard(5)
    storyboard["style_anchor"]["continuity_rules"] = "keep the red accent on product"
    validate_storyboard(storyboard)
