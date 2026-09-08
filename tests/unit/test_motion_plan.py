"""Tests for P6-T01 MotionPlan schema.

Covers the acceptance criteria:

- invalid easing fails;
- invalid z-order fails;
- duration required;
- frame count derived (from duration + fps).
"""

from __future__ import annotations

import pytest

from app.schemas.motion_plan import (
    ALLOWED_EASINGS,
    MAX_Z,
    MotionPlan,
    MotionPlanError,
    build_motion_plan,
    validate_easing,
)


def valid_plan(**overrides) -> dict:
    data = {
        "scene_id": "scene_001",
        "duration_ms": 5320,
        "fps": 30,
        "canvas": {"width": 1920, "height": 1080},
        "camera": {"x": {"easing": "ease_in", "keyframes": [[0, 0], [5320, -12]]}},
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "scale": {"easing": "linear", "keyframes": [[0, 1.0], [5320, 1.04]]},
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 20,
                "transform": {
                    "x": {"easing": "ease_out", "keyframes": [[0, -100], [500, 0], [5320, 14]]},
                },
            },
        ],
        "text_animations": [{"text": "DÒNG CHỮ", "scale": [{"t": 0, "value": 0.9}]}],
        "effects": [{"type": "paper_grain", "amount": 0.12}],
        "transition_in": "none",
        "transition_out": "paper_wipe",
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# Valid plan builds
# --------------------------------------------------------------------------- #
def test_valid_plan_builds() -> None:
    plan = build_motion_plan(valid_plan())
    assert isinstance(plan, MotionPlan)
    assert plan.scene_id == "scene_001"
    assert plan.duration_ms == 5320
    assert len(plan.layers) == 2


def test_valid_plan_round_trip() -> None:
    plan = build_motion_plan(valid_plan())
    rebuilt = build_motion_plan(plan.to_dict())
    assert rebuilt == plan


# --------------------------------------------------------------------------- #
# Duration required + derived frame count (AC)
# --------------------------------------------------------------------------- #
def test_duration_required() -> None:
    with pytest.raises(MotionPlanError, match="duration"):
        build_motion_plan(valid_plan(duration_ms=None))


def test_duration_must_be_positive() -> None:
    with pytest.raises(MotionPlanError, match="duration"):
        build_motion_plan(valid_plan(duration_ms=0))
    with pytest.raises(MotionPlanError, match="duration"):
        build_motion_plan(valid_plan(duration_ms=-5))


def test_frame_count_derived() -> None:
    plan = build_motion_plan(valid_plan(duration_ms=5320, fps=30))
    assert plan.frame_count == 160  # 5320/1000*30 = 159.6 -> round 160


def test_frame_count_scales_with_fps() -> None:
    plan = build_motion_plan(valid_plan(duration_ms=2000, fps=60))
    assert plan.frame_count == 120
    plan2 = build_motion_plan(valid_plan(duration_ms=2000, fps=30))
    assert plan2.frame_count == 60


def test_frame_count_property_is_derived_not_stored() -> None:
    plan = build_motion_plan(valid_plan(duration_ms=1000, fps=30))
    # frame_count is not an attribute; it is a computed property.
    assert not hasattr(plan, "frame_count_field")
    assert plan.frame_count == 30


# --------------------------------------------------------------------------- #
# Invalid easing fails (AC: invalid easing fail)
# --------------------------------------------------------------------------- #
def test_invalid_easing_fails() -> None:
    data = valid_plan()
    data["layers"][1]["transform"]["x"]["easing"] = "teleport"
    with pytest.raises(MotionPlanError, match="invalid easing"):
        build_motion_plan(data)


def test_invalid_camera_easing_fails() -> None:
    data = valid_plan()
    data["camera"] = {"x": {"easing": "warp_speed", "keyframes": [[0, 0], [1000, 5]]}}
    with pytest.raises(MotionPlanError, match="invalid easing"):
        build_motion_plan(data)


def test_allowed_easings_are_accepted() -> None:
    for easing in ALLOWED_EASINGS:
        data = valid_plan()
        data["layers"][1]["transform"]["x"]["easing"] = easing
        plan = build_motion_plan(data)
        assert plan is not None


def test_validate_easing_helper() -> None:
    validate_easing("linear")
    with pytest.raises(MotionPlanError):
        validate_easing("bogus")


# --------------------------------------------------------------------------- #
# Invalid z-order fails (AC: invalid z-order fail)
# --------------------------------------------------------------------------- #
def test_duplicate_z_order_fails() -> None:
    data = valid_plan()
    data["layers"][1]["z"] = 0  # collides with layer[0]
    with pytest.raises(MotionPlanError, match="duplicate z"):
        build_motion_plan(data)


def test_out_of_range_z_fails() -> None:
    data = valid_plan()
    data["layers"][1]["z"] = MAX_Z  # must be < MAX_Z
    with pytest.raises(MotionPlanError, match="outside"):
        build_motion_plan(data)


def test_non_integer_z_fails() -> None:
    data = valid_plan()
    data["layers"][1]["z"] = 1.5
    with pytest.raises(MotionPlanError):
        build_motion_plan(data)


def test_negative_z_fails() -> None:
    data = valid_plan()
    data["layers"][1]["z"] = -1
    with pytest.raises(MotionPlanError):
        build_motion_plan(data)


# --------------------------------------------------------------------------- #
# Structure / bounds
# --------------------------------------------------------------------------- #
def test_missing_scene_id_fails() -> None:
    with pytest.raises(MotionPlanError, match="scene_id"):
        build_motion_plan(valid_plan(scene_id=None))


def test_non_dict_input_fails() -> None:
    with pytest.raises(MotionPlanError):
        build_motion_plan("not a plan")


def test_bad_keyframe_ordering_fails() -> None:
    data = valid_plan()
    data["layers"][1]["transform"]["x"]["keyframes"] = [[500, 0], [0, -100]]
    with pytest.raises(MotionPlanError, match="non-decreasing"):
        build_motion_plan(data)


def test_bare_track_list_accepted() -> None:
    data = valid_plan()
    data["layers"][1]["transform"]["x"] = [[0, -100], [500, 0]]  # shorthand
    plan = build_motion_plan(data)
    assert plan is not None


def test_invalid_transition_fails() -> None:
    data = valid_plan()
    data["transition_out"] = "explode"
    with pytest.raises(MotionPlanError, match="transition"):
        build_motion_plan(data)


def test_effect_requires_type() -> None:
    data = valid_plan()
    data["effects"] = [{"amount": 0.5}]  # no 'type'
    with pytest.raises(MotionPlanError, match="type"):
        build_motion_plan(data)


def test_frame_count_never_stored_in_dict() -> None:
    plan = build_motion_plan(valid_plan())
    assert "frame_count" not in plan.to_dict()
