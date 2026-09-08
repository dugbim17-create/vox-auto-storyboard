from __future__ import annotations

import pytest

from app.schemas.style_contract import StyleContractError, StyleDraftV1, StyleSnapshotV1


def _draft(**overrides):
    data = {
        "schema_version": 1,
        "project_id": "project-a",
        "revision": 1,
        "preset": "vox_documentary",
        "visual_language": "Editorial paper collage",
        "palette": [" cream ", "ink", "cream", ""],
        "texture": ["paper grain", "halftone"],
        "typography": "Bold serif cards",
        "negative_prompt": ["watermark", "logo"],
        "continuity_rules": ["same wardrobe"],
        "motion_profile": "documentary",
        "renderer_theme": {"grain": 0.08, "card_color": "#f3ead7"},
    }
    data.update(overrides)
    return StyleDraftV1.from_mapping(data)


def test_canonical_hashes_ignore_ordering_and_storage_identity() -> None:
    first = _draft()
    second = _draft(
        project_id="project-b",
        revision=9,
        renderer_theme={"card_color": "#f3ead7", "grain": 0.08},
    )
    assert first.draft_hash == second.draft_hash
    assert first.palette == ("cream", "ink")


def test_palette_change_only_changes_visual_domain() -> None:
    first = StyleSnapshotV1.from_draft(_draft(), style_revision=1)
    second = StyleSnapshotV1.from_draft(
        _draft(palette=["navy", "white"]),
        style_revision=2,
    )
    assert first.visual_hash != second.visual_hash
    assert first.motion_hash == second.motion_hash
    assert first.render_theme_hash == second.render_theme_hash


def test_motion_profile_change_only_changes_motion_domain() -> None:
    first = StyleSnapshotV1.from_draft(_draft(), style_revision=1)
    second = StyleSnapshotV1.from_draft(
        _draft(motion_profile="kinetic"),
        style_revision=2,
    )
    assert first.motion_hash != second.motion_hash
    assert first.visual_hash == second.visual_hash


def test_style_a_b_a_restores_content_hashes() -> None:
    style_a = StyleSnapshotV1.from_draft(_draft(), style_revision=1)
    _style_b = StyleSnapshotV1.from_draft(_draft(palette=["blue"]), style_revision=2)
    style_a_again = StyleSnapshotV1.from_draft(_draft(revision=3), style_revision=3)
    assert style_a.visual_hash == style_a_again.visual_hash
    assert style_a.motion_hash == style_a_again.motion_hash
    assert style_a.render_theme_hash == style_a_again.render_theme_hash


def test_unknown_schema_version_fails_closed() -> None:
    with pytest.raises(StyleContractError, match="schema_version"):
        _draft(schema_version=2)


def test_blank_preset_fails_closed() -> None:
    with pytest.raises(StyleContractError, match="preset"):
        _draft(preset="  ")


def test_no_op_draft_normalization_is_stable() -> None:
    first = _draft()
    second = StyleDraftV1.from_mapping(first.to_dict())
    assert first == second
    assert first.draft_hash == second.draft_hash
