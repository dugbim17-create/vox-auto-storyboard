from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.schemas.visual_events import build_visual_stage
from app.services.visual_event_assets import materialize_visual_event_assets


def test_event_assets_are_distinct_content_bearing_rgba_files(tmp_path: Path) -> None:
    stage = build_visual_stage(
        {
            "stage_id": "crisis_2008",
            "narration": "Năm 2008, SpaceX và Tesla khủng hoảng tiền mặt.",
            "duration_ms": 2200,
            "background": str(tmp_path / "background.png"),
            "canvas": {"width": 640, "height": 360},
            "events": [
                {
                    "event_id": "year",
                    "trigger": "Năm 2008",
                    "start_ms": 0,
                    "duration_ms": 800,
                    "asset": "foreground",
                    "placement": "top_left",
                    "enter": "counter",
                },
                {
                    "event_id": "tesla",
                    "trigger": "Tesla",
                    "start_ms": 700,
                    "duration_ms": 1000,
                    "asset": "foreground",
                    "placement": "right",
                    "enter": "popup",
                },
            ],
        }
    )
    foreground = tmp_path / "foreground.png"
    Image.new("RGBA", (640, 360), (0, 0, 0, 0)).save(foreground)
    result = materialize_visual_event_assets(
        stage,
        role_assets={"foreground": str(foreground)},
        output_dir=tmp_path / "event-assets",
    )
    assert set(result) == {"year", "tesla", "_manifest"}
    assert result["year"] != result["tesla"]
    for key, path in result.items():
        if key == "_manifest":
            continue
        image = Image.open(path).convert("RGBA")
        assert image.getchannel("A").getbbox() is not None
        assert image.size[0] <= 920
        assert image.size[1] <= 520


def test_event_asset_manifest_records_sha256_and_triggers(tmp_path: Path) -> None:
    stage = build_visual_stage(
        {
            "stage_id": "one",
            "narration": "Một dữ kiện.",
            "duration_ms": 1000,
            "background": str(tmp_path / "background.png"),
            "events": [
                {
                    "event_id": "fact",
                    "trigger": "Dữ kiện thật",
                    "start_ms": 0,
                    "duration_ms": 800,
                    "asset": "foreground",
                    "placement": "center",
                }
            ],
        }
    )
    foreground = tmp_path / "foreground.png"
    Image.new("RGBA", (640, 360), (0, 0, 0, 0)).save(foreground)
    result = materialize_visual_event_assets(
        stage,
        role_assets={"foreground": str(foreground)},
        output_dir=tmp_path / "event-assets",
    )
    manifest = json.loads(Path(result["_manifest"]).read_text(encoding="utf-8"))
    assert manifest["kind"] == "visual_event_assets"
    assert manifest["events"][0]["trigger"] == "Dữ kiện thật"
    assert len(manifest["events"][0]["sha256"]) == 64
