"""Safe document boundary for opt-in Quiz V2 visual style snapshots."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from app.services.quiz_style_packs import resolve_style_snapshot


def _validated_snapshot(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("visual_style must be an object")
    style_id = value.get("id")
    if not isinstance(style_id, str) or not style_id.strip():
        raise ValueError("visual_style id is required")
    snapshot = resolve_style_snapshot(
        style_id,
        locale=str(value.get("locale") or "en-US"),
        motion=str(value.get("motion") or "medium"),
        mascot=value.get("mascot", False),
        snapshot_override=value.get("snapshot"),
        version=value.get("version"),
    )
    return snapshot


def save_visual_style_snapshot(document: Mapping[str, Any], path: str | Path) -> Path:
    if not isinstance(document, Mapping):
        raise ValueError("document must be an object")
    snapshot = _validated_snapshot(document.get("visual_style"))
    payload = deepcopy(dict(document))
    payload["visual_style"] = snapshot
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.partial")
    partial.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(partial, destination)
    if load_visual_style_snapshot(destination) != snapshot:
        raise RuntimeError("visual style snapshot readback mismatch")
    return destination


def load_visual_style_snapshot(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load visual_style: {path}") from exc
    if not isinstance(payload, Mapping) or "visual_style" not in payload:
        raise ValueError("visual_style is required")
    return _validated_snapshot(payload["visual_style"])


__all__ = ["load_visual_style_snapshot", "save_visual_style_snapshot"]
