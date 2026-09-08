"""Anti-Ken-Burns validator (P6-T06).

Validates a MotionPlan dict and rejects plans that are 'Ken Burns only'
(a single bitmap with just scale + translate, no independent layers).

MASTER_PLAN section 11.1 rules:
- layer_count >= 2
- independent_transform_tracks >= 3
- at_least_one_local_event = True (text_animations or effects)
"""

from __future__ import annotations

from dataclasses import dataclass, field


class KenBurnsError(Exception):
    """Raised when a plan is rejected as Ken Burns-only."""


@dataclass
class KenBurnsResult:
    """Outcome of anti-Ken-Burns validation."""
    is_ken_burns: bool
    layer_count: int
    transform_tracks: int
    has_local_event: bool
    reasons: list[str] = field(default_factory=list)


def _count_transform_tracks(plan: dict) -> int:
    """Count independent transform channels across camera + all layers."""
    tracks = 0

    # Camera tracks.
    camera = plan.get("camera") or {}
    for key in ("x", "y", "scale", "rotation_deg"):
        val = camera.get(key)
        if val is not None:
            # Accept dict with "keyframes" key (track format) or bare list.
            if isinstance(val, dict):
                kf = val.get("keyframes", val)
                if kf:
                    tracks += 1
            elif isinstance(val, list) and len(val) >= 1:
                tracks += 1

    # Per-layer tracks.
    for layer in plan.get("layers", []):
        transform = layer.get("transform") or {}
        for key in ("x", "y", "scale", "rotation_deg", "opacity"):
            val = transform.get(key)
            if val is not None:
                if isinstance(val, dict):
                    kf = val.get("keyframes", val)
                    if kf:
                        tracks += 1
                elif isinstance(val, list) and len(val) >= 1:
                    tracks += 1

    return tracks


def _has_local_event(plan: dict) -> bool:
    """True if the plan has text_animations or effects."""
    text_anims = plan.get("text_animations") or []
    effects = plan.get("effects") or []
    return bool(text_anims) or bool(effects)


def validate(plan: dict) -> KenBurnsResult:
    """Check if a plan is Ken Burns-only. Returns detailed result."""
    layers = plan.get("layers") or []
    layer_count = len(layers)
    transform_tracks = _count_transform_tracks(plan)
    has_event = _has_local_event(plan)

    reasons: list[str] = []
    is_kb = False

    if layer_count < 2:
        reasons.append(f"layer_count={layer_count} < 2")
        is_kb = True
    if transform_tracks < 3:
        reasons.append(f"transform_tracks={transform_tracks} < 3")
        is_kb = True
    if not has_event:
        reasons.append("no text_animations or effects (no local event)")
        is_kb = True

    return KenBurnsResult(
        is_ken_burns=is_kb,
        layer_count=layer_count,
        transform_tracks=transform_tracks,
        has_local_event=has_event,
        reasons=reasons,
    )


def validate_or_raise(plan: dict) -> KenBurnsResult:
    """Validate and raise KenBurnsError if the plan is Ken Burns-only."""
    result = validate(plan)
    if result.is_ken_burns:
        raise KenBurnsError(
            f"Plan is Ken Burns-only: {'; '.join(result.reasons)}"
        )
    return result
