from __future__ import annotations

from pathlib import Path

from app.services.visual_stage_pipeline import VisualStagePipeline


def stage_spec() -> dict:
    return {
        "stage_id": "crisis_2008",
        "narration": "Năm 2008, SpaceX và Tesla đối mặt với khủng hoảng.",
        "duration_ms": 5200,
        "background": "bg.png",
        "events": [
            {
                "event_id": "year",
                "trigger": "Năm 2008",
                "start_ms": 0,
                "duration_ms": 600,
                "asset": "year",
                "placement": "center_top",
                "enter": "counter",
            },
            {
                "event_id": "crisis",
                "trigger": "khủng hoảng",
                "start_ms": 2400,
                "duration_ms": 1200,
                "asset": "crisis",
                "placement": "right_bottom",
                "enter": "stamp",
            },
        ],
    }


def test_pipeline_validates_and_writes_stage_manifest(tmp_path: Path) -> None:
    pipeline = VisualStagePipeline()
    result = pipeline.prepare_stage(
        stage_spec(),
        assets={"year": "year.png", "crisis": "crisis.png"},
        output_path=tmp_path / "crisis.mp4",
        manifest_path=tmp_path / "crisis.json",
    )
    assert result.stage_id == "crisis_2008"
    assert result.event_count == 2
    assert result.duration_ms == 5200
    assert result.command[-1] == str(tmp_path / "crisis.mp4")
    assert (tmp_path / "crisis.json").is_file()


def test_pipeline_keeps_stage_events_ordered(tmp_path: Path) -> None:
    pipeline = VisualStagePipeline()
    result = pipeline.prepare_stage(
        stage_spec(),
        assets={"year": "year.png", "crisis": "crisis.png"},
        output_path=tmp_path / "crisis.mp4",
        manifest_path=tmp_path / "crisis.json",
    )
    assert result.event_ids == ("year", "crisis")
    assert "enable='between(t,2.400,3.600)'" in result.filter_graph
