"""Tests for P6-T02 motion template library.

Covers the acceptance criteria:

- snapshot MotionPlan (deterministic: same seed -> identical plan);
- template không vượt motion bounds (section 11.4);
- không phải Ken Burns-only (>=3 independent motion channels + layered);
- duration scaling;
- 16:9 and 9:16 both work.
"""

from __future__ import annotations

import pytest

from app.services.motion_templates import (
    BG_MAX_SCALE,
    CAMERA_PAN_FRAC,
    JITTER_MAX,
    JITTER_MIN,
    SUBJECT_DRIFT_FRAC,
    SUBJECT_ROTATION_DEG,
    MotionTemplateError,
    build_template,
    build_template_plan,
    template_meta,
    template_names,
)

W = 1920
H = 1080


# --------------------------------------------------------------------------- #
# 12 templates exist + build
# --------------------------------------------------------------------------- #
def test_twelve_templates_registered() -> None:
    names = template_names()
    assert len(names) == 12
    assert names[0] == "01_subject_slide_headline_pop"
    assert names[-1] == "12_conclusion_lockup"


def test_every_template_builds_valid_plan() -> None:
    for name in template_names():
        plan = build_template_plan(name, "scene_001", 5320, seed=1, canvas_size=(W, H))
        assert plan.scene_id == "scene_001"
        assert plan.duration_ms == 5320


def test_unknown_template_raises() -> None:
    with pytest.raises(MotionTemplateError):
        build_template("99_not_a_template", "s", 1000)
    with pytest.raises(MotionTemplateError):
        template_meta("99_not_a_template")


def test_template_meta_available() -> None:
    meta = template_meta("01_subject_slide_headline_pop")
    assert meta.name == "01_subject_slide_headline_pop"


# --------------------------------------------------------------------------- #
# AC: snapshot MotionPlan (deterministic)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", template_names())
def test_snapshot_is_deterministic(name) -> None:
    a = build_template_plan(name, "s1", 5320, seed=99, canvas_size=(W, H)).to_dict()
    b = build_template_plan(name, "s1", 5320, seed=99, canvas_size=(W, H)).to_dict()
    assert a == b


def test_different_seed_differs() -> None:
    a = build_template_plan("08_photo_stack_shuffle", "s", 5320, seed=1, canvas_size=(W, H))
    b = build_template_plan("08_photo_stack_shuffle", "s", 5320, seed=2, canvas_size=(W, H))
    # jitter amount differs between seeds (deterministic per seed).
    assert a.effects != b.effects


# --------------------------------------------------------------------------- #
# AC: not Ken Burns-only (>=3 independent channels, layered)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", template_names())
def test_not_ken_burns_only(name) -> None:
    plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
    # At least 2 independent layers (background + subject/foreground/...).
    assert len(plan.layers) >= 2
    # Local motion is carried by independent visual layers; typography is
    # injected later from narration semantics and may be absent in raw templates.
    # Motion channels across layers + camera = >= 3 independent channels.
    channels = 0
    for layer in plan.layers:
        channels += len(layer.get("transform", {}))
    channels += len(plan.camera or {})
    assert channels >= 3


def test_raw_templates_never_publish_literal_placeholder_copy() -> None:
    forbidden = {"HEADLINE", "LABEL", "MARKER", "BEFORE", "AFTER", "TIMELINE", "HIGHLIGHT"}
    for name in template_names():
        plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
        assert {str(item.get("text") or "") for item in plan.text_animations}.isdisjoint(forbidden), name


# --------------------------------------------------------------------------- #
# AC: template không vượt motion bounds (section 11.4)
# --------------------------------------------------------------------------- #
def test_background_scale_within_bounds() -> None:
    for name in template_names():
        plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
        for layer in plan.layers:
            t = layer.get("transform", {})
            if "scale" in t:
                for kf in t["scale"]["keyframes"]:
                    assert kf[1] <= BG_MAX_SCALE, f"{name}: scale {kf[1]}"


def test_subject_rotation_within_bounds() -> None:
    for name in template_names():
        plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
        for layer in plan.layers:
            t = layer.get("transform", {})
            if "rotation_deg" in t:
                for kf in t["rotation_deg"]["keyframes"]:
                    assert abs(kf[1]) <= SUBJECT_ROTATION_DEG + 0.01, (
                        f"{name}: rotation {kf[1]}"
                    )


def test_subject_drift_within_width_bounds() -> None:
    for name in template_names():
        plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
        subject = next((layer for layer in plan.layers if layer["asset_role"] == "subject"), None)
        if subject is None or "x" not in subject.get("transform", {}):
            continue
        max_drift = SUBJECT_DRIFT_FRAC * W
        for kf in subject["transform"]["x"]["keyframes"]:
            assert abs(kf[1]) <= max_drift, f"{name}: x {kf[1]}"


def test_camera_pan_within_bounds() -> None:
    for name in template_names():
        plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
        cam = plan.camera or {}
        if "x" in cam:
            max_pan = CAMERA_PAN_FRAC * W
            for kf in cam["x"]["keyframes"]:
                assert abs(kf[1]) <= max_pan, f"{name}: cam x {kf[1]}"


def test_jitter_within_bounds() -> None:
    for name in template_names():
        plan = build_template_plan(name, "s", 5320, seed=1, canvas_size=(W, H))
        for eff in plan.effects:
            if eff["type"] == "jitter":
                assert JITTER_MIN <= eff["amount"] <= JITTER_MAX


# --------------------------------------------------------------------------- #
# Duration scaling
# --------------------------------------------------------------------------- #
def test_keyframe_times_scale_with_duration() -> None:
    short = build_template_plan("01_subject_slide_headline_pop", "s", 2000, seed=1, canvas_size=(W, H))
    long = build_template_plan("01_subject_slide_headline_pop", "s", 8000, seed=1, canvas_size=(W, H))
    # No keyframe time exceeds its duration.
    for plan in (short, long):
        for layer in plan.layers:
            for _channel, track in layer.get("transform", {}).items():
                for kf in track["keyframes"]:
                    assert 0 <= kf[0] <= plan.duration_ms
    # Frame count scales linearly.
    assert short.frame_count * 4 == long.frame_count


# --------------------------------------------------------------------------- #
# 16:9 and 9:16
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("canvas", [(1920, 1080), (1080, 1920)])
@pytest.mark.parametrize("name", template_names())
def test_works_on_both_aspects(name, canvas) -> None:
    plan = build_template_plan(name, "s", 4000, seed=3, canvas_size=canvas)
    assert plan.canvas_width, plan.canvas_height == canvas
    assert plan.frame_count > 0


# --------------------------------------------------------------------------- #
# build_template returns raw dict that passes P6-T01
# --------------------------------------------------------------------------- #
def test_build_template_dict_passes_schema() -> None:
    from app.schemas.motion_plan import build_motion_plan

    raw = build_template("05_stat_number_count", "s", 3000, seed=5, canvas_size=(W, H))
    build_motion_plan(raw)  # no raise
