"""Tests for P4-T04 scene image prompt builder.

Covers the acceptance criteria:

- không yêu cầu AI tạo chữ: every built prompt carries the TEXT_SAFE_STUB
  (no text/words/letters) so the model never renders typography;
- prompt có text-safe area: background leaves open space, foreground is an
  edge overlay — verified structurally;
- prompt có continuity: style anchor + verbatim character descriptions are
  inlined and identical across scenes;
- prompt role-specific: background/subject/foreground/texture/composite each
  have distinct content.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.providers.base import IMAGE_ROLES, ImageGenerationRequest
from app.services.scene_image_prompt import (
    TEXT_SAFE_STUB,
    BuiltPrompt,
    SceneImagePromptBuilder,
    SceneImagePromptBuilderError,
)


def _storyboard(**overrides: Any) -> dict[str, Any]:
    sb: dict[str, Any] = {
        "project_id": "prj_test",
        "summary": "A test storyboard.",
        "style_anchor": {
            "visual_language": "editorial collage, warm grain",
            "palette": ["crimson", "cream", "ink"],
            "texture": ["paper grain", "halftone"],
            "typography": "Serif display",
            "continuity_rules": ["keep the red car the same across scenes"],
        },
        "characters": [
            {
                "character_id": "char_001",
                "name": "An",
                "description": "a young cyclist in a red jacket",
            }
        ],
        "locations": [
            {"location_id": "loc_001", "name": "old town", "description": "cobbled lanes"}
        ],
        "scenes": [
            {
                "scene_id": "scene_001",
                "order": 1,
                "script_span": {"start_char": 0, "end_char": 10},
                "narration_text": "An pedals through the old town.",
                "visual_summary": "A cyclist crossing a cobbled lane.",
                "image_prompt": "a red-jacketed cyclist on a cobbled lane in morning light",
                "negative_constraints": ["blur", "people in background"],
                "purpose": "hook",
            },
            {
                "scene_id": "scene_002",
                "order": 2,
                "script_span": {"start_char": 11, "end_char": 25},
                "narration_text": "The sun climbs above the rooftops.",
                "visual_summary": "Sunrise over the rooftops.",
                "image_prompt": "rooftops at sunrise with warm light",
                "negative_constraints": [],
                "purpose": "body",
            },
        ],
    }
    sb.update(overrides)
    return sb


def _roles_for(sb: dict[str, Any], scene_id: str) -> list[BuiltPrompt]:
    return SceneImagePromptBuilder().build(sb)[scene_id]


# --------------------------------------------------------------------------- #
# Structure: roles per scene
# --------------------------------------------------------------------------- #
def test_build_returns_all_five_roles_per_scene() -> None:
    sb = _storyboard()
    by_scene = SceneImagePromptBuilder().build(sb)
    assert set(by_scene) == {"scene_001", "scene_002"}
    for scene_id in ("scene_001", "scene_002"):
        roles = [p.role for p in by_scene[scene_id]]
        assert sorted(roles) == sorted(IMAGE_ROLES)


def test_composite_is_first_role() -> None:
    plans = _roles_for(_storyboard(), "scene_001")
    assert plans[0].role == "composite"


def test_every_plan_carries_scene_id_role_aspect() -> None:
    plans = _roles_for(_storyboard(), "scene_002")
    for plan in plans:
        assert plan.scene_id == "scene_002"
        assert plan.role in IMAGE_ROLES
        assert plan.aspect_ratio == "16:9"


def test_build_empty_storyboard_returns_empty() -> None:
    assert SceneImagePromptBuilder().build({}) == {}


def test_missing_image_prompt_raises() -> None:
    sb = _storyboard()
    del sb["scenes"][0]["image_prompt"]
    with pytest.raises(SceneImagePromptBuilderError):
        SceneImagePromptBuilder().build(sb)


# --------------------------------------------------------------------------- #
# AC1: no AI-generated text
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("role", IMAGE_ROLES)
def test_text_safe_clause_in_every_role(role: str) -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", role)
    assert "No text" in plan.prompt
    assert "no words" in plan.prompt
    assert "no watermark" in plan.prompt
    assert "no typography" in plan.prompt


def test_text_safe_stub_is_shared_constant() -> None:
    assert "no letters" in TEXT_SAFE_STUB
    assert "no logo" in TEXT_SAFE_STUB


# --------------------------------------------------------------------------- #
# AC2: text-safe area
# --------------------------------------------------------------------------- #
def test_background_keeps_empty_space() -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "background")
    assert "clean background layer" in plan.prompt
    assert "open space" in plan.prompt
    assert "Do not place the subject" in plan.prompt


def test_foreground_is_edge_overlay_for_depth() -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "foreground")
    assert "Foreground overlay layer" in plan.prompt
    assert "frame edge" in plan.prompt
    assert "parallax" in plan.prompt
    assert "flat" in plan.negative_constraints  # flat helps the overlay not carry depth


# --------------------------------------------------------------------------- #
# AC3: continuity
# --------------------------------------------------------------------------- #
def test_style_block_present_and_consistent() -> None:
    sb = _storyboard()
    b = SceneImagePromptBuilder()
    s1_bg = b.build_role(sb, "scene_001", "background").prompt
    s2_bg = b.build_role(sb, "scene_002", "background").prompt
    # Style anchor inlined identically in every role & scene.
    assert "crimson" in s1_bg
    assert "paper grain" in s1_bg
    assert "editorial collage" in s1_bg
    assert s1_bg.split("Visual language:")[1].split(".")[0].strip() == (
        s2_bg.split("Visual language:")[1].split(".")[0].strip()
    )


def test_character_description_reused_verbatim_in_subject() -> None:
    sb = _storyboard()
    plans = _roles_for(sb, "scene_001")
    subject = next(p for p in plans if p.role == "subject")
    assert "An" in subject.prompt
    assert "a young cyclist in a red jacket" in subject.prompt  # verbatim desc


def test_composite_lists_characters_and_locations() -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "composite")
    assert "An" in plan.prompt
    assert "old town" in plan.prompt


def test_composite_carries_character_reference_image() -> None:
    sb = _storyboard()
    sb["characters"][0]["image"] = "refs/an.png"
    plan = SceneImagePromptBuilder().build_role(sb, "scene_001", "composite")
    assert plan.reference_images == ("refs/an.png",)


# --------------------------------------------------------------------------- #
# AC4: role-specific content
# --------------------------------------------------------------------------- #
def test_roles_have_distinct_prompts() -> None:
    plans = _roles_for(_storyboard(), "scene_001")
    prompts = {p.role: p.prompt for p in plans}
    # Each role prompt differs from every other.
    unique = {prompts[r] for r in IMAGE_ROLES}
    assert len(unique) == len(IMAGE_ROLES)
    # Role keywords that make them distinct.
    assert "background layer" in prompts["background"]
    assert "Hero subject layer" in prompts["subject"]
    assert "Foreground overlay layer" in prompts["foreground"]
    assert "Abstract texture/overlay patch" in prompts["texture"]
    assert "Full composite reference frame" in prompts["composite"]


# --------------------------------------------------------------------------- #
# build_role / to_request
# --------------------------------------------------------------------------- #
def test_build_role_invalid_role_raises() -> None:
    with pytest.raises(SceneImagePromptBuilderError):
        SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "nope")


def test_build_role_missing_scene_raises() -> None:
    with pytest.raises(SceneImagePromptBuilderError):
        SceneImagePromptBuilder().build_role(_storyboard(), "scene_999", "background")


def test_to_request_wraps_built_prompt() -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "subject")
    req = SceneImagePromptBuilder().to_request(plan, seed=42, output_path="out/s.png")
    assert isinstance(req, ImageGenerationRequest)
    assert req.prompt == plan.prompt
    assert req.role == "subject"
    assert req.seed == 42
    assert req.output_path == "out/s.png"
    assert req.candidate_count == 1
    assert req.aspect_ratio == "16:9"


def test_to_request_negative_constraints_joined() -> None:
    plan = SceneImagePromptBuilder().build_role(_storyboard(), "scene_001", "background")
    req = SceneImagePromptBuilder().to_request(plan)
    assert "blur" in req.negative_prompt
    assert "people in background" in req.negative_prompt
