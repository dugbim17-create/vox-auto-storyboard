"""Deterministic event-level asset materialization for accumulated VOX stages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.schemas.visual_events import VisualStage


def materialize_visual_event_assets(
    stage: VisualStage,
    *,
    role_assets: dict[str, str],
    output_dir: str | Path,
) -> dict[str, str]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    manifest_events: list[dict[str, Any]] = []
    for event in stage.events:
        source = role_assets.get(event.asset) or role_assets.get("foreground")
        if not source or not Path(source).is_file():
            raise ValueError(f"event asset missing: {event.event_id}")
        image = Image.open(source).convert("RGBA")
        image = _fit_event_canvas(image, stage.canvas_width, stage.canvas_height)
        image = _author_event_overlay(image, event.trigger, event.event_id)
        path = target / f"{stage.stage_id}_{event.event_id}.png"
        image.save(path, format="PNG", optimize=False)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result[event.event_id] = str(path)
        manifest_events.append(
            {
                "event_id": event.event_id,
                "trigger": event.trigger,
                "asset": str(path),
                "sha256": digest,
            }
        )
    manifest_path = target / f"{stage.stage_id}_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"kind": "visual_event_assets", "stage_id": stage.stage_id, "events": manifest_events},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    result["_manifest"] = str(manifest_path)
    return result


def _fit_event_canvas(image: Image.Image, width: int, height: int) -> Image.Image:
    image.thumbnail((min(920, width), min(520, height)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    canvas.alpha_composite(image)
    return canvas


def _author_event_overlay(image: Image.Image, trigger: str, event_id: str) -> Image.Image:
    width, height = image.size
    draw = ImageDraw.Draw(image)
    label_height = min(72, max(42, height // 7))
    draw.rounded_rectangle(
        (4, 4, width - 4, label_height),
        radius=max(6, label_height // 5),
        fill="#eee4ce",
        outline="#161616",
        width=max(2, label_height // 18),
    )
    font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
    font = ImageFont.truetype(str(font_path), max(16, label_height // 3)) if font_path.is_file() else ImageFont.load_default()
    draw.text((14, max(7, label_height // 4)), trigger[:48], fill="#161616", font=font)
    # A deterministic event marker makes identical source-role files distinct
    # while keeping the actual content-bearing trigger visible to the audience.
    draw.line((12, height - 12, min(width - 12, 80 + len(event_id) * 8), height - 12), fill="#cf2637", width=max(2, height // 90))
    return image


__all__ = ["materialize_visual_event_assets"]
