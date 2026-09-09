"""Deterministic identity boundaries for optional Quiz visual style snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.services.quiz_style_packs import resolve_style_snapshot

SCHEMA_VERSION = "quiz_visual_identity_v1"


def _canonical(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _hash(value: object) -> str:
    raw = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_quiz_visual_identity(
    base: Mapping[str, Any],
    *,
    visual_style: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(base, Mapping):
        raise ValueError("quiz identity base must be an object")
    semantic_source = base.get("questions", base)
    semantic = deepcopy(semantic_source)
    assets = deepcopy(base.get("assets", {}))
    narration = deepcopy(base.get("narration", {}))
    baseline_visual = {"renderer": "quiz-v2-baseline", "style": None}
    baseline_video = {"renderer": "quiz-v2-baseline-video", "visual": baseline_visual}
    normalized_style = None
    if visual_style is not None:
        style_id = visual_style.get("id")
        normalized_style = resolve_style_snapshot(
            str(style_id),
            locale=str(visual_style.get("locale") or "en-US"),
            motion=str(visual_style.get("motion") or "medium"),
            mascot=visual_style.get("mascot", False),
            snapshot_override=visual_style.get("snapshot"),
            version=visual_style.get("version"),
        )
    visual_payload = {"renderer": "quiz-v2-style-pack", "style": normalized_style}
    asset_hash = _hash(assets)
    narration_hash = _hash(narration)
    semantic_hash = _hash(semantic)
    baseline_visual_hash = _hash({"renderer": "quiz-v2-baseline", "style": None})
    baseline_video_hash = _hash({"renderer": "quiz-v2-baseline-video", "semantic": semantic_hash, "assets": asset_hash, "narration": narration_hash, "visual": baseline_visual_hash})
    visual_hash = _hash(visual_payload)
    video_hash = _hash({"renderer": "quiz-v2-style-video", "semantic": semantic_hash, "assets": asset_hash, "narration": narration_hash, "visual": visual_hash})
    return {
        "schema_version": SCHEMA_VERSION,
        "visual_style": normalized_style,
        "semantic_hash": semantic_hash,
        "asset_hash": asset_hash,
        "narration_hash": narration_hash,
        "baseline_visual_hash": baseline_visual_hash,
        "baseline_video_hash": baseline_video_hash,
        "visual_hash": visual_hash if normalized_style is not None else baseline_visual_hash,
        "video_hash": video_hash if normalized_style is not None else baseline_video_hash,
    }


__all__ = ["SCHEMA_VERSION", "build_quiz_visual_identity"]
