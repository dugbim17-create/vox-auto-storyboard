from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.vox_asset_pack import (
    VoxAssetPackBuilder,
    derive_vox_beat,
    semantic_purpose,
    validate_vox_asset_pack,
)
from app.services.vox_scene_planner import plan_vox_scene
from app.storage.asset_store import AssetStore


def _rgba_subject(path: Path) -> Path:
    image = Image.new("RGBA", (320, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((110, 25, 210, 125), fill=(220, 190, 160, 255))
    draw.rectangle((95, 110, 225, 235), fill=(28, 35, 42, 255))
    image.save(path)
    return path


def _background(path: Path) -> Path:
    image = Image.new("RGB", (640, 360), "#c9b58b")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 620, 340), outline="#4b4032", width=8)
    image.save(path)
    return path


def test_semantic_beat_derives_authored_keyword_and_meaningful_assets() -> None:
    beat = derive_vox_beat(
        scene_id="scene_003",
        narration=(
            "Ông kiên nhẫn làm sạch từng bánh răng, thay một chiếc lò xo mảnh "
            "và khẽ lên dây cót."
        ),
        purpose="evidence",
        order=3,
    )

    assert beat.visual_function == "evidence"
    assert beat.keyword == "TỪNG BÁNH RĂNG"
    assert beat.accent_kind == "evidence"
    assert beat.accent_labels
    assert beat.accent_labels == ("BÁNH RĂNG", "LÒ XO")
    assert "HEADLINE" not in json.dumps(beat.to_dict(), ensure_ascii=False)


