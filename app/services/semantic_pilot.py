"""Provider-free six-scene semantic-motion acceptance pilot."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.services.final_composer import FinalComposer
from app.services.semantic_scene_renderer import VoxSemanticSceneRenderer

WIDTH = 640
HEIGHT = 360
FPS = 30
MOTION_FPS = 12
DURATION_MS = 2400


def render_semantic_pilot(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).resolve() / "semantic-v061-pilot"
    assets = root / "assets"
    scenes_dir = root / "scenes"
    manifests = root / "manifests"
    review = root / "review"
    final_dir = root / "final"
    for directory in (assets, scenes_dir, manifests, review, final_dir):
        directory.mkdir(parents=True, exist_ok=True)
    local_assets = _build_assets(assets)
    plans = _build_plans(local_assets)
    renderer = VoxSemanticSceneRenderer()
    scene_paths: list[Path] = []
    scene_rows: list[dict[str, Any]] = []
    for plan in plans:
        scene_id = str(plan["scene_id"])
        plan_path = manifests / f"{scene_id}.semantic.json"
        _write_json(plan_path, plan)
        output = renderer.render_plan(plan, scenes_dir / f"{scene_id}.mp4")
        row = _verify_scene(output, plan, review)
        row["plan"] = str(plan_path)
        row["plan_sha256"] = _sha256(plan_path)
        scene_rows.append(row)
        scene_paths.append(output)
    final_path = final_dir / "semantic-pilot-final.mp4"
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
    report = {
        "schema_version": "vox.semantic.qa/1.0",
        "status": "PASS" if all(row["status"] == "PASS" for row in scene_rows) else "FAIL",
        "renderer": renderer.renderer_name,
        "renderer_version": renderer.renderer_version,
        "scene_count": len(scene_rows),
        "scenes": scene_rows,
        "final": {
            "path": str(final_path),
            "sha256": _sha256(final_path),
            "duration_ms": DURATION_MS * len(scene_rows),
            "decode": "PASS",
        },
        "provider_calls": 0,
    }
    report_path = manifests / "semantic-qa.json"
    _write_json(report_path, report)
    if report["status"] != "PASS":
        raise RuntimeError("semantic pilot QA failed")
    return {
        "renderer": renderer.renderer_name,
        "provider_calls": 0,
        "scenes": [str(path) for path in scene_paths],
        "final_mp4": str(final_path),
        "qa_report": str(report_path),
        "artifact_root": str(root),
    }


def _build_assets(root: Path) -> dict[str, str]:
    files: dict[str, Image.Image] = {}
    for scene, color in {
        "P01": "#eadfc7", "P02": "#dce7e5", "P03": "#d9d2bf",
        "P04": "#f2ead8", "P05": "#26313a", "P06": "#e9e0cb",
    }.items():
        background = Image.new("RGBA", (WIDTH, HEIGHT), color)
        draw = ImageDraw.Draw(background)
        draw.text((32, 22), f"{scene}  SEMANTIC PILOT", fill="#161616" if scene != "P05" else "#ffffff")
        files[f"{scene}_background"] = background
    neutral = Image.new("RGBA", (150, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(neutral)
    draw.ellipse((52, 8, 98, 54), fill="#e5aa79", outline="#161616", width=3)
    draw.rectangle((45, 54, 105, 190), fill="#2d3f67")
    draw.line((52, 80, 20, 145), fill="#161616", width=14)
    draw.line((98, 80, 128, 145), fill="#161616", width=14)
    files["character_neutral"] = neutral
    operate = neutral.copy()
    draw = ImageDraw.Draw(operate)
    draw.line((98, 82, 148, 102), fill="#cf2637", width=15)
    draw.ellipse((139, 93, 153, 107), fill="#e5aa79")
    files["character_operate"] = operate
    machine = Image.new("RGBA", (180, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(machine)
    draw.rounded_rectangle((10, 20, 170, 140), 12, fill="#59616b", outline="#161616", width=4)
    draw.ellipse((68, 60, 112, 104), fill="#20262d")
    files["machine"] = machine
    for index, color in enumerate(("#cf2637", "#2f6690", "#e5a126"), 1):
        part = Image.new("RGBA", (70, 70), (0, 0, 0, 0))
        ImageDraw.Draw(part).rounded_rectangle((4, 4, 66, 66), 10, fill=color, outline="#161616", width=3)
        files[f"part_{index}"] = part
    marker = Image.new("RGBA", (26, 26), (0, 0, 0, 0))
    ImageDraw.Draw(marker).ellipse((2, 2, 24, 24), fill="#cf2637", outline="#ffffff", width=2)
    files["route_marker"] = marker
    document = Image.new("RGBA", (440, 250), "#f8f4e8")
    draw = ImageDraw.Draw(document)
    draw.rectangle((0, 0, 439, 249), outline="#161616", width=3)
    draw.text((24, 20), "SOURCE RECORD", fill="#161616")
    for y in (65, 95, 125, 155, 185):
        draw.line((24, y, 410, y), fill="#777777", width=4)
    files["document"] = document
    result: dict[str, str] = {}
    for name, image in files.items():
        path = root / f"{name}.png"
        image.save(path)
        result[name] = str(path)
    return result


def _base(scene_id: str, grammar: str, assets: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "vox.semantic.plan/2",
        "scene_id": scene_id,
        "grammar": grammar,
        "duration_ms": DURATION_MS,
        "fps": FPS,
        "motion_fps": MOTION_FPS,
        "canvas": {"width": WIDTH, "height": HEIGHT},
        "assets": {"background": assets[f"{scene_id}_background"]},
        "placements": {},
        "procedural_actions": [],
        "hold_windows": [{"start_ms": 1850, "end_ms": 2400, "purpose": "result_read"}],
    }


def _build_plans(assets: dict[str, str]) -> list[dict[str, Any]]:
    p1 = _base("P01", "character_demonstration", assets)
    p1["assets"].update({key: assets[key] for key in ("character_neutral", "character_operate", "machine")})
    p1["placements"].update({"character_neutral": [70, 95], "character_operate": [70, 95], "machine": [380, 145]})
    p1["procedural_actions"] = [
        {"action_id": "pose", "type": "pose_sequence", "subject": "character_neutral", "variants": ["character_neutral", "character_operate"], "start_ms": 350, "end_ms": 1250},
        {"action_id": "machine_on", "type": "state_swap", "subject": "machine", "active_tint": "#f1c54a", "start_ms": 1050, "end_ms": 1550},
    ]
    p2 = _base("P02", "object_assembly", assets)
    p2["assets"].update({key: assets[key] for key in ("part_1", "part_2", "part_3")})
    paths = [
        [[60, 120], [280, 190]], [[580, 100], [350, 190]], [[320, 320], [320, 205]],
    ]
    p2["procedural_actions"] = [
        {"action_id": f"part_{index}", "type": "object_path", "subject": f"part_{index}", "path": path, "start_ms": 200 + index * 120, "end_ms": 1550 + index * 80}
        for index, path in enumerate(paths, 1)
    ]
    p3 = _base("P03", "map_route", assets)
    p3["assets"]["route_marker"] = assets["route_marker"]
    route = [[70, 275], [220, 100], [390, 185], [560, 80]]
    p3["procedural_actions"] = [
        {"action_id": "route", "type": "path_draw", "subject": "route_marker", "path": route, "start_ms": 200, "end_ms": 1750, "color": "#161616", "width": 8},
        {"action_id": "marker", "type": "traveling_marker", "subject": "route_marker", "path": route, "start_ms": 200, "end_ms": 1750},
    ]
    p4 = _base("P04", "chart_progression", assets)
    p4["procedural_actions"] = [
        {"action_id": "series", "type": "chart_series", "values": [2, 5, 8, 4, 7], "origin": [120, 300], "bar_width": 58, "gap": 34, "max_height": 210, "start_ms": 250, "end_ms": 1800, "color": "#2f6690"},
        {"action_id": "count", "type": "counter_progress", "from": 0, "to": 8, "suffix": "x", "position": [500, 65], "start_ms": 650, "end_ms": 1650, "font_size": 26, "color": "#cf2637"},
    ]
    p5 = _base("P05", "document_evidence", assets)
    p5["assets"]["document"] = assets["document"]
    p5["placements"]["document"] = [100, 70]
    p5["procedural_actions"] = [
        {"action_id": "focus", "type": "document_focus", "box": [125, 177, 515, 215], "start_ms": 700, "end_ms": 1600, "color": "#cf2637", "width": 7},
        {"action_id": "citation", "type": "text_reveal", "text": "SOURCE: LOCAL FIXTURE / LINE 3", "position": [185, 328], "start_ms": 1050, "end_ms": 1800, "font_size": 14, "color": "#f8f4e8"},
    ]
    p6 = _base("P06", "explanatory_hold", assets)
    p6["assets"]["machine"] = assets["machine"]
    p6["placements"]["machine"] = [230, 115]
    p6["procedural_actions"] = [
        {"action_id": "state", "type": "state_swap", "subject": "machine", "active_tint": "#55a36f", "start_ms": 550, "end_ms": 1000},
        {"action_id": "label", "type": "text_reveal", "text": "RESULT STATE — HOLD TO EXPLAIN", "position": [120, 292], "start_ms": 750, "end_ms": 1200, "font_size": 22, "color": "#161616"},
    ]
    p6["hold_windows"] = [{"start_ms": 1200, "end_ms": 2400, "purpose": "explanation_read", "focus": "machine"}]
    return [p1, p2, p3, p4, p5, p6]


def _verify_scene(path: Path, plan: dict[str, Any], review: Path) -> dict[str, Any]:
    probe = _probe(path)
    _decode_or_raise(path)
    samples = _sample_frames(path, [0.2, 0.9, 1.7, 2.2])
    deltas = [float(np.mean(cv2.absdiff(left, right))) for left, right in zip(samples, samples[1:], strict=False)]
    action_delta = max(deltas[:2]) if deltas else 0.0
    hold_delta = deltas[-1] if deltas else 0.0
    status = "PASS" if action_delta >= 0.35 else "FAIL"
    sheet_path = review / f"{plan['scene_id']}_dense.jpg"
    rgb = [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for frame in samples]
    sheet = Image.new("RGB", (WIDTH * len(rgb), HEIGHT), "white")
    for index, frame in enumerate(rgb):
        sheet.paste(Image.fromarray(frame), (index * WIDTH, 0))
    sheet.save(sheet_path, quality=88)
    return {
        "scene_id": plan["scene_id"],
        "grammar": plan["grammar"],
        "status": status,
        "path": str(path),
        "sha256": _sha256(path),
        "probe": probe,
        "decode": "PASS",
        "action_delta": round(action_delta, 4),
        "hold_delta": round(hold_delta, 4),
        "hold_policy": plan.get("hold_windows") or [],
        "dense_sheet": str(sheet_path),
    }


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,pix_fmt,avg_frame_rate:format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "pix_fmt": stream["pix_fmt"],
        "avg_frame_rate": stream["avg_frame_rate"],
        "duration_ms": round(float(payload["format"]["duration"]) * 1000),
    }


def _decode_or_raise(path: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, check=True)


def _sample_frames(path: Path, seconds: list[float]) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(path))
    frames: list[np.ndarray] = []
    try:
        for second in seconds:
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError(f"cannot sample {path} at {second}s")
            frames.append(frame)
    finally:
        capture.release()
    return frames


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ["render_semantic_pilot"]
