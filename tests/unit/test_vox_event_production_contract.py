from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.services.visual_event_scene_renderer import compose_visual_stage_frame
from app.services.vox_event_stage import build_scene_visual_stage
from app.services.vox_production_pipeline import VoxProductionPipeline
from app.storage.asset_store import AssetStore


class FakeSegmentation:
    def produce_mask(self, image: Image.Image) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).rectangle((100, 30, 300, 340), fill=255)
        return mask


def composite(path: Path) -> Path:
    image = Image.new("RGB", (640, 360), "#baab8e")
    ImageDraw.Draw(image).rectangle((100, 30, 300, 340), fill="#222222")
    image.save(path)
    return path


def test_production_pipeline_publishes_visual_stage_and_event_lineage(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    store.init_project("event-vox")
    storyboard = {
        "project_id": "event-vox",
        "style_snapshot": {"visual_hash": "v" * 64, "motion_hash": "m" * 64},
        "scenes": [
            {
                "scene_id": "scene_001",
                "order": 1,
                "purpose": "opening",
                "narration_text": "Năm 2008, SpaceX thất bại nhiều lần, còn Tesla khủng hoảng tiền mặt.",
                "visual_events": [
                    {"event_id": "year", "trigger": "Năm 2008", "start_ms": 0, "duration_ms": 600, "asset": "foreground", "placement": "center_top", "enter": "counter"},
                    {"event_id": "spacex", "trigger": "SpaceX", "start_ms": 650, "duration_ms": 800, "asset": "subject", "placement": "left", "enter": "swipe_right"},
                    {"event_id": "tesla", "trigger": "Tesla", "start_ms": 1700, "duration_ms": 900, "asset": "foreground", "placement": "right", "enter": "page_flip"},
                ],
            }
        ],
    }
    image = composite(tmp_path / "source.png")
    result = VoxProductionPipeline(
        project_root=store.base,
        canvas_size=(640, 360),
        segmentation_backend=FakeSegmentation(),
    ).prepare(
        "event-vox",
        storyboard=storyboard,
        selected_assets={"scene_001": SimpleNamespace(path=str(image))},
        voice_durations_ms={"scene_001": 4200},
        store=store,
    )
    assert result.event_stage_ids == ["scene_001"]
    assert result.event_count == 3
    manifest = store.subdir("event-vox", "manifests") / "visual_events" / "scene_001.json"
    envelope = json.loads(manifest.read_text(encoding="utf-8"))
    assert envelope["kind"] == "visual_stage"
    assert envelope["style"]["motion_hash"] == "m" * 64
    assert [item["event_id"] for item in envelope["payload"]["events"]] == ["year", "spacex", "tesla"]
    assert all(item["persistent"] for item in envelope["payload"]["events"])
    event_assets = [item["asset"] for item in envelope["payload"]["events"]]
    assert len(set(event_assets)) == len(event_assets)
    assert all(Path(path).is_file() for path in event_assets)
    assert Path(envelope["event_assets_manifest"]).is_file()


def test_qt_and_cli_construct_one_canonical_semantic_renderer() -> None:
    qt = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    cli = Path("app/cli.py").read_text(encoding="utf-8-sig")
    assert "VoxSemanticSceneRenderer" in qt
    assert "VoxSemanticSceneRenderer" in cli
    assert "VoxAccumulatedSceneRenderer" not in qt
    assert "VoxAccumulatedSceneRenderer" not in cli
    assert "prepared.canonical_scenes" in qt
    assert "prepared.canonical_scenes" in cli
    assert "plan_canonical_visuals" in qt
    assert "plan_canonical_visuals" in cli
    assert "canonical_scenes.json" in Path("app/services/script_analysis.py").read_text(encoding="utf-8-sig")


def test_event_stage_derives_multiple_accumulating_clauses_without_named_entities() -> None:
    stage = build_scene_visual_stage(
        scene={
            "scene_id": "scene_002",
            "narration_text": (
                "Chiếc đồng hồ đã im lặng ba mươi năm. "
                "Người thợ mở nắp, kiểm tra bánh răng và lò xo."
            ),
        },
        duration_ms=5200,
        background="background.png",
        asset_roles={"background", "subject", "foreground", "texture"},
    )
    assert stage.event_count >= 3
    assert stage.events[0].start_ms == 0
    assert all(item.persistent for item in stage.events)


def test_raster_frame_retains_prior_events_after_later_trigger() -> None:
    stage = build_scene_visual_stage(
        scene={
            "scene_id": "scene_2008",
            "narration_text": "Năm 2008, SpaceX và Tesla khủng hoảng tiền mặt.",
            "canvas": {"width": 320, "height": 180},
            "visual_events": [
                {"event_id": "year", "trigger": "2008", "start_ms": 0, "duration_ms": 500, "asset": "year", "placement": "top_left", "enter": "popup"},
                {"event_id": "tesla", "trigger": "Tesla", "start_ms": 800, "duration_ms": 500, "asset": "tesla", "placement": "right", "enter": "popup"},
            ],
        },
        duration_ms=1800,
        background="background.png",
        asset_roles={"year", "tesla"},
    )
    background = Image.new("RGBA", (320, 180), (0, 0, 0, 255))
    year = Image.new("RGBA", (40, 30), (255, 0, 0, 255))
    tesla = Image.new("RGBA", (40, 30), (0, 255, 0, 255))
    frame = compose_visual_stage_frame(
        background,
        {"year": year, "tesla": tesla},
        stage,
        1400,
    )
    colors = set(frame.convert("RGB").getdata())
    assert (255, 0, 0) in colors
    assert (0, 255, 0) in colors
