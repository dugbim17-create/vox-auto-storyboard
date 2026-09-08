"""Lineage envelope for narration-synchronised accumulated visual stages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.schemas.visual_events import VisualStage


def build_visual_stage_envelope(
    stage: VisualStage,
    *,
    style_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = stage.to_dict()
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    style = style_snapshot if isinstance(style_snapshot, dict) else {}
    return {
        "kind": "visual_stage",
        "schema_version": 1,
        "version": 1,
        "stage_id": stage.stage_id,
        "payload": payload,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "style": {
            key: str(style.get(key) or "")
            for key in ("visual_hash", "motion_hash", "render_theme_hash")
        },
        "events": {
            "count": stage.event_count,
            "persistent_count": sum(1 for event in stage.events if event.persistent),
            "ids": [event.event_id for event in stage.events],
        },
    }


def write_visual_stage_envelope(path: str | Path, envelope: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


__all__ = ["build_visual_stage_envelope", "write_visual_stage_envelope"]
