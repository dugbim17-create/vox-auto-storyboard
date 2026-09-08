from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.layer_workflow import LayerWorkflow
from app.services.motion_templates import build_template
from app.services.vox_scene_planner import plan_vox_scene
from app.storage.asset_store import AssetStore


class CenterSubjectBackend:
    def produce_mask(self, image: Image.Image) -> Image.Image:
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle((80, 30, 175, 215), fill=255)
        return mask


class EmptyMaskBackend:
    def produce_mask(self, image: Image.Image) -> Image.Image:
        return Image.new("L", image.size, 0)


def _composite(path: Path) -> Path:
    image = Image.new("RGB", (256, 256), "#d9c7a2")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 30, 175, 215), fill="#242424")
    draw.ellipse((100, 50, 155, 105), fill="#ddd0b8")
    image.save(path)
    return path


def test_vox_prepare_requires_a_real_alpha_subject_and_removed_background(tmp_path: Path) -> None:
    source = _composite(tmp_path / "source.png")
    store = AssetStore(tmp_path / "projects")
    store.init_project("vox")

    result = LayerWorkflow(
        canvas_width=256,
        canvas_height=256,
        project_root=store.base,
        segmentation_backend=CenterSubjectBackend(),
    ).prepare_composite("vox", "scene_001", str(source), store=store, require_subject=True)

    assert result.ok is True
    by_role = {layer.role: Path(layer.path) for layer in result.layers}
    assert set(by_role) == {"background", "subject"}
    with Image.open(by_role["subject"]) as subject:
        assert subject.mode == "RGBA"
        assert subject.getchannel("A").getextrema() == (0, 255)
    with Image.open(by_role["background"]) as background:
        center = background.convert("RGB").getpixel((128, 150))
    with Image.open(source) as original:
        original_center = original.convert("RGB").getpixel((128, 150))
    assert center != original_center

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["strategy"] == "segmented_composite"
    assert manifest["subject_found"] is True
    assert 0 < manifest["subject_coverage"] < 1


def test_vox_prepare_fails_closed_when_subject_cannot_be_separated(tmp_path: Path) -> None:
    source = _composite(tmp_path / "source.png")
    store = AssetStore(tmp_path / "projects")
    store.init_project("vox")

    result = LayerWorkflow(
        canvas_width=256,
        canvas_height=256,
        project_root=store.base,
        segmentation_backend=EmptyMaskBackend(),
    ).prepare_composite("vox", "scene_001", str(source), store=store, require_subject=True)

    assert result.ok is False
    assert "subject separation required" in result.error


def test_vox_scene_planner_uses_valid_templates_and_never_emits_placeholders() -> None:
    cases = {
        "opening": "09_cutout_parallax",
        "object_detail": "11_object_zoom_texture_wipe",
        "evidence": "07_document_highlight",
        "arrival": "02_subject_float_label_reveal",
        "handoff": "01_subject_slide_headline_pop",
        "conclusion": "12_conclusion_lockup",
    }
    for purpose, expected in cases.items():
        scene = plan_vox_scene(
            scene_id="scene_001",
            narration="Chiếc đồng hồ được đánh thức.",
            purpose=purpose,
            duration_ms=5000,
            canvas_size=(1920, 1080),
            available_roles=frozenset({"background", "subject", "foreground", "texture"}),
        )
        assert scene.template_name == expected
        raw = build_template(expected, "scene_001", 5000, canvas_size=(1920, 1080))
        forbidden = {"HEADLINE", "LABEL", "MARKER", "BEFORE", "AFTER", "TIMELINE", "HIGHLIGHT", "42"}
        text_values = {item["text"] for item in raw.get("text_animations", [])}
        assert text_values.isdisjoint(forbidden)
        assert len({layer["asset_role"] for layer in raw["layers"]}) >= 2


def test_vox_scene_planner_supplies_authored_text_only_when_requested() -> None:
    scene = plan_vox_scene(
        scene_id="scene_001",
        narration="Thời gian không quay lại.",
        purpose="conclusion",
        duration_ms=5000,
        canvas_size=(1920, 1080),
        available_roles=frozenset({"background", "subject", "foreground", "texture"}),
        authored_text="KÝ ỨC THỨC GIẤC",
    )
    assert [item["text"] for item in scene.plan["text_animations"]] == ["KÝ ỨC THỨC GIẤC"]

    silent = plan_vox_scene(
        scene_id="scene_002",
        narration="Một cảnh không có title.",
        purpose="opening",
        duration_ms=5000,
        canvas_size=(1920, 1080),
        available_roles=frozenset({"background", "subject"}),
    )
    assert silent.plan["text_animations"] == []
