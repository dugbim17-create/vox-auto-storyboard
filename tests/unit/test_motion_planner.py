"""Tests for P6-T03 motion planner service.

Covers the acceptance criteria:

- output đúng schema (every plan validates via P6-T01);
- unknown template fallback (safe template used);
- all scenes have a MotionPlan (even with no LLM / failing LLM);
- LLM recommendation is allowlisted (unknown names are discarded).
"""

from __future__ import annotations

from app.schemas.motion_plan import MotionPlan, build_motion_plan
from app.schemas.timeline import SceneTimeline
from app.services.motion_planner import (
    SAFE_TEMPLATE,
    MotionPlannerResult,
    MotionPlannerService,
    MotionProjectResult,
    SceneMotionContext,
)
from app.services.motion_templates import template_names

ALL_ROLES = frozenset({"background", "subject", "foreground", "texture", "composite"})


def ctx(
    scene_id="scene_001",
    *,
    voice=5320,
    template="05_stat_number_count",
    roles=ALL_ROLES,
    llm="",
    seed=42,
    timeline=None,
):
    return SceneMotionContext(
        scene_id=scene_id,
        voice_duration_ms=voice,
        template_name=template,
        seed=seed,
        canvas_size=(1920, 1080),
        available_roles=roles,
        llm_recommendation=llm,
        timeline=timeline,
    )


class FakeLLM:
    """Duck-typed LLM provider that returns a canned, allowlisted response."""

    def __init__(self, *, template="08_photo_stack_shuffle", seed=7, easing="spring", fail=False) -> None:
        self.template = template
        self.seed = seed
        self.easing = easing
        self.fail = fail
        self.calls = 0

    async def generate_json(self, **_kwargs) -> dict:
        self.calls += 1
        if self.fail:
            raise RuntimeError("llm down")
        return {"template": self.template, "seed": self.seed, "easing": self.easing}


async def plan(scene_ctx, *, llm=None, preset=None) -> MotionPlannerResult:
    svc = MotionPlannerService(llm_provider=llm, preset=preset)
    return await svc.plan_scene(scene_ctx)


# --------------------------------------------------------------------------- #
# AC: output đúng schema
# --------------------------------------------------------------------------- #
async def test_plan_output_valid_schema() -> None:
    result = await plan(ctx())
    assert result.ok
    assert isinstance(result.plan, MotionPlan)
    # re-validating the serialized form must pass P6-T01
    build_motion_plan(result.plan.to_dict())


async def test_plan_output_has_derived_frame_count() -> None:
    result = await plan(ctx(voice=5320))
    assert result.plan.frame_count == 170


async def test_plan_respects_voice_duration() -> None:
    result = await plan(ctx(voice=3000))
    assert result.plan.duration_ms == 3340


async def test_plan_uses_supplied_canonical_timeline() -> None:
    timeline = SceneTimeline.from_voice(
        "scene_001",
        voice_duration_ms=1800,
        fps=30,
        lead_in_ms=80,
        lead_out_ms=120,
    )
    result = await plan(ctx(voice=9999, timeline=timeline))

    assert result.ok
    assert result.plan.duration_ms == 2000
    assert result.plan.frame_count == 60


# --------------------------------------------------------------------------- #
# AC: unknown template fallback
# --------------------------------------------------------------------------- #
async def test_unknown_template_falls_back_to_safe() -> None:
    result = await plan(ctx(template="not_a_real_template"))
    assert result.ok
    assert result.template_used == SAFE_TEMPLATE
    assert result.plan is not None


async def test_llm_unknown_template_discarded() -> None:
    # LLM recommends an unknown template -> discarded; the scene's own
    # (valid) template is retained (never an untrusted name).
    llm = FakeLLM(template="99_hack_move")
    result = await plan(ctx(template="05_stat_number_count"), llm=llm)
    assert result.ok
    assert result.template_used == "05_stat_number_count"


async def test_scene_unknown_template_uses_safe() -> None:
    # A scene whose *own* template is unknown falls back to the safe template.
    result = await plan(ctx(template="not_a_real_template"), llm=None)
    assert result.ok
    assert result.template_used == SAFE_TEMPLATE


# --------------------------------------------------------------------------- #
# AC: all scenes have a MotionPlan
# --------------------------------------------------------------------------- #
async def test_project_planning_all_scenes() -> None:
    scenes = [
        ctx("scene_001", template="01_subject_slide_headline_pop"),
        ctx("scene_002", template="03_map_pan_marker_pulse"),
        ctx("scene_003", template="bogus"),  # falls back
    ]
    result = await MotionPlannerService().plan_project("prj", scenes)
    assert isinstance(result, MotionProjectResult)
    assert result.all_scenes_have_plan
    assert len(result.plans) == 3


async def test_no_llm_still_plans_every_scene() -> None:
    scenes = [ctx(f"scene_{i}", template=t) for i, t in enumerate(template_names()[:4])]
    result = await MotionPlannerService().plan_project("prj", scenes)
    assert result.all_scenes_have_plan


async def test_failing_llm_still_plans() -> None:
    llm = FakeLLM(fail=True)
    result = await plan(ctx(), llm=llm)
    assert result.ok
    assert result.plan is not None
    assert not result.llm_used


# --------------------------------------------------------------------------- #
# LLM recommendation is allowlisted
# --------------------------------------------------------------------------- #
async def test_llm_template_override_applied() -> None:
    llm = FakeLLM(template="08_photo_stack_shuffle")
    result = await plan(ctx(template="01_subject_slide_headline_pop"), llm=llm)
    assert result.ok
    assert result.template_used == "08_photo_stack_shuffle"
    assert result.llm_used


async def test_llm_easing_override_applied_and_valid() -> None:
    llm = FakeLLM(easing="bounce")
    result = await plan(ctx(), llm=llm)
    assert result.ok
    # some track carries the bounce easing now
    any_bounce = False
    for layer in result.plan.layers:
        for track in layer.get("transform", {}).values():
            if isinstance(track, dict) and track.get("easing") == "bounce":
                any_bounce = True
    assert any_bounce


async def test_llm_bad_easing_ignored() -> None:
    # A fake LLM that returns an invalid easing must not break the plan.
    llm = FakeLLM(easing="teleport")
    result = await plan(ctx(), llm=llm)
    assert result.ok
    assert result.plan is not None


# --------------------------------------------------------------------------- #
# Asset availability prunes layers
# --------------------------------------------------------------------------- #
async def test_missing_role_layer_pruned() -> None:
    result = await plan(ctx(roles=frozenset({"background", "subject"})))
    assert result.ok
    roles = {layer["asset_role"] for layer in result.plan.layers}
    # only roles with a prepared asset remain
    assert roles <= {"background", "subject"}


async def test_preset_forces_template() -> None:
    result = await plan(ctx(template="01_subject_slide_headline_pop"), preset={"template": "12_conclusion_lockup"})
    assert result.ok
    assert result.template_used == "12_conclusion_lockup"
