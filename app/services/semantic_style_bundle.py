"""Render a provider-free multi-style VOX approval bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.services.final_composer import FinalComposer
from app.services.semantic_pilot import (
    DURATION_MS,
    FPS,
    HEIGHT,
    MOTION_FPS,
    WIDTH,
    _decode_or_raise,
    _sha256,
    _verify_scene,
    _write_json,
)
from app.services.semantic_scene_renderer import VoxSemanticSceneRenderer

STYLE_NAMES = (
    "cutout_character_story",
    "editorial_map_data",
    "archival_document_collage",
    "diagram_process_explainer",
)


def render_vox_style_bundle(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve() / "vox-style-approval-bundle"
    assets_dir = root / "assets"
    scenes_dir = root / "scenes"
    manifests = root / "manifests"
    review = root / "review"
    final_dir = root / "final"
    for directory in (assets_dir, scenes_dir, manifests, review, final_dir):
        directory.mkdir(parents=True, exist_ok=True)

    assets = _build_style_assets(assets_dir)
    plans = _build_style_plans(assets)
    renderer = VoxSemanticSceneRenderer()
    scene_paths: list[Path] = []
    style_rows: dict[str, dict[str, Any]] = {
        name: {"status": "PASS", "scenes": []} for name in STYLE_NAMES
    }
    for plan in plans:
        scene_id = str(plan["scene_id"])
        plan_path = manifests / f"{scene_id}.semantic.json"
        _write_json(plan_path, plan)
        output = renderer.render_plan(plan, scenes_dir / f"{scene_id}.mp4")
        row = _verify_scene(output, plan, review)
        row["style"] = plan["style"]
        row["plan"] = str(plan_path)
        row["plan_sha256"] = _sha256(plan_path)
        style_rows[str(plan["style"])]["scenes"].append(row)
        if row["status"] != "PASS":
            style_rows[str(plan["style"])]["status"] = "FAIL"
        scene_paths.append(output)

    final_path = final_dir / "vox-style-approval-reel.mp4"
    FinalComposer().compose(
        scene_paths,
        None,
        final_path,
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
        expected_duration_ms=DURATION_MS * len(scene_paths),
    )
    _decode_or_raise(final_path)
    status = "PASS" if all(row["status"] == "PASS" for row in style_rows.values()) else "FAIL"
    report = {
        "schema_version": "vox.semantic.style-bundle/1.0",
        "status": status,
        "renderer": renderer.renderer_name,
        "renderer_version": renderer.renderer_version,
        "provider_calls": 0,
        "style_count": len(style_rows),
        "scene_count": len(plans),
        "styles": style_rows,
        "final": {
            "path": str(final_path),
            "sha256": _sha256(final_path),
            "duration_ms": DURATION_MS * len(plans),
            "decode": "PASS",
        },
    }
    report_path = manifests / "style-bundle-qa.json"
    _write_json(report_path, report)
    if status != "PASS":
        raise RuntimeError("VOX style approval bundle QA failed")
    return {
        "renderer": renderer.renderer_name,
        "provider_calls": 0,
        "style_count": len(style_rows),
        "scene_count": len(plans),
        "final_mp4": str(final_path),
        "qa_report": str(report_path),
        "artifact_root": str(root),
    }


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/impact.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _save(root: Path, name: str, image: Image.Image) -> str:
    path = root / f"{name}.png"
    image.save(path)
    return str(path)


def _background(color: str, kicker: str, title: str, *, light: bool = True) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), color)
    draw = ImageDraw.Draw(image)
    ink = "#17191c" if light else "#f7f0df"
    draw.text((28, 20), kicker.upper(), font=_font(14), fill=ink)
    draw.text((28, 43), title.upper(), font=_font(29), fill=ink)
    draw.line((28, 82, 612, 82), fill="#d13b35", width=5)
    return image


def _cutout_person(shirt: str, pose: str) -> Image.Image:
    image = Image.new("RGBA", (190, 245), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((65, 8, 125, 68), fill="#dba074", outline="#17191c", width=4)
    draw.polygon(((48, 72), (142, 72), (160, 220), (30, 220)), fill=shirt, outline="#17191c")
    if pose == "point":
        draw.line((135, 100, 188, 50), fill="#17191c", width=18)
        draw.ellipse((174, 35, 190, 52), fill="#dba074")
    elif pose == "open":
        draw.line((50, 100, 3, 75), fill="#17191c", width=18)
        draw.line((138, 100, 185, 75), fill="#17191c", width=18)
    else:
        draw.line((50, 100, 20, 170), fill="#17191c", width=18)
        draw.line((138, 100, 170, 170), fill="#17191c", width=18)
    draw.ellipse((79, 28, 87, 36), fill="#17191c")
    draw.ellipse((106, 28, 114, 36), fill="#17191c")
    return image


def _build_style_assets(root: Path) -> dict[str, str]:
    assets: dict[str, str] = {}
    backgrounds = {
        "C01": ("#f0d5ba", "01 · CUTOUT STORY", "THE MACHINE DECIDES", True),
        "C02": ("#bdd8d2", "01 · CUTOUT STORY", "ONE CHOICE — TWO OUTCOMES", True),
        "M01": ("#d8d0b9", "02 · EDITORIAL MAP", "THE ROUTE THAT CHANGED IT", True),
        "M02": ("#142531", "02 · EDITORIAL DATA", "THE SPIKE NOBODY EXPECTED", False),
        "A01": ("#2c2926", "03 · ARCHIVAL COLLAGE", "THE RECEIPT TELLS THE STORY", False),
        "A02": ("#42342d", "03 · ARCHIVAL COLLAGE", "THREE CLUES — ONE CLAIM", False),
        "D01": ("#eef0eb", "04 · PROCESS DIAGRAM", "FROM INPUT TO VERDICT", True),
        "D02": ("#e4e9ef", "04 · SYSTEM EXPLAINER", "THREE PARTS — ONE SYSTEM", True),
    }
    for scene, (color, kicker, title, light) in backgrounds.items():
        assets[f"{scene}_background"] = _save(root, f"{scene}_background", _background(color, kicker, title, light=light))

    for name, shirt, pose in (
        ("person_neutral", "#263d67", "neutral"),
        ("person_point", "#263d67", "point"),
        ("person_open", "#a93131", "open"),
    ):
        assets[name] = _save(root, name, _cutout_person(shirt, pose))

    machine = Image.new("RGBA", (190, 135), (0, 0, 0, 0))
    draw = ImageDraw.Draw(machine)
    draw.rounded_rectangle((5, 10, 185, 130), 8, fill="#3b4148", outline="#17191c", width=5)
    draw.rectangle((35, 35, 155, 88), fill="#a7d3c8", outline="#17191c", width=3)
    draw.ellipse((83, 99, 108, 124), fill="#d13b35")
    assets["story_machine"] = _save(root, "story_machine", machine)

    marker = Image.new("RGBA", (34, 34), (0, 0, 0, 0))
    ImageDraw.Draw(marker).ellipse((3, 3, 31, 31), fill="#d13b35", outline="#fff6e8", width=3)
    assets["map_marker"] = _save(root, "map_marker", marker)

    map_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(map_layer)
    draw.polygon(((50, 255), (135, 110), (230, 145), (310, 105), (400, 185), (510, 120), (600, 205), (580, 320), (95, 325)), fill="#b5ad95", outline="#696253", width=3)
    for x, y, label in ((120, 245, "A"), (315, 185, "B"), (540, 170, "C")):
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#17191c")
        draw.text((x + 9, y - 12), label, font=_font(14), fill="#17191c")
    assets["map_layer"] = _save(root, "map_layer", map_layer)

    document = Image.new("RGBA", (430, 230), "#eee4cd")
    draw = ImageDraw.Draw(document)
    draw.rectangle((0, 0, 429, 229), outline="#17191c", width=3)
    draw.text((22, 15), "MEMORANDUM · 1974", font=_font(18), fill="#17191c")
    for y, width in ((62, 360), (91, 330), (120, 375), (149, 280), (178, 350)):
        draw.rectangle((25, y, 25 + width, y + 5), fill="#756b5d")
    assets["archive_document"] = _save(root, "archive_document", document)

    for index, color in enumerate(("#c59c6c", "#8798a8", "#b35c4b"), 1):
        card = Image.new("RGBA", (150, 105), "#f0e7d3")
        d = ImageDraw.Draw(card)
        d.rectangle((0, 0, 149, 104), outline="#17191c", width=3)
        d.rectangle((12, 12, 138, 72), fill=color)
        d.text((16, 79), f"EVIDENCE {index}", font=_font(13), fill="#17191c")
        assets[f"evidence_{index}"] = _save(root, f"evidence_{index}", card)

    for index, (label, color) in enumerate((("INPUT", "#477998"), ("CHECK", "#d19a38"), ("VERDICT", "#4d8a68")), 1):
        node = Image.new("RGBA", (145, 76), (0, 0, 0, 0))
        d = ImageDraw.Draw(node)
        d.rounded_rectangle((3, 3, 142, 73), 16, fill=color, outline="#17191c", width=3)
        d.text((25, 24), label, font=_font(18), fill="#ffffff")
        assets[f"node_{index}"] = _save(root, f"node_{index}", node)
    return assets


def _base(scene_id: str, style: str, grammar: str, assets: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "vox.semantic.plan/2",
        "scene_id": scene_id,
        "style": style,
        "grammar": grammar,
        "duration_ms": DURATION_MS,
        "fps": FPS,
        "motion_fps": MOTION_FPS,
        "canvas": {"width": WIDTH, "height": HEIGHT},
        "assets": {"background": assets[f"{scene_id}_background"]},
        "placements": {},
        "procedural_actions": [],
        "hold_windows": [{"start_ms": 1850, "end_ms": DURATION_MS, "purpose": "result_read"}],
    }


def _build_style_plans(a: dict[str, str]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    c1 = _base("C01", STYLE_NAMES[0], "character_demonstration", a)
    c1["assets"].update({k: a[k] for k in ("person_neutral", "person_point", "story_machine")})
    c1["placements"].update({"person_neutral": [52, 95], "person_point": [52, 95], "story_machine": [390, 155]})
    c1["procedural_actions"] = [
        {"type": "pose_sequence", "subject": "person_neutral", "variants": ["person_neutral", "person_point"], "start_ms": 260, "end_ms": 1120},
        {"type": "state_swap", "subject": "story_machine", "active_tint": "#e0b745", "start_ms": 920, "end_ms": 1450},
        {"type": "text_reveal", "text": "PRESS → REACTION → RESULT", "position": [328, 300], "font_size": 18, "start_ms": 1250, "end_ms": 1700, "color": "#17191c"},
    ]
    plans.append(c1)

    c2 = _base("C02", STYLE_NAMES[0], "comparison_split", a)
    c2["assets"].update({k: a[k] for k in ("person_neutral", "person_open", "evidence_1", "evidence_3")})
    c2["placements"].update({"person_neutral": [42, 100], "person_open": [42, 100]})
    c2["procedural_actions"] = [
        {"type": "pose_sequence", "subject": "person_neutral", "variants": ["person_neutral", "person_open"], "start_ms": 250, "end_ms": 900},
        {"type": "object_path", "subject": "evidence_1", "path": [[560, 305], [380, 190]], "start_ms": 450, "end_ms": 1300},
        {"type": "object_path", "subject": "evidence_3", "path": [[560, 70], [470, 190]], "start_ms": 650, "end_ms": 1500},
    ]
    plans.append(c2)

    m1 = _base("M01", STYLE_NAMES[1], "map_route", a)
    m1["assets"].update({"map_layer": a["map_layer"], "map_marker": a["map_marker"]})
    m1["placements"]["map_layer"] = [0, 0]
    route = [[120, 245], [205, 140], [315, 185], [430, 120], [540, 170]]
    m1["procedural_actions"] = [
        {"type": "path_draw", "subject": "map_marker", "path": route, "start_ms": 250, "end_ms": 1700, "color": "#d13b35", "width": 7},
        {"type": "traveling_marker", "subject": "map_marker", "path": route, "start_ms": 250, "end_ms": 1700},
    ]
    plans.append(m1)

    m2 = _base("M02", STYLE_NAMES[1], "chart_progression", a)
    m2["procedural_actions"] = [
        {"type": "chart_series", "values": [2, 3, 5, 4, 9, 7], "origin": [70, 310], "bar_width": 52, "gap": 31, "max_height": 205, "start_ms": 220, "end_ms": 1700, "color": "#5ea4c6"},
        {"type": "counter_progress", "from": 0, "to": 312, "suffix": "%", "position": [480, 105], "font_size": 36, "start_ms": 800, "end_ms": 1650, "color": "#f0c34e"},
        {"type": "text_reveal", "text": "PEAK", "position": [485, 158], "font_size": 16, "start_ms": 1450, "end_ms": 1750, "color": "#f7f0df"},
    ]
    plans.append(m2)

    a1 = _base("A01", STYLE_NAMES[2], "document_evidence", a)
    a1["assets"]["archive_document"] = a["archive_document"]
    a1["placements"]["archive_document"] = [105, 95]
    a1["procedural_actions"] = [
        {"type": "document_focus", "box": [127, 205, 515, 239], "start_ms": 650, "end_ms": 1550, "color": "#d13b35", "width": 7},
        {"type": "text_reveal", "text": "SOURCE / MEMO / LINE 3", "position": [395, 325], "font_size": 13, "start_ms": 1150, "end_ms": 1700, "color": "#f7f0df"},
    ]
    plans.append(a1)

    a2 = _base("A02", STYLE_NAMES[2], "archival_bridge", a)
    a2["assets"].update({f"evidence_{i}": a[f"evidence_{i}"] for i in range(1, 4)})
    a2["procedural_actions"] = [
        {"type": "object_path", "subject": "evidence_1", "path": [[-70, 130], [80, 135]], "start_ms": 150, "end_ms": 900},
        {"type": "object_path", "subject": "evidence_2", "path": [[320, 370], [245, 180]], "start_ms": 400, "end_ms": 1200},
        {"type": "object_path", "subject": "evidence_3", "path": [[700, 115], [415, 135]], "start_ms": 650, "end_ms": 1450},
        {"type": "text_reveal", "text": "CORROBORATED", "position": [225, 300], "font_size": 25, "start_ms": 1450, "end_ms": 1750, "color": "#f0c34e"},
    ]
    plans.append(a2)

    d1 = _base("D01", STYLE_NAMES[3], "process_flow", a)
    d1["assets"].update({f"node_{i}": a[f"node_{i}"] for i in range(1, 4)})
    d1["procedural_actions"] = [
        {"type": "object_path", "subject": "node_1", "path": [[-80, 185], [142, 185]], "start_ms": 150, "end_ms": 750},
        {"type": "object_path", "subject": "node_2", "path": [[320, 420], [322, 185]], "start_ms": 500, "end_ms": 1150},
        {"type": "object_path", "subject": "node_3", "path": [[720, 185], [502, 185]], "start_ms": 850, "end_ms": 1500},
        {"type": "path_draw", "subject": "connector_1", "path": [[215, 185], [250, 185]], "start_ms": 760, "end_ms": 1120, "color": "#17191c", "width": 5},
        {"type": "path_draw", "subject": "connector_2", "path": [[395, 185], [430, 185]], "start_ms": 1160, "end_ms": 1520, "color": "#17191c", "width": 5},
    ]
    plans.append(d1)

    d2 = _base("D02", STYLE_NAMES[3], "object_assembly", a)
    d2["assets"].update({f"node_{i}": a[f"node_{i}"] for i in range(1, 4)})
    d2["procedural_actions"] = [
        {"type": "object_path", "subject": "node_1", "path": [[75, 315], [245, 205]], "start_ms": 180, "end_ms": 1100},
        {"type": "object_path", "subject": "node_2", "path": [[495, 315], [320, 205]], "start_ms": 350, "end_ms": 1250},
        {"type": "object_path", "subject": "node_3", "path": [[320, 70], [395, 205]], "start_ms": 520, "end_ms": 1450},
        {"type": "text_reveal", "text": "SYSTEM READY", "position": [238, 300], "font_size": 24, "start_ms": 1500, "end_ms": 1800, "color": "#245b45"},
    ]
    plans.append(d2)
    return plans


__all__ = ["render_vox_style_bundle"]
