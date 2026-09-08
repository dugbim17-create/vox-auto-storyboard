"""Narration clauses -> persistent VisualStage events for production VOX."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.visual_events import VisualStage, build_visual_stage

_TRIGGER_PATTERN = re.compile(
    r"(?:\b(?:19|20)\d{2}\b|\$?\d+(?:[.,]\d+)?\s*(?:triệu|tỷ|million|billion|m|b|đô|usd)?|"
    r"SpaceX|Tesla|Starlink|Neuralink|Boring Company|Twitter|PayPal|Zip2|X\.com|eBay|Compaq)",
    flags=re.IGNORECASE,
)

_EFFECTS = ("counter", "swipe_right", "popup", "stamp", "page_flip", "line_draw")
_PLACEMENTS = ("center_top", "left", "right", "left_bottom", "right_bottom", "center")


def build_scene_visual_stage(
    *,
    scene: dict[str, Any],
    duration_ms: int,
    background: str,
    asset_roles: set[str] | frozenset[str],
) -> VisualStage:
    """Build one accumulated stage; explicit storyboard events win.

    Generated events are provider-free and deterministic. Every prior event is
    persistent until the stage changes, matching narration-led VOX semantics.
    """
    scene_id = str(scene.get("scene_id") or "").strip()
    narration = " ".join(str(scene.get("narration_text") or "").split())
    explicit = scene.get("visual_events")
    if isinstance(explicit, list) and explicit:
        events = [dict(item, persistent=True) for item in explicit if isinstance(item, dict)]
    else:
        events = _derive_events(narration, duration_ms, asset_roles)
    return build_visual_stage(
        {
            "stage_id": scene_id,
            "narration": narration,
            "duration_ms": duration_ms,
            "background": background,
            "canvas": scene.get("canvas") or {},
            "style": "accumulated_editorial_collage",
            "events": events,
        }
    )


def _derive_events(narration: str, duration_ms: int, asset_roles: set[str] | frozenset[str]) -> list[dict]:
    matches = [match.group(0).strip() for match in _TRIGGER_PATTERN.finditer(narration)]
    clauses = [
        clause.strip(" ,.-")
        for clause in re.split(r"[.!?;:]|\b(?:và|rồi|nhưng|sau đó|còn)\b", narration, flags=re.IGNORECASE)
        if len(clause.strip(" ,.-").split()) >= 2
    ]
    for clause in clauses:
        authored = " ".join(clause.split()[:5])
        if authored and all(authored.casefold() not in item.casefold() for item in matches):
            matches.append(authored)
    if not matches:
        words = [word.strip(".,!?;:") for word in narration.split() if len(word.strip(".,!?;:")) >= 4]
        matches = [" ".join(words[:3]) or "THÔNG TIN"]
    # Keep a readable event budget for short narration stages.
    matches = matches[: min(7, max(1, duration_ms // 700))]
    step = max(320, duration_ms // max(len(matches) + 1, 2))
    roles = [role for role in ("foreground", "subject", "texture") if role in asset_roles]
    if not roles:
        roles = [next(iter(asset_roles), "foreground")]
    events = []
    for index, trigger in enumerate(matches):
        start = min(duration_ms - 200, index * step)
        remaining = max(200, duration_ms - start)
        events.append(
            {
                "event_id": f"event_{index + 1:02d}",
                "trigger": trigger,
                "start_ms": start,
                "duration_ms": remaining,
                "asset": roles[index % len(roles)],
                "placement": _PLACEMENTS[index % len(_PLACEMENTS)],
                "enter": "counter" if re.fullmatch(r"(?:19|20)\d{2}|\$?[\d.,]+.*", trigger) else _EFFECTS[index % len(_EFFECTS)],
                "persistent": True,
                "z": 10 + index,
            }
        )
    return events


__all__ = ["build_scene_visual_stage"]
