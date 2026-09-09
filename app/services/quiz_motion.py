"""Deterministic, bounded motion primitives for opt-in Quiz style packs."""

from __future__ import annotations

import math
from typing import Any, Mapping

from app.services.quiz_layout_spec import LayoutSpec

MOTION_AMPLITUDE = {"low": 0.35, "medium": 0.7, "high": 1.0}


def motion_amplitude(motion: str) -> float:
    try:
        return MOTION_AMPLITUDE[motion]
    except KeyError as exc:
        raise ValueError(f"invalid motion level: {motion}") from exc


def bounded_displacement(motion: str, time_s: float, *, max_pixels: float = 18.0) -> tuple[int, int]:
    amplitude = motion_amplitude(motion) * max_pixels
    phase = float(time_s) * 2.0 * math.pi
    return round(amplitude * math.sin(phase)), round(amplitude * 0.5 * math.cos(phase))


def safe_motion_rect(rect: tuple[int, int, int, int], displacement: tuple[int, int], bounds: LayoutSpec) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    dx, dy = displacement
    moved = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    canvas = bounds.canvas
    safe = bounds.safe_margin
    safe_rect = (canvas.x, canvas.y, canvas.right, canvas.bottom)
    if not (safe_rect[0] <= moved[0] and safe_rect[1] <= moved[1] and safe_rect[2] >= moved[2] and safe_rect[3] >= moved[3]):
        raise ValueError(f"motion leaves safe bounds: {moved}")
    return moved


def motion_state(*, motion: str, time_s: float, layout: LayoutSpec, rects: Mapping[str, tuple[int, int, int, int]]) -> dict[str, Any]:
    displacement = bounded_displacement(motion, time_s)
    return {
        "motion": motion,
        "time": float(time_s),
        "displacement": list(displacement),
        "rects": {name: list(safe_motion_rect(rect, displacement, layout)) for name, rect in rects.items()},
    }


__all__ = ["MOTION_AMPLITUDE", "bounded_displacement", "motion_amplitude", "motion_state", "safe_motion_rect"]
