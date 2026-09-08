"""Unit tests for MicroBeatPlanner."""

from __future__ import annotations

from app.services.micro_beat_planner import MicroBeatPlanner


def test_plan_scene_beats_divides_duration_into_micro_beats() -> None:
    plan = MicroBeatPlanner.plan_scene_beats(
        "scene_001",
        duration_ms=6000,
        template_name="07_document_highlight",
        headline="1933: ĐẾ CHẾ ĐỘC TÀI",
        key_phrase="BÃI BỎ ĐA ĐẢNG",
    )

    assert plan.scene_id == "scene_001"
    assert plan.total_duration_ms == 6000
    assert plan.beat_count >= 2
    assert sum(b.duration_ms for b in plan.beats) == 6000
    assert plan.beats[0].headline == "1933: ĐẾ CHẾ ĐỘC TÀI"
    assert plan.beats[1].highlight_text == "BÃI BỎ ĐA ĐẢNG"


def test_plan_scene_beats_for_radar_map_template() -> None:
    plan = MicroBeatPlanner.plan_scene_beats(
        "scene_map",
        duration_ms=5000,
        template_name="03_map_pan_marker_pulse",
    )
    actions = [b.visual_action for b in plan.beats]
    assert "radar_sweep" in actions or "arrow_tracer" in actions
