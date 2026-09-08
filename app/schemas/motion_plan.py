"""MotionPlan schema validation (P6-T01).

Validates a scene's ``MotionPlan`` — the per-scene motion spec consumed by the
local renderer. Structure (MASTER_PLAN section 6.5):

- exact duration: ``duration_ms`` (required, > 0) + ``fps``;
- layer tracks: ``layers`` with id/asset_role/z/transform key/value tracks;
- text animations: ``text_animations`` (text + timeline);
- effects: ``effects`` (grain, shadow, jitter...);
- transition: ``transition_in``/``transition_out`` (allow-listed);
- bounds: easing + z-order are pinned so the renderer never sees garbage.

Validation is a dataclass round-trip with extra checks, mirroring the
``storyboard.py`` approach. A buildable ``MotionPlan`` object is produced when
the input is valid.

Acceptance criteria (MASTER_PLAN P6-T01):

- invalid easing fails;
- invalid z-order fails;
- duration required;
- frame count derived (``frame_count = round(duration_ms / 1000 * fps)``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Allow-listed easings the renderer/compiler can evaluate.
ALLOWED_EASINGS: tuple[str, ...] = (
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "spring",
    "bounce",
    "overshoot",
)

# Allow-listed transition types (section 11.3).
ALLOWED_TRANSITIONS: tuple[str, ...] = (
    "none",
    "hard_cut",
    "crossfade",
    "wipe_left",
    "wipe_right",
    "paper_wipe",
    "paper_tear",
    "dip_to_color",
)

# z-order ceiling (non-negative integers in [0, MAX_Z)).
MAX_Z = 64

DEFAULT_FPS = 30
DEFAULT_CANVAS = (1920, 1080)


class MotionPlanError(ValueError):
    """Raised when a MotionPlan is invalid."""


@dataclass(frozen=True)
class MotionPlan:
    """A validated motion plan for one scene (round-trippable via dict)."""

    scene_id: str
    duration_ms: int
    fps: int = DEFAULT_FPS
    motion_fps: int = 12
    canvas_width: int = DEFAULT_CANVAS[0]
    canvas_height: int = DEFAULT_CANVAS[1]
    layers: list[dict] = field(default_factory=list)
    camera: dict = field(default_factory=dict)
    text_animations: list[dict] = field(default_factory=list)
    effects: list[dict] = field(default_factory=list)
    transition_in: str = "none"
    transition_out: str = "none"

    @property
    def frame_count(self) -> int:
        """Frame count ALWAYS derived from duration+fps (AC: derived)."""
        return int(round(self.duration_ms / 1000.0 * self.fps))

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "duration_ms": self.duration_ms,
            "fps": self.fps,
            "motion_fps": self.motion_fps,
            "canvas": {"width": self.canvas_width, "height": self.canvas_height},
            "camera": dict(self.camera),
            "layers": [dict(layer) for layer in self.layers],
            "text_animations": [dict(t) for t in self.text_animations],
            "effects": [dict(e) for e in self.effects],
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
        }


# --------------------------------------------------------------------------- #
# Small validators
# --------------------------------------------------------------------------- #
def validate_easing(value: Any) -> None:
    """Raise ``MotionPlanError`` when ``value`` is not an allowed easing."""
    if not isinstance(value, str) or value not in ALLOWED_EASINGS:
        raise MotionPlanError(
            f"invalid easing {value!r}; expected one of {ALLOWED_EASINGS}"
        )


def validate_transition(value: Any) -> None:
    if not isinstance(value, str) or value not in ALLOWED_TRANSITIONS:
        raise MotionPlanError(
            f"invalid transition {value!r}; expected one of {ALLOWED_TRANSITIONS}"
        )


def _check_keyframes(keys: Any, ctx: str) -> None:
    """A keyframe list is ``[[t, value], ...]`` with non-decreasing ``t``."""
    if not isinstance(keys, list) or not keys:
        raise MotionPlanError(f"{ctx}: keyframes must be a non-empty list")
    last_t = -1.0
    for kf in keys:
        if not isinstance(kf, (list, tuple)) or len(kf) != 2:
            raise MotionPlanError(f"{ctx}: keyframe must be [t, value]")
        t, value = kf
        if not isinstance(t, (int, float)) or isinstance(t, bool):
            raise MotionPlanError(f"{ctx}: keyframe time must be numeric")
        if not isinstance(value, (int, float)):
            raise MotionPlanError(f"{ctx}: keyframe value must be numeric")
        if t < last_t:
            raise MotionPlanError(f"{ctx}: keyframe times must be non-decreasing")
        last_t = t


def _check_track(track: Any, ctx: str) -> None:
    """A channel track is ``{easing, keyframes}`` or a bare ``[[t, v]]`` list."""
    if isinstance(track, dict):
        easing = track.get("easing", "linear")
        validate_easing(easing)
        _check_keyframes(track.get("keyframes"), f"{ctx}.keyframes")
        return
    if isinstance(track, list):
        _check_keyframes(track, ctx)
        return
    raise MotionPlanError(f"{ctx}: track must be an object or list")


def _check_transform(transform: Any, ctx: str) -> None:
    if not isinstance(transform, dict):
        raise MotionPlanError(f"{ctx}: transform must be an object")
    for channel, track in transform.items():
        _check_track(track, f"{ctx}.{channel}")


def _check_text(ta: Any, idx: int) -> None:
    """A text animation must carry a non-empty ``text``."""
    ctx = f"text_animations[{idx}]"
    if not isinstance(ta, dict):
        raise MotionPlanError(f"{ctx} must be an object")
    if not ta.get("text"):
        raise MotionPlanError(f"{ctx} missing 'text'")


# --------------------------------------------------------------------------- #
# Public build entrypoint
# --------------------------------------------------------------------------- #
def build_motion_plan(data: Any) -> MotionPlan:
    """Validate ``data`` and return a buildable ``MotionPlan``.

    Raises ``MotionPlanError`` on the first violation.
    """
    if not isinstance(data, dict):
        raise MotionPlanError("motion plan must be an object")

    scene_id = data.get("scene_id")
    if not scene_id:
        raise MotionPlanError("motion plan missing required field 'scene_id'")

    # duration is REQUIRED and must be positive (AC: duration required).
    duration_ms = data.get("duration_ms")
    if duration_ms is None:
        raise MotionPlanError("motion plan missing required field 'duration_ms'")
    if not isinstance(duration_ms, (int, float)) or isinstance(duration_ms, bool) or duration_ms <= 0:
        raise MotionPlanError(f"duration_ms must be a positive number, got {duration_ms!r}")

    fps = data.get("fps", DEFAULT_FPS)
    if not isinstance(fps, (int, float)) or isinstance(fps, bool) or fps <= 0:
        raise MotionPlanError(f"fps must be positive, got {fps!r}")
    motion_fps = data.get("motion_fps", min(12, int(fps)))
    if (
        not isinstance(motion_fps, (int, float))
        or isinstance(motion_fps, bool)
        or motion_fps <= 0
        or motion_fps > fps
    ):
        raise MotionPlanError(
            f"motion_fps must be positive and <= output fps, got {motion_fps!r}"
        )

    canvas = data.get("canvas", {})
    canvas_w = canvas.get("width", DEFAULT_CANVAS[0]) if isinstance(canvas, dict) else DEFAULT_CANVAS[0]
    canvas_h = canvas.get("height", DEFAULT_CANVAS[1]) if isinstance(canvas, dict) else DEFAULT_CANVAS[1]

    # z-order validation: unique, integer, in range.
    layers_raw = data.get("layers", [])
    if not isinstance(layers_raw, list):
        raise MotionPlanError("layers must be a list")
    z_seen: set[int] = set()
    layers: list[dict] = []
    for i, layer in enumerate(layers_raw):
        lctx = f"layers[{i}]"
        if not isinstance(layer, dict):
            raise MotionPlanError(f"{lctx} must be an object")
        lid = layer.get("id")
        if not lid:
            raise MotionPlanError(f"{lctx} missing 'id'")
        z = layer.get("z", 0)
        if not isinstance(z, int) or isinstance(z, bool):
            raise MotionPlanError(f"{lctx}: 'z' must be an integer, got {z!r}")
        if not (0 <= z < MAX_Z):
            raise MotionPlanError(f"{lctx}: 'z' {z} outside [0, {MAX_Z})")
        if z in z_seen:
            raise MotionPlanError(f"duplicate z-order {z} across layers")
        z_seen.add(z)
        if "transform" in layer:
            _check_transform(layer["transform"], f"{lctx}.transform")
        layers.append(layer)

    camera = data.get("camera", {})
    if isinstance(camera, dict):
        _check_transform(camera, "camera")
    elif camera:
        raise MotionPlanError("camera must be an object")

    text_animations = data.get("text_animations", [])
    if not isinstance(text_animations, list):
        raise MotionPlanError("text_animations must be an array")
    for idx, ta in enumerate(text_animations):
        _check_text(ta, idx)

    effects = data.get("effects", [])
    if not isinstance(effects, list):
        raise MotionPlanError("effects must be an array")
    for i, eff in enumerate(effects):
        if not isinstance(eff, dict) or "type" not in eff:
            raise MotionPlanError(f"effects[{i}] must be an object with a 'type'")

    transition_in = data.get("transition_in", "none")
    validate_transition(transition_in)
    transition_out = data.get("transition_out", "none")
    validate_transition(transition_out)

    return MotionPlan(
        scene_id=scene_id,
        duration_ms=int(duration_ms),
        fps=int(fps),
        motion_fps=int(motion_fps),
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        layers=layers,
        camera=camera,
        text_animations=text_animations,
        effects=effects,
        transition_in=transition_in,
        transition_out=transition_out,
    )
