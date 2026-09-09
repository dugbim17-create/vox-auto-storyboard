from __future__ import annotations

import pytest

from app.services.quiz_style_packs import (
    STYLE_IDS,
    StylePackError,
    get_style_pack,
    resolve_style_snapshot,
)


def test_registry_exposes_three_phase_b_presets() -> None:
    assert STYLE_IDS == (
        "sport-scoreboard",
        "editorial-culture",
        "clear-knowledge",
    )
    snapshots = [resolve_style_snapshot(style_id) for style_id in STYLE_IDS]
    assert [snapshot["id"] for snapshot in snapshots] == list(STYLE_IDS)
    assert all(snapshot["version"] == 1 for snapshot in snapshots)
    assert all(snapshot["motion"] == "medium" for snapshot in snapshots)
    assert all(snapshot["mascot"] is False for snapshot in snapshots)


def test_same_locale_accepts_every_style_and_snapshot_is_independent() -> None:
    first = resolve_style_snapshot("clear-knowledge", locale="en-US")
    second = resolve_style_snapshot("clear-knowledge", locale="en-US")
    assert first == second
    first["snapshot"]["palette"]["accent"] = "mutated"
    assert second["snapshot"]["palette"]["accent"] != "mutated"
    assert get_style_pack("clear-knowledge")["id"] == "clear-knowledge"


@pytest.mark.parametrize("style_id", ["", "unknown", "clear_knowledge"])
def test_unknown_style_fails_closed(style_id: str) -> None:
    with pytest.raises(StylePackError, match="Unknown visual style"):
        resolve_style_snapshot(style_id)


@pytest.mark.parametrize("motion", ["", "burst", "low\ncode"])
def test_invalid_motion_fails_closed(motion: str) -> None:
    with pytest.raises(StylePackError, match="motion"):
        resolve_style_snapshot("clear-knowledge", motion=motion)


def test_style_snapshot_rejects_unsafe_override_payload() -> None:
    with pytest.raises(StylePackError, match="snapshot"):
        resolve_style_snapshot(
            "clear-knowledge",
            snapshot_override={"palette": {"accent": "javascript:alert(1)"}},
        )
