from __future__ import annotations

import pytest

from app.schemas.visual_events import VisualEventError, build_visual_stage


def crisis_stage() -> dict:
    return {
        "stage_id": "crisis_2008",
        "narration": "Năm 2008, SpaceX thất bại nhiều lần, còn Tesla đối mặt với khủng hoảng tiền mặt.",
        "duration_ms": 5200,
        "background": "aged_paper_grid",
        "events": [
            {"event_id": "year", "trigger": "năm 2008", "start_ms": 0, "duration_ms": 650, "asset": "text:2008", "placement": "center_top", "enter": "counter", "persistent": True},
            {"event_id": "spacex", "trigger": "SpaceX", "start_ms": 650, "duration_ms": 750, "asset": "spacex_wordmark", "placement": "left", "enter": "swipe_right", "persistent": True},
            {"event_id": "rocket", "trigger": "phóng", "start_ms": 1100, "duration_ms": 900, "asset": "rocket_cutout", "placement": "left_center", "enter": "popup", "persistent": True},
            {"event_id": "failures", "trigger": "thất bại nhiều lần", "start_ms": 2000, "duration_ms": 1300, "asset": "failure_markers_3", "placement": "left_bottom", "enter": "stamp", "persistent": True},
            {"event_id": "tesla", "trigger": "Tesla", "start_ms": 3100, "duration_ms": 750, "asset": "tesla_card", "placement": "right", "enter": "page_flip", "persistent": True},
            {"event_id": "cash_crisis", "trigger": "khủng hoảng tiền mặt", "start_ms": 3800, "duration_ms": 1400, "asset": "cash_meter_crisis", "placement": "right_bottom", "enter": "counter", "persistent": True},
        ],
    }


def test_stage_accumulates_events_in_narration_order() -> None:
    stage = build_visual_stage(crisis_stage())
    assert stage.event_count == 6
    assert [event.event_id for event in stage.events] == ["year", "spacex", "rocket", "failures", "tesla", "cash_crisis"]
    assert all(event.persistent for event in stage.events)
    assert stage.events[-1].end_ms == 5200


def test_stage_rejects_event_outside_duration() -> None:
    data = crisis_stage()
    data["events"][2]["start_ms"] = 5000
    with pytest.raises(VisualEventError, match="exceeds stage duration"):
        build_visual_stage(data)


def test_stage_rejects_unordered_events_and_unknown_effect() -> None:
    data = crisis_stage()
    data["events"][1]["start_ms"] = 1200
    with pytest.raises(VisualEventError, match="ordered"):
        build_visual_stage(data)
    data = crisis_stage()
    data["events"][0]["enter"] = "random_magic"
    with pytest.raises(VisualEventError, match="invalid enter"):
        build_visual_stage(data)


def test_stage_round_trip_keeps_effect_and_trigger_contract() -> None:
    stage = build_visual_stage(crisis_stage())
    payload = stage.to_dict()
    assert payload["events"][0]["trigger"] == "năm 2008"
    assert payload["events"][3]["enter"] == "stamp"
    assert payload["events"][4]["persistent"] is True
