from __future__ import annotations

from app.schemas.visual_events import build_visual_stage
from app.services.visual_event_renderer import VisualEventCompiler


def test_event_renderer_keeps_accumulated_events_in_one_filter_graph() -> None:
    stage = build_visual_stage(
        {
            "stage_id": "crisis_2008",
            "narration": "Năm 2008, SpaceX thất bại nhiều lần, còn Tesla đối mặt với khủng hoảng tiền mặt.",
            "duration_ms": 5200,
            "background": r"C:\assets\background.png",
            "events": [
                {"event_id": "year", "trigger": "năm 2008", "start_ms": 0, "duration_ms": 650, "asset": "year", "placement": "center_top", "enter": "counter"},
                {"event_id": "spacex", "trigger": "SpaceX", "start_ms": 650, "duration_ms": 750, "asset": "spacex", "placement": "left", "enter": "swipe_right"},
                {"event_id": "tesla", "trigger": "Tesla", "start_ms": 3100, "duration_ms": 750, "asset": "tesla", "placement": "right", "enter": "page_flip"},
                {"event_id": "crisis", "trigger": "khủng hoảng tiền mặt", "start_ms": 3800, "duration_ms": 1400, "asset": "cash", "placement": "right_bottom", "enter": "counter"},
            ],
        }
    )
    graph, inputs = VisualEventCompiler().build_filter_graph(
        stage,
        assets={"year": "year.png", "spacex": "spacex.png", "tesla": "tesla.png", "cash": "cash.png"},
        options=type("Options", (), {"fps": 30, "width": 1920, "height": 1080, "crf": 18, "preset": "medium"})(),
    )
    assert len(inputs) == 4
    assert "stage0" in graph
    assert "stage1" in graph and "stage2" in graph and "stage4" in graph
    assert "enable='between(t,0.650,1.400)'" in graph
    assert "enable='between(t,3.800,5.200)'" in graph
    assert "[final]" in graph


def test_event_renderer_command_is_argument_list_and_preserves_windows_paths() -> None:
    stage = build_visual_stage(
        {
            "stage_id": "single",
            "narration": "Năm 2008.",
            "duration_ms": 1000,
            "background": r"C:\Project Dir\bg.png",
            "events": [
                {"event_id": "year", "trigger": "2008", "start_ms": 0, "duration_ms": 800, "asset": "year", "placement": "center", "enter": "popup"}
            ],
        }
    )
    command = VisualEventCompiler().compile(
        stage,
        assets={"year": r"C:\Project Dir\year.png"},
        output_path=r"C:\Output Dir\stage.mp4",
    )
    assert isinstance(command, list)
    assert r"C:\Project Dir\bg.png" in command
    assert r"C:\Project Dir\year.png" in command
    assert command[-1] == r"C:\Output Dir\stage.mp4"
    assert "-filter_complex" in command
