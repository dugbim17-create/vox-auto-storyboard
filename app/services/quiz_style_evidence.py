"""Non-overwriting PNG evidence writer for the quiz style repair gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from PIL import Image


def _safe_part(value: object) -> str:
    text = str(value or "").strip()
    if not text or any(char in text for char in "\\/:*?\"<>|\r\n"):
        raise ValueError("invalid evidence path component")
    return text


def write_preview_evidence(
    root: str | Path,
    *,
    run_id: str,
    document: Mapping[str, Any],
    frames: Mapping[str, Image.Image],
    aspect: str,
) -> Path:
    if not isinstance(document, Mapping) or not isinstance(document.get("visual_style"), Mapping):
        raise ValueError("visual_style is required for style evidence")
    style = document["visual_style"]
    style_id = _safe_part(style.get("id"))
    motion = _safe_part(style.get("motion") or "medium")
    run = _safe_part(run_id)
    aspect_part = _safe_part(aspect.replace(":", "_"))
    if not frames:
        raise ValueError("at least one preview frame is required")
    output = Path(root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for state, frame in frames.items():
        state_part = _safe_part(state)
        if not isinstance(frame, Image.Image):
            raise ValueError(f"frame must be an image: {state}")
        path = output / f"{run}-{style_id}-{motion}-{aspect_part}-{state_part}.png"
        if path.exists():
            raise FileExistsError(path)
        frame.convert("RGB").save(path, format="PNG")
        with Image.open(path) as decoded:
            decoded.load()
            if decoded.format != "PNG" or decoded.getbbox() is None:
                raise RuntimeError(f"preview readback failed: {path}")
            width, height = decoded.size
        artifacts.append({
            "state": state,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": [width, height],
        })
    manifest = output / "manifest.json"
    if manifest.exists():
        raise FileExistsError(manifest)
    manifest.write_text(json.dumps({
        "schema_version": "quiz_style_png_evidence_v1",
        "run_id": run,
        "style_id": style_id,
        "motion": motion,
        "aspect": aspect,
        "artifacts": artifacts,
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "mp4_count": 0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


__all__ = ["write_preview_evidence"]