def test_builder_creates_content_bearing_pack_and_readback_manifest(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    store.init_project("vox")
    subject = _rgba_subject(tmp_path / "subject.png")
    background = _background(tmp_path / "background.png")
    beat = derive_vox_beat(
        scene_id="scene_003",
        narration="Ông làm sạch từng bánh răng và thay chiếc lò xo mảnh.",
        purpose="evidence",
        order=3,
    )

    result = VoxAssetPackBuilder(
        canvas_size=(640, 360),
        project_root=store.base,
    ).build(
        "vox",
        beat,
        background_path=background,
        subject_path=subject,
        store=store,
    )

    assert result.ok is True
    assert set(result.assets) == {"background", "subject", "foreground", "texture"}
    for path in result.assets.values():
        assert Path(path).is_file()
        assert Path(path).stat().st_size > 0
    with Image.open(result.assets["foreground"]) as foreground:
        assert foreground.mode == "RGBA"
        assert foreground.getchannel("A").getextrema() == (0, 255)
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["kind"] == "vox_asset_pack"
    assert manifest["beat"]["keyword"] == beat.keyword
    assert manifest["beat"]["accent_labels"] == list(beat.accent_labels)
    assert manifest["roles"] == ["background", "subject", "foreground", "texture"]
    assert validate_vox_asset_pack(manifest, expected_scene_id="scene_003") == manifest


def test_asset_pack_is_deterministic_for_same_semantic_inputs(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    store.init_project("vox")
    subject = _rgba_subject(tmp_path / "subject.png")
    background = _background(tmp_path / "background.png")
    beat = derive_vox_beat(
        scene_id="scene_001",
        narration="Mỗi sáng, người thợ mở cửa tiệm đồng hồ cuối phố.",
        purpose="opening",
        order=1,
    )
    builder = VoxAssetPackBuilder(canvas_size=(640, 360), project_root=store.base)

    first = builder.build("vox", beat, background_path=background, subject_path=subject, store=store)
    hashes_first = dict(first.sha256_by_role)
    second = builder.build("vox", beat, background_path=background, subject_path=subject, store=store)

    assert second.sha256_by_role == hashes_first


def test_scene_plan_uses_asset_pack_roles_and_benchmark_cadence() -> None:
    beat = derive_vox_beat(
        scene_id="scene_006",
        narration="Thời gian không quay lại, nhưng ký ức có thể được đánh thức.",
        purpose="conclusion",
        order=6,
    )
    scene = plan_vox_scene(
        scene_id=beat.scene_id,
        narration=beat.narration,
        purpose=beat.visual_function,
        duration_ms=8000,
        canvas_size=(1920, 1080),
        available_roles=frozenset({"background", "subject", "foreground", "texture"}),
        authored_text=beat.keyword,
    )

    roles = {layer["asset_role"] for layer in scene.plan["layers"]}
    assert roles == {"background", "subject", "foreground", "texture"}
    assert scene.plan["text_animations"][0]["text"] == beat.keyword
    assert scene.plan["text_animations"][0]["end_ms"] - scene.plan["text_animations"][0]["start_ms"] <= 2200
    assert scene.plan["motion_fps"] == 12
    animated_channels = sum(
        bool(layer.get("transform")) for layer in scene.plan["layers"]
    )
    assert animated_channels >= 3
    assert scene.plan["transition_in"] == "none"
    assert scene.plan["transition_out"] == "hard_cut"


def test_handoff_and_arrival_win_over_generic_evidence_words() -> None:
    handoff = derive_vox_beat(
        scene_id="scene_005",
        narration="Bà mỉm cười, nhận ra kỷ vật của cha mình.",
        purpose="handoff",
        order=5,
    )
    arrival = derive_vox_beat(
        scene_id="scene_004",
        narration="Tích tắc vang lên khi người phụ nữ bước vào.",
        purpose="arrival",
        order=4,
    )
    assert handoff.accent_labels == ("KỶ VẬT", "CHA CỦA BÀ")
    assert arrival.accent_labels == ("TÍCH TẮC", "NGƯỜI PHỤ NỮ")


def test_opening_and_conclusion_labels_are_audience_copy_not_debug_taxonomy() -> None:
    opening = derive_vox_beat(
        scene_id="scene_001",
        narration="Người thợ sửa đồng hồ mở cửa tiệm nhỏ cuối phố.",
        purpose="opening",
        order=1,
    )
    conclusion = derive_vox_beat(
        scene_id="scene_006",
        narration="Thời gian không quay lại, nhưng ký ức có thể được đánh thức.",
        purpose="conclusion",
        order=6,
    )
    assert opening.accent_labels == ("TIỆM CUỐI PHỐ", "NGƯỜI THỢ")
    assert conclusion.accent_labels == ("KHÔNG QUAY LẠI", "ĐƯỢC ĐÁNH THỨC")


def test_scene_plan_never_begins_with_all_content_layers_invisible() -> None:
    scene = plan_vox_scene(
        scene_id="scene_006",
        narration="Ký ức có thể được đánh thức.",
        purpose="conclusion",
        duration_ms=8000,
        canvas_size=(1920, 1080),
        available_roles=frozenset({"background", "subject", "foreground", "texture"}),
        authored_text="KÝ ỨC THỨC GIẤC",
    )
    content_layers = [
        layer for layer in scene.plan["layers"]
        if layer["asset_role"] in {"subject", "foreground"}
    ]
    initial_opacities = []
    for layer in content_layers:
        opacity = (layer.get("transform") or {}).get("opacity")
        if opacity:
            initial_opacities.append(float(opacity["keyframes"][0][1]))
        else:
            initial_opacities.append(1.0)
    assert max(initial_opacities) >= 0.65


def test_storyboard_body_scenes_are_classified_from_narration_semantics() -> None:
    arrival = {
        "purpose": "body",
        "narration_text": "Tích tắc vang lên khi một người phụ nữ bước vào.",
    }
    handoff = {
        "purpose": "body",
        "narration_text": "Bà nhận ra kỷ vật của cha mình.",
    }
    object_detail = {
        "purpose": "body",
        "narration_text": "Chiếc đồng hồ đã im lặng suốt ba mươi năm.",
    }
    assert semantic_purpose(arrival, order=4, total=6) == "arrival"
    assert semantic_purpose(handoff, order=5, total=6) == "handoff"
    assert semantic_purpose(object_detail, order=2, total=6) == "object_detail"


def test_validator_rejects_decorative_or_placeholder_pack() -> None:
    payload = {
        "kind": "vox_asset_pack",
        "scene_id": "scene_001",
        "roles": ["background", "subject", "foreground", "texture"],
        "beat": {
            "keyword": "HEADLINE",
            "accent_kind": "decorative",
            "accent_labels": [],
        },
        "assets": {},
    }
    try:
        validate_vox_asset_pack(payload, expected_scene_id="scene_001")
    except ValueError as exc:
        assert "placeholder" in str(exc) or "content-bearing" in str(exc)
    else:
        raise AssertionError("decorative placeholder pack must be rejected")
