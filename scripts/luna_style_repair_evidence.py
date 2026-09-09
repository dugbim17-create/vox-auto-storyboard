from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw

from app.services.quiz_channel_renderer import render as render_channel
from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2, get_font
from app.services.quiz_style_evidence import write_preview_evidence
from app.services.quiz_style_packs import STYLE_IDS, resolve_style_snapshot
from app.services.quiz_v2_runtime import content_fingerprint, require_review


def question() -> dict:
    return {
        "id": "q1",
        "question": "Which explanation fits the runway numbering rule?",
        "choices": [
            {"id": "A", "text": "Magnetic heading"},
            {"id": "B", "text": "Opening year"},
        ],
        "correct_id": "A",
        "answer_text": "Magnetic heading",
        "explanation_text": "Runway numbers follow magnetic heading.",
        "difficulty": "medium",
        "countdown_seconds": 3.5,
    }


def event() -> dict:
    return {
        "idx": 1,
        "total_q": 1,
        "q_start": 0,
        "cd_start": 2,
        "cd_dur": 6,
        "rev_start": 8,
        "rev_dur": 4,
        "data": question(),
    }


def document(style: dict | None, *, profile: str = "de-wissen") -> dict:
    payload = {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Luna repair evidence",
        "language": "en-US",
        "questions": [question()],
    }
    if profile:
        payload["channel_profile"] = profile
    if style is not None:
        payload["visual_style"] = deepcopy(style)
    return payload


def channel_engine(style: dict | None, profile: str = "de-wissen") -> SimpleNamespace:
    return SimpleNamespace(
        opt=SimpleNamespace(
            channel_profile=profile,
            language="en-US",
            visual_style=deepcopy(style),
        ),
        _normalize_choices=lambda item: [
            (str(choice["id"]), str(choice["text"]))
            for choice in item.get("choices", [])
        ],
    )


def render_dispatch(style: dict | None, *, profile: str, aspect: str, state: str) -> Image.Image:
    size = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    canvas = Image.new("RGB", size, "black")
    if profile:
        options = QuizRenderOptions(
            aspect_ratio=aspect,
            channel_profile=profile,
            language="en-US",
            visual_style=deepcopy(style),
        )
    else:
        options = QuizRenderOptions(
            aspect_ratio=aspect,
            language="en-US",
            visual_style=deepcopy(style),
        )
    engine = QuizVideoEngineV2(options)
    return engine._render_question_card(
        canvas,
        ImageDraw.Draw(canvas),
        9 if state == "reveal" else 3,
        event(),
    )


def render_via_channel(style: dict | None, *, profile: str, aspect: str, state: str) -> Image.Image:
    size = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    canvas = Image.new("RGB", size, "black")
    engine = channel_engine(style, profile)
    return render_channel(
        engine,
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=event(),
        time=9 if state == "reveal" else 3,
    )


def make_evidence(run_id: str, output_root: Path) -> dict:
    evidence_root = output_root / "png" / run_id
    evidence_root.mkdir(parents=True, exist_ok=False)
    manifest_paths: list[str] = []
    style_records: list[dict] = []
    for style_id in STYLE_IDS:
        style = resolve_style_snapshot(style_id, locale="en-US", motion="medium")
        frames = {}
        for state in ("question", "reveal"):
            preview = render_via_channel(style, profile="de-wissen", aspect="16:9", state=state)
            production = render_dispatch(style, profile="de-wissen", aspect="16:9", state=state)
            if preview.tobytes() != production.tobytes():
                raise RuntimeError(f"shared dispatch mismatch: {style_id}/{state}")
            frames[state] = production
        manifest_dir = evidence_root / style_id
        manifest_dir.mkdir(parents=True, exist_ok=False)
        manifest = write_preview_evidence(
            manifest_dir,
            run_id=run_id,
            document=document(style),
            frames=frames,
            aspect="16:9",
        )
        manifest_paths.append(str(manifest.resolve()))
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        style_records.append({"style_id": style_id, "manifest": payload})

    legacy_frames = {
        state: render_dispatch(None, profile="", aspect="16:9", state=state)
        for state in ("question", "reveal")
    }
    legacy_dir = output_root / "png" / run_id / "legacy"
    legacy_dir.mkdir(parents=True, exist_ok=False)
    legacy_paths = []
    for state, frame in legacy_frames.items():
        path = legacy_dir / f"{run_id}-legacy-medium-16_9-{state}.png"
        if path.exists():
            raise FileExistsError(path)
        frame.save(path, format="PNG")
        with Image.open(path) as decoded:
            decoded.load()
            if decoded.format != "PNG" or decoded.size != (1920, 1080):
                raise RuntimeError(f"legacy PNG readback failed: {path}")
        legacy_paths.append({
            "state": state,
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    return {
        "schema_version": "luna_style_acceptance_repair_evidence_v1",
        "run_id": run_id,
        "status": "PASS",
        "styles": style_records,
        "legacy": legacy_paths,
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "mp4_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--output-root", default="output/channel-style-packs/repair")
    args = parser.parse_args()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    payload = make_evidence(args.run, output_root)
    path = output_root / f"{args.run}-manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "manifest": str(path),
        "style_count": len(payload["styles"]),
        "style_png_count": sum(len(item["manifest"]["artifacts"]) for item in payload["styles"]),
        "legacy_png_count": len(payload["legacy"]),
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "mp4_count": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ["main", "make_evidence"]
