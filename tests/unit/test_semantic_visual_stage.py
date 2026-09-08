from __future__ import annotations

import pytest

from app.schemas.semantic_visual_stage import (
    SemanticStageError,
    build_semantic_stage,
)


def semantic_stage() -> dict:
    return {
        "stage_id": "return_to_apple",
        "narration": "Apple mua NeXT; Jobs trở lại Apple.",
        "duration_ms": 5000,
        "background": "background.png",
        "entities": [
            {"entity_id": "jobs", "kind": "character", "asset": "jobs.png", "x": 300, "y": 420},
            {"entity_id": "next", "kind": "company", "asset": "next.png", "x": 620, "y": 420},
            {"entity_id": "apple", "kind": "company", "asset": "apple.png", "x": 1380, "y": 420},
        ],
        "events": [
            {"event_id": "show_jobs", "start_ms": 0, "duration_ms": 600, "action": "reveal", "target": "jobs"},
            {"event_id": "show_next", "start_ms": 500, "duration_ms": 600, "action": "reveal", "target": "next"},
            {"event_id": "show_apple", "start_ms": 1200, "duration_ms": 600, "action": "reveal", "target": "apple"},
            {"event_id": "acquire", "start_ms": 2000, "duration_ms": 900, "action": "connect", "source": "apple", "target": "next", "label": "MUA · 1996"},
            {"event_id": "merge", "start_ms": 2900, "duration_ms": 900, "action": "merge", "source": "next", "target": "apple"},
            {"event_id": "return", "start_ms": 3800, "duration_ms": 900, "action": "move", "target": "jobs", "to_x": 1260, "to_y": 420, "label": "TRỞ LẠI · 1997"},
        ],
    }


def test_semantic_stage_tracks_entities_relationships_and_state_mutations() -> None:
    stage = build_semantic_stage(semantic_stage())
    assert [entity.entity_id for entity in stage.entities] == ["jobs", "next", "apple"]
    assert [event.action for event in stage.events] == ["reveal", "reveal", "reveal", "connect", "merge", "move"]
    assert stage.visual_action_count == 6
    assert stage.text_only_event_count == 0


def test_semantic_stage_rejects_relationship_to_unknown_entity() -> None:
    data = semantic_stage()
    data["events"][3]["target"] = "missing"
    with pytest.raises(SemanticStageError, match="unknown entity"):
        build_semantic_stage(data)


def test_semantic_stage_rejects_text_only_poster() -> None:
    data = semantic_stage()
    data["entities"] = [{"entity_id": "label", "kind": "label", "asset": "label.png", "x": 100, "y": 100}]
    data["events"] = [{"event_id": "caption", "start_ms": 0, "duration_ms": 1000, "action": "reveal", "target": "label"}]
    with pytest.raises(SemanticStageError, match="non-text semantic entity"):
        build_semantic_stage(data)


def test_semantic_stage_rejects_narration_relationship_without_visual_edge() -> None:
    data = semantic_stage()
    data["events"] = [event for event in data["events"] if event["action"] not in {"connect", "merge"}]
    data["requires_relationship_visualization"] = True
    with pytest.raises(SemanticStageError, match="relationship mutation"):
        build_semantic_stage(data)


def test_semantic_stage_accepts_disconnect_and_focus_mutations() -> None:
    data = semantic_stage()
    data["events"].extend(
        [
            {
                "event_id": "disconnect",
                "start_ms": 4700,
                "duration_ms": 200,
                "action": "disconnect",
                "source": "apple",
                "target": "next",
            },
            {
                "event_id": "focus",
                "start_ms": 4900,
                "duration_ms": 100,
                "action": "focus",
                "target": "apple",
            },
        ]
    )
    stage = build_semantic_stage(data)
    assert [event.action for event in stage.events[-2:]] == ["disconnect", "focus"]
