"""Motion template library (P6-T02).

Implements the 12 MVP templates from MASTER_PLAN section 11.2:

    01_subject_slide_headline_pop
    02_subject_float_label_reveal
    03_map_pan_marker_pulse
    04_before_after_split
    05_stat_number_count
    06_timeline_cards
    07_document_highlight
    08_photo_stack_shuffle
    09_cutout_parallax
    10_quote_card
    11_object_zoom_texture_wipe
    12_conclusion_lockup

Every template:

- has at least 3 independent motion channels (background/camera, subject, and
  text/foreground/effect — section 11.1), so a scene is never Ken Burns-only;
- uses a deterministic seed (same seed -> identical MotionPlan);
- scales with duration (keyframe times are fractions of the duration);
- works on both 16:9 and 9:16 canvases (coordinates derive from canvas size);
- respects the motion bounds in section 11.4 (background scale <= 1.06,
  subject drift <= 4% width, rotation +-3 deg, foreground drift <= 6% width,
  camera pan <= 3% canvas, jitter 0.2-1.2 px).

A template produces a plain dict that passes ``build_motion_plan`` from
P6-T01, so the two phases compose cleanly.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.motion_plan import build_motion_plan

# The 12 templates in the order listed in section 11.2.
TEMPLATE_NAMES: tuple[str, ...] = (
    "01_subject_slide_headline_pop",
    "02_subject_float_label_reveal",
    "03_map_pan_marker_pulse",
    "04_before_after_split",
    "05_stat_number_count",
    "06_timeline_cards",
    "07_document_highlight",
    "08_photo_stack_shuffle",
    "09_cutout_parallax",
    "10_quote_card",
    "11_object_zoom_texture_wipe",
    "12_conclusion_lockup",
)

# Motion bounds (section 11.4) used by the validators.
BG_MAX_SCALE = 1.06
SUBJECT_DRIFT_FRAC = 0.04
SUBJECT_ROTATION_DEG = 3.0
FG_DRIFT_FRAC = 0.06
CAMERA_PAN_FRAC = 0.03
JITTER_MIN = 0.2
JITTER_MAX = 1.2

DEFAULT_FPS = 30


class MotionTemplateError(ValueError):
    """Raised for an unknown template name or invalid parameters."""


@dataclass(frozen=True)
class TemplateMeta:
    """Metadata for one template."""

    name: str
    description: str


def _t_ms(duration_ms: int, frac: float) -> int:
    """Absolute time in ms for a fractional time within the duration."""
    return int(duration_ms * frac)


def _scale_bg() -> float:
    """Background scale to allow a subtle cover-fit drift within bounds."""
    return 1.05  # within 1.06 cap


def _pct(width: int, frac: float) -> int:
    return int(width * frac)


# --------------------------------------------------------------------------- #
# Template builders. Each returns a dict compatible with build_motion_plan.
# --------------------------------------------------------------------------- #
def _t01_subject_slide_headline_pop(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    drift = _pct(w, SUBJECT_DRIFT_FRAC)  # subject drifts <= 4% width
    mid = _t_ms(duration_ms, 0.5)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [mid, _pct(w, -CAMERA_PAN_FRAC) * 0.5], [end, _pct(w, CAMERA_PAN_FRAC) * 0.4]]},
            "y": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(h, 0.02)]]},
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(w, -0.01)]]},
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "x": {"easing": "ease_out", "keyframes": [[0, -drift], [mid, 0], [end, drift * 0.3]]},
                    "y": {"easing": "ease_out", "keyframes": [[0, 20], [mid, 0]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, -1.0], [mid, 0], [end, 0.8]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 20,
                "transform": {
                    "x": {"easing": "linear", "keyframes": [[0, 0], [end, _pct(w, FG_DRIFT_FRAC) * 0.3]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [mid, 1.0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [
            {"type": "film_grain", "amount": round(rng.uniform(0.05, 0.10), 3)},
            {"type": "jitter", "amount": round(rng.uniform(JITTER_MIN, JITTER_MAX), 3)},
        ],
        "transition_in": "none",
        "transition_out": "crossfade",
    }


def _t02_subject_float_label_reveal(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    drift = _pct(w, SUBJECT_DRIFT_FRAC)
    mid = _t_ms(duration_ms, 0.45)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
            "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(w, CAMERA_PAN_FRAC) * 0.6]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "y": {"easing": "ease_out", "keyframes": [[0, 0], [_t_ms(duration_ms, 0.3), -_pct(h, 0.04)], [end, _pct(h, 0.01)]]},
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [mid, drift * 0.5], [end, -drift * 0.4]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, 1.5]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 20,
                "transform": {
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.5), 1.0]]},
                    "y": {"easing": "ease_out", "keyframes": [[0, _pct(h, 0.05)], [_t_ms(duration_ms, 0.5), 0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [{"type": "film_grain", "amount": round(rng.uniform(0.03, 0.08), 3)}],
        "transition_in": "crossfade",
        "transition_out": "crossfade",
    }


def _t03_map_pan_marker_pulse(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    pan = _pct(w, CAMERA_PAN_FRAC)  # camera pan <= 3% canvas
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "x": {"easing": "linear", "keyframes": [[0, -pan], [end, pan]]},
            "y": {"easing": "linear", "keyframes": [[0, -_pct(h, 0.01)], [end, _pct(h, 0.01)]]},
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 10,
                "transform": {
                    "x": {"easing": "linear", "keyframes": [[0, 0], [end, _pct(w, FG_DRIFT_FRAC) * 0.2]]},
                    "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [_t_ms(duration_ms, 0.5), 1.02], [end, 1.0]]},
                },
            },
            {
                "id": "texture",
                "asset_role": "texture",
                "z": 5,
                "transform": {
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.3), 1.0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [
            {"type": "halftone_pulse", "amount": round(rng.uniform(0.05, 0.12), 3)},
            {"type": "jitter", "amount": round(rng.uniform(JITTER_MIN, JITTER_MAX), 3)},
        ],
        "transition_in": "wipe_right",
        "transition_out": "none",
    }


def _t04_before_after_split(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    mid = _t_ms(duration_ms, 0.5)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [mid, 0], [end, _pct(w, -0.02)]]},
                    "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 10,
                "transform": {
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [mid, 0], [end, _pct(w, FG_DRIFT_FRAC) * 0.3]]},
                    "opacity": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [mid, 0.0], [end, 1.0]]},
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 5,
                "transform": {
                    "x": {"easing": "ease_in_out", "keyframes": [[0, -_pct(w, SUBJECT_DRIFT_FRAC)], [mid, 0], [end, _pct(w, SUBJECT_DRIFT_FRAC)]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [mid, 1.0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [
            {"type": "film_grain", "amount": round(rng.uniform(0.03, 0.09), 3)},
            {"type": "shadow", "amount": 0.5},
        ],
        "transition_in": "wipe_left",
        "transition_out": "crossfade",
    }


def _t05_stat_number_count(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
            "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(w, CAMERA_PAN_FRAC) * 0.5]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "scale": {"easing": "ease_out", "keyframes": [[0, 0.94], [_t_ms(duration_ms, 0.4), 1.0], [end, 1.03]]},
                    "y": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, -_pct(h, 0.03)]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 20,
                "transform": {
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.5), 1.0]]},
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(w, FG_DRIFT_FRAC) * 0.2]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [
            {"type": "counter", "amount": round(rng.uniform(0.5, 1.0), 3)},
            {"type": "film_grain", "amount": round(rng.uniform(0.03, 0.07), 3)},
        ],
        "transition_in": "crossfade",
        "transition_out": "dip_to_color",
    }


def _t06_timeline_cards(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    n_cards = 3
    cards = []
    for i in range(n_cards):
        t0 = _t_ms(duration_ms, (i + 1) / (n_cards + 1))
        t1 = _t_ms(duration_ms, (i + 2) / (n_cards + 1))
        cards.append(
            {
                "id": f"card{i}",
                "asset_role": "foreground",
                "z": 10 + i,
                "transform": {
                    "y": {"easing": "ease_out", "keyframes": [[0, _pct(h, 0.2)], [t0, 0]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [t0, 1.0], [t1, 0.0]]},
                },
            }
        )
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "x": {"easing": "linear", "keyframes": [[0, -_pct(w, CAMERA_PAN_FRAC)], [end, _pct(w, CAMERA_PAN_FRAC)]]},
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            *cards,
        ],
        "text_animations": [],
        "effects": [{"type": "shadow", "amount": 0.4}, {"type": "jitter", "amount": round(rng.uniform(JITTER_MIN, JITTER_MAX), 3)}],
        "transition_in": "none",
        "transition_out": "crossfade",
    }


def _t07_document_highlight(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [_t_ms(duration_ms, 0.6), 1.04], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [_t_ms(duration_ms, 0.5), -_pct(w, 0.02)], [end, 0]]},
                    "y": {"easing": "ease_in_out", "keyframes": [[0, 0], [_t_ms(duration_ms, 0.5), _pct(h, 0.02)], [end, 0]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, 2.0]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 20,
                "transform": {
                    "opacity": {"easing": "ease_in_out", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.5), 1.0]]},
                    "x": {"easing": "ease_in", "keyframes": [[0, _pct(w, 0.03)], [_t_ms(duration_ms, 0.5), 0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [{"type": "marker_highlight", "amount": round(rng.uniform(0.4, 0.9), 3)}],
        "transition_in": "wipe_left",
        "transition_out": "wipe_left",
    }


def _t08_photo_stack_shuffle(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    n_photos = 3
    photos = []
    for i in range(n_photos):
        t0 = _t_ms(duration_ms, (i + 1) / (n_photos + 1))
        angle = round(rng.uniform(-SUBJECT_ROTATION_DEG, SUBJECT_ROTATION_DEG), 2)
        photos.append(
            {
                "id": f"photo{i}",
                "asset_role": "foreground",
                "z": 10 + i,
                "transform": {
                    "x": {"easing": "ease_out", "keyframes": [[0, _pct(w, 0.06)], [t0, 0]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, angle], [t0, angle * 0.4]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [t0, 1.0]]},
                },
            }
        )
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
            "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(w, CAMERA_PAN_FRAC) * 0.6]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            *photos,
        ],
        "text_animations": [],
        "effects": [
            {"type": "photo_stack", "amount": n_photos},
            {"type": "shadow", "amount": 0.5},
            {"type": "jitter", "amount": round(rng.uniform(JITTER_MIN, JITTER_MAX), 3)},
        ],
        "transition_in": "crossfade",
        "transition_out": "crossfade",
    }


def _t09_cutout_parallax(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "x": {"easing": "ease_in_out", "keyframes": [[0, -_pct(w, CAMERA_PAN_FRAC) * 0.5], [end, _pct(w, CAMERA_PAN_FRAC) * 0.5]]},
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]},
                    "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, -_pct(w, 0.03)]]},
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "x": {"easing": "ease_in_out", "keyframes": [[0, -_pct(w, SUBJECT_DRIFT_FRAC)], [end, _pct(w, SUBJECT_DRIFT_FRAC)]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, -1.0], [end, 1.5]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 20,
                "transform": {
                    "x": {"easing": "ease_in_out", "keyframes": [[0, _pct(w, FG_DRIFT_FRAC) * 0.4], [end, -_pct(w, FG_DRIFT_FRAC) * 0.4]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.2), 1.0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [{"type": "parallax", "amount": round(rng.uniform(0.3, 0.8), 3)}],
        "transition_in": "none",
        "transition_out": "crossfade",
    }


def _t10_quote_card(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [_t_ms(duration_ms, 0.4), 1.02], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 10,
                "transform": {
                    "y": {"easing": "ease_out", "keyframes": [[0, _pct(h, 0.06)], [_t_ms(duration_ms, 0.3), 0]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.3), 1.0]]},
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 5,
                "transform": {
                    "opacity": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [_t_ms(duration_ms, 0.3), 0.3], [end, 1.0]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, 1.2]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [
            {"type": "film_grain", "amount": round(rng.uniform(0.04, 0.09), 3)},
            {"type": "shadow", "amount": 0.4},
        ],
        "transition_in": "crossfade",
        "transition_out": "dip_to_color",
    }


def _t11_object_zoom_texture_wipe(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [_t_ms(duration_ms, 0.7), 1.05], [end, _scale_bg()]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "scale": {"easing": "ease_out", "keyframes": [[0, 0.92], [_t_ms(duration_ms, 0.6), 1.0], [end, 1.04]]},
                    "rotation_deg": {"easing": "ease_in_out", "keyframes": [[0, -1.0], [_t_ms(duration_ms, 0.6), 0], [end, 1.0]]},
                },
            },
            {
                "id": "texture",
                "asset_role": "texture",
                "z": 20,
                "transform": {
                    "x": {"easing": "linear", "keyframes": [[0, -_pct(w, 0.1)], [end, _pct(w, 0.1)]]},
                    "opacity": {"easing": "ease_in_out", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.6), 1.0], [end, 0.0]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [{"type": "paper_tear", "amount": round(rng.uniform(0.3, 0.7), 3)}],
        "transition_in": "none",
        "transition_out": "paper_tear",
    }


def _t12_conclusion_lockup(
    scene_id: str, duration_ms: int, seed: int, canvas: tuple[int, int]
) -> dict:
    w, h = canvas
    rng = random.Random(seed)
    end = duration_ms
    return {
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "fps": DEFAULT_FPS,
        "canvas": {"width": w, "height": h},
        "camera": {
            "scale": {"easing": "ease_in_out", "keyframes": [[0, _scale_bg()], [_t_ms(duration_ms, 0.7), _scale_bg()], [end, _scale_bg()]]},
            "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [end, _pct(w, CAMERA_PAN_FRAC) * 0.3]]},
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {"scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [end, _scale_bg()]]}},
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 10,
                "transform": {
                    "y": {"easing": "ease_in", "keyframes": [[0, _pct(h, 0.04)], [_t_ms(duration_ms, 0.4), 0]]},
                    "opacity": {"easing": "ease_in", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.4), 1.0]]},
                },
            },
            {
                "id": "foreground",
                "asset_role": "foreground",
                "z": 20,
                "transform": {
                    "opacity": {"easing": "ease_in_out", "keyframes": [[0, 0.0], [_t_ms(duration_ms, 0.5), 1.0], [end, 1.0]]},
                    "x": {"easing": "ease_in_out", "keyframes": [[0, _pct(w, FG_DRIFT_FRAC) * 0.5], [end, -_pct(w, FG_DRIFT_FRAC) * 0.3]]},
                },
            },
        ],
        "text_animations": [],
        "effects": [
            {"type": "film_grain", "amount": round(rng.uniform(0.05, 0.10), 3)},
            {"type": "jitter", "amount": round(rng.uniform(JITTER_MIN, JITTER_MAX), 3)},
        ],
        "transition_in": "crossfade",
        "transition_out": "dip_to_color",
    }


# Registry: name -> builder callable.
_TEMPLATE_BUILDERS: dict[str, Callable[..., dict]] = {
    "01_subject_slide_headline_pop": _t01_subject_slide_headline_pop,
    "02_subject_float_label_reveal": _t02_subject_float_label_reveal,
    "03_map_pan_marker_pulse": _t03_map_pan_marker_pulse,
    "04_before_after_split": _t04_before_after_split,
    "05_stat_number_count": _t05_stat_number_count,
    "06_timeline_cards": _t06_timeline_cards,
    "07_document_highlight": _t07_document_highlight,
    "08_photo_stack_shuffle": _t08_photo_stack_shuffle,
    "09_cutout_parallax": _t09_cutout_parallax,
    "10_quote_card": _t10_quote_card,
    "11_object_zoom_texture_wipe": _t11_object_zoom_texture_wipe,
    "12_conclusion_lockup": _t12_conclusion_lockup,
}

_TEMPLATE_META: dict[str, TemplateMeta] = {
    name: TemplateMeta(name=name, description=_TEMPLATE_BUILDERS[name].__doc__ or "")
    for name in TEMPLATE_NAMES
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def template_names() -> list[str]:
    """All registered template names, in section 11.2 order."""
    return list(TEMPLATE_NAMES)


def template_meta(name: str) -> TemplateMeta:
    """Metadata for one template; raises ``MotionTemplateError`` if unknown."""
    if name not in _TEMPLATE_META:
        raise MotionTemplateError(f"unknown template {name!r}; expected one of {TEMPLATE_NAMES}")
    return _TEMPLATE_META[name]


def build_template(
    name: str,
    scene_id: str,
    duration_ms: int,
    *,
    seed: int = 42,
    canvas_size: tuple[int, int] = (1920, 1080),
) -> dict:
    """Build a template's raw MotionPlan dict (validates via P6-T01).

    Deterministic: the same (name, seed, duration, canvas) always yields the
    same dict, so a project can be re-rendered identically.
    """
    if name not in _TEMPLATE_BUILDERS:
        raise MotionTemplateError(f"unknown template {name!r}; expected one of {TEMPLATE_NAMES}")
    if duration_ms <= 0:
        raise MotionTemplateError(f"duration_ms must be positive, got {duration_ms}")
    plan = _TEMPLATE_BUILDERS[name](scene_id, duration_ms, seed, canvas_size)
    # Validate immediately so callers never receive an ill-formed plan.
    build_motion_plan(plan)
    return plan


def build_template_plan(
    name: str,
    scene_id: str,
    duration_ms: int,
    *,
    seed: int = 42,
    canvas_size: tuple[int, int] = (1920, 1080),
) -> Any:
    """Build and return a validated ``MotionPlan`` object (P6-T01 dataclass)."""
    raw = build_template(name, scene_id, duration_ms, seed=seed, canvas_size=canvas_size)
    return build_motion_plan(raw)
