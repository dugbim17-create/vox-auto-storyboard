from __future__ import annotations

from app.services.prompts import StylePreset
from app.services.style_resolver import StyleResolver


def _preset() -> StylePreset:
    return StylePreset(
        "editorial_collage",
        {
            "visual_language": "preset language",
            "palette": ["preset cream", "preset ink"],
            "texture": ["preset grain"],
            "typography": "preset serif",
            "continuity_rules": ["preset continuity"],
        },
    )


def _storyboard() -> dict:
    return {
        "style_anchor": {
            "visual_language": "legacy language",
            "palette": ["legacy red"],
            "texture": ["legacy paper"],
            "typography": "legacy serif",
            "continuity_rules": ["legacy continuity"],
        }
    }


def test_resolve_legacy_applied_snapshot_from_storyboard_anchor() -> None:
    result = StyleResolver({"editorial_collage": _preset()}).resolve_applied(_storyboard())
    assert result.visual_language == "legacy language"
    assert result.palette == ("legacy red",)
    assert result.style_revision == 1


def test_resolve_applied_prefers_versioned_snapshot() -> None:
    storyboard = _storyboard()
    storyboard["style_snapshot"] = {
        "schema_version": 1,
        "style_revision": 4,
        "preset": "vox_documentary",
        "visual_language": "applied language",
        "palette": ["navy"],
        "texture": ["film grain"],
        "typography": "sans",
        "negative_prompt": ["logo"],
        "continuity_rules": ["same wardrobe"],
        "motion_profile": "calm",
        "renderer_theme": {"grain": 0.1},
    }
    result = StyleResolver({"editorial_collage": _preset()}).resolve_applied(storyboard)
    assert result.style_revision == 4
    assert result.visual_language == "applied language"
    assert result.palette == ("navy",)


def test_resolve_draft_prefers_explicit_values_then_preset_then_storyboard() -> None:
    result = StyleResolver({"editorial_collage": _preset()}).resolve_draft(
        project_id="p1",
        project_preset="editorial_collage",
        storyboard=_storyboard(),
        draft_payload={
            "schema_version": 1,
            "revision": 2,
            "preset": "editorial_collage",
            "visual_language": "custom language",
            "palette": [],
        },
    )
    assert result.visual_language == "custom language"
    assert result.palette == ("preset cream", "preset ink")
    assert result.texture == ("preset grain",)
    assert result.project_id == "p1"
    assert result.revision == 2


def test_partial_draft_without_known_preset_falls_back_to_storyboard() -> None:
    result = StyleResolver({}).resolve_draft(
        project_id="p1",
        project_preset="unknown",
        storyboard=_storyboard(),
        draft_payload={"schema_version": 1, "revision": 1, "preset": "unknown"},
    )
    assert result.visual_language == "legacy language"
    assert result.palette == ("legacy red",)


def test_draft_values_do_not_change_applied_snapshot() -> None:
    resolver = StyleResolver({"editorial_collage": _preset()})
    applied_before = resolver.resolve_applied(_storyboard())
    resolver.resolve_draft(
        project_id="p1",
        project_preset="editorial_collage",
        storyboard=_storyboard(),
        draft_payload={
            "schema_version": 1,
            "revision": 2,
            "preset": "editorial_collage",
            "palette": ["blue"],
        },
    )
    applied_after = resolver.resolve_applied(_storyboard())
    assert applied_before == applied_after
