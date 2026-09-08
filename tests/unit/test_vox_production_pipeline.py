from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.services.vox_production_pipeline import VoxProductionPipeline
from app.storage.asset_store import AssetStore


def _selected_composite(path: Path) -> Path:
    image = Image.new("RGB", (640, 360), "#cdbb91")
    draw = ImageDraw.Draw(image)
    draw.rectangle((210, 55, 430, 350), fill="#23262a")
    draw.ellipse((250, 20, 390, 160), fill="#dac5aa")
    image.save(path)
    return path


class FakeSegmentation:
    def produce_mask(self, image: Image.Image) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle((210, 55, 430, 350), fill=255)
        draw.ellipse((250, 20, 390, 160), fill=255)
        return mask


def _storyboard(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "style_snapshot": {
            "visual_hash": "v" * 64,
            "motion_hash": "m" * 64,
            "render_theme_hash": "r" * 64,
        },
        "scenes": [
            {
                "scene_id": "scene_001",
                "order": 1,
                "purpose": "opening",
                "narration_text": "Mỗi sáng, người thợ mở cửa tiệm đồng hồ cuối phố.",
                "visual_summary": "Người thợ mở cửa tiệm.",
            },
            {
                "scene_id": "scene_002",
                "order": 2,
                "purpose": "conclusion",
                "narration_text": "Thời gian không quay lại, nhưng ký ức có thể được đánh thức.",
                "visual_summary": "Hai người nhìn chiếc đồng hồ đã chạy lại.",
            },
        ],
    }


def test_production_pipeline_builds_vox_packs_and_lineage_motion(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    store.init_project("vox")
    store.write_manifest("vox", "storyboard.json", _storyboard("vox"))
    composite = _selected_composite(tmp_path / "composite.png")
    selected = {
        "scene_001": SimpleNamespace(path=str(composite)),
        "scene_002": SimpleNamespace(path=str(composite)),
    }
    durations = {"scene_001": 4800, "scene_002": 7100}

    result = VoxProductionPipeline(
        project_root=store.base,
        canvas_size=(640, 360),
        fps=30,
        segmentation_backend=FakeSegmentation(),
    ).prepare(
        "vox",
        storyboard=_storyboard("vox"),
        selected_assets=selected,
        voice_durations_ms=durations,
        store=store,
    )

    assert result.scene_ids == ["scene_001", "scene_002"]
    assert result.visual_change_budget >= 6
    assert result.median_change_interval_ms <= 2000
    for scene_id in result.scene_ids:
        pack_path = store.subdir("vox", "manifests") / f"vox_asset_pack_{scene_id}.json"
        motion_path = store.subdir("vox", "manifests") / "motion" / f"{scene_id}.json"
        assert pack_path.is_file()
        assert motion_path.is_file()
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        assert pack["roles"] == ["background", "subject", "foreground", "texture"]
        motion = json.loads(motion_path.read_text(encoding="utf-8"))
        assert motion["kind"] == "motion_plan"
        payload = motion["payload"]
        assert payload["motion_fps"] == 12
        assert len(payload["layers"]) == 4
        assert all(item["text"] != "HEADLINE" for item in payload["text_animations"])


def test_production_pipeline_rejects_composite_fallback(tmp_path: Path) -> None:
    class EmptySegmentation:
        def produce_mask(self, image: Image.Image) -> Image.Image:
            return Image.new("L", image.size, 0)

    store = AssetStore(tmp_path / "projects")
    store.init_project("vox")
    composite = _selected_composite(tmp_path / "composite.png")
    selected = {
        "scene_001": SimpleNamespace(path=str(composite)),
        "scene_002": SimpleNamespace(path=str(composite)),
    }
    try:
        VoxProductionPipeline(
            project_root=store.base,
            canvas_size=(640, 360),
            fps=30,
            segmentation_backend=EmptySegmentation(),
        ).prepare(
            "vox",
            storyboard=_storyboard("vox"),
            selected_assets=selected,
            voice_durations_ms={"scene_001": 4800, "scene_002": 7100},
            store=store,
        )
    except RuntimeError as exc:
        assert "subject separation required" in str(exc)
    else:
        raise AssertionError("VOX production must fail closed on composite fallback")


def test_qt_and_cli_route_production_render_through_vox_pipeline() -> None:
    qt_source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    cli_source = Path("app/cli.py").read_text(encoding="utf-8-sig")
    assert "VoxProductionPipeline" in qt_source
    assert "VoxProductionPipeline" in cli_source
    assert "require_subject=True" not in qt_source  # encapsulated in the shared pipeline
    assert "require_subject=True" not in cli_source
    assert "MotionPlannerService()" not in cli_source
    render_block = qt_source[qt_source.index("async def _render_final_async") :]
    assert "MotionPlannerService" not in render_block
    assert "prepare_composite" not in render_block
