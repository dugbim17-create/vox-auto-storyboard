"""Bridge semantic narration events into compiler-ready MotionPlan cues."""

from __future__ import annotations

from copy import deepcopy

from app.schemas.editorial_timeline import SceneEditorialTimeline
from app.schemas.motion_plan import build_motion_plan


class EditorialMotionError(ValueError):
    """Raised when semantic event timing and a motion template disagree."""


PLACEHOLDER_TEXT = {"HEADLINE", "LABEL", "MARKER", "NUMBER", "42"}


def apply_editorial_events(
    motion_plan: dict,
    timeline: SceneEditorialTimeline,
) -> dict:
    """Replace template placeholders with narration-anchored visual cues."""
    plan = deepcopy(motion_plan)
    if plan.get("scene_id") != timeline.scene_id:
        raise EditorialMotionError("motion plan and editorial timeline scene ids differ")
    if int(plan.get("fps") or 0) != timeline.fps:
        raise EditorialMotionError("motion plan and editorial timeline fps differ")
    if int(plan.get("duration_ms") or 0) != timeline.duration_ms:
        raise EditorialMotionError("motion plan duration must equal measured voice duration")

    retained = [
        item
        for item in plan.get("text_animations", [])
        if str(item.get("text") or "").strip().upper() not in PLACEHOLDER_TEXT
    ]
    for event in timeline.visual_events:
        if event.object_type not in {"headline", "label", "counter", "quote"}:
            continue
        retained.append(
            {
                "event_id": event.event_id,
                "beat_id": event.beat_id,
                "object_type": event.object_type,
                "layer_role": event.layer_role,
                "text": event.display_text,
                "narration_anchor": event.anchor.text,
                "start_ms": event.start_ms,
                "end_ms": event.end_ms,
                "placement": "center" if event.object_type in {"counter", "headline"} else "top_left",
                "font_size": 96 if event.object_type == "counter" else 64,
            }
        )
    plan["text_animations"] = retained
    return build_motion_plan(plan).to_dict()
