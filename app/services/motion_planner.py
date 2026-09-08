"""Motion planner service (P6-T03).

Combines, per scene:

- LLM motion recommendation (allow-list only — the LLM picks a template name
  and parameter overrides, never free-form FFmpeg filters);
- a safe template (the scene's storyboard ``motion_template``, or a default
  when the LLM names something unknown);
- voice duration (``Scene.actual_voice_duration_ms``);
- asset availability (only layers whose role has a prepared asset are kept);
- preset (a named preset may force a template / seed / canvas).

The output of every scene is a validated ``MotionPlan`` (P6-T01 schema), so a
project that moves through the planner always ends up with a motion plan per
scene — the renderer never has to guess.

Acceptance criteria (MASTER_PLAN P6-T03):

- output đúng schema (validated MotionPlan);
- unknown template fallback (safe template used);
- all scenes have a MotionPlan (even when the LLM is unavailable).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.schemas.editorial_timeline import VoiceTimeline
from app.schemas.motion_plan import (
    ALLOWED_EASINGS as ALLOWED_EASING_NAMES,
)
from app.schemas.motion_plan import MotionPlan, MotionPlanError, build_motion_plan
from app.schemas.timeline import SceneTimeline
from app.services.motion_templates import (
    MotionTemplateError,
    build_template,
    template_names,
)

logger = logging.getLogger(__name__)

DEFAULT_FPS = 30
DEFAULT_CANVAS = (1920, 1080)
# When a scene has no recorded voice duration, use this fallback.
DEFAULT_VOICE_DURATION_MS = 5000
# Allowed template names the LLM may recommend; anything else falls back.
TEMPLATE_ALLOWLIST = frozenset(template_names())

# The safe fallback template when the LLM names an unknown one.
SAFE_TEMPLATE = "01_subject_slide_headline_pop"


@dataclass
class SceneMotionContext:
    """Per-scene inputs the planner needs."""

    scene_id: str
    voice_duration_ms: int
    template_name: str = SAFE_TEMPLATE
    seed: int = 42
    canvas_size: tuple[int, int] = DEFAULT_CANVAS
    available_roles: frozenset[str] = frozenset()  # roles with a prepared asset
    llm_recommendation: str = ""  # template name recommended by the LLM (if any)
    timeline: SceneTimeline | None = None
    voice_timeline: VoiceTimeline | None = None


@dataclass
class MotionPlannerResult:
    """Outcome of planning motion for one scene."""

    scene_id: str
    ok: bool
    plan: MotionPlan | None = None
    template_used: str = ""
    llm_used: bool = False
    error: str = ""


@dataclass
class MotionProjectResult:
    """Outcome of planning motion for every scene in a project."""

    project_id: str
    scenes: list[MotionPlannerResult] = field(default_factory=list)

    @property
    def plans(self) -> list[MotionPlan]:
        return [r.plan for r in self.scenes if r.plan is not None]

    @property
    def all_scenes_have_plan(self) -> bool:
        return bool(self.scenes) and all(r.plan is not None for r in self.scenes)


class MotionPlannerError(Exception):
    """Raised when motion planning fails unrecoverably."""


class MotionPlannerService:
    """Plan motion for all scenes in a project."""

    def __init__(
        self,
        *,
        llm_provider: Any | None = None,
        template_builder: Callable[..., dict] | None = None,
        canvas_size: tuple[int, int] = DEFAULT_CANVAS,
        fps: int = DEFAULT_FPS,
        seed: int = 42,
        preset: dict[str, Any] | None = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.template_builder = template_builder or build_template
        self.canvas_size = canvas_size
        self.fps = fps
        self.seed = seed
        self.preset = preset or {}

    # ------------------------------------------------------------------ #
    # Entrypoint
    # ------------------------------------------------------------------ #
    async def plan_scene(self, ctx: SceneMotionContext) -> MotionPlannerResult:
        """Plan motion for one scene; never raises for a bad recommendation."""
        # Resolve the template name: preset > scene template > safe fallback.
        template_name = self._resolve_template(ctx)

        # LLM may also provide parameter overrides (allowlisted keys only).
        overrides = {}
        if self.llm_provider is not None:
            try:
                overrides = await self._llm_overrides(ctx, template_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("scene %s: LLM motion recommendation failed (%s)", ctx.scene_id, exc)
                overrides = {}

        # The LLM's template override (already allowlisted) wins over the
        # scene's own template.
        if overrides.get("template"):
            template_name = overrides["template"]
        llm_used = bool(overrides) or bool(ctx.llm_recommendation)

        scene_timeline = ctx.timeline or SceneTimeline.from_voice(
            ctx.scene_id,
            ctx.voice_duration_ms or DEFAULT_VOICE_DURATION_MS,
            fps=self.fps,
        )
        duration_ms = scene_timeline.visual_duration_ms
        duration_ms = self.preset.get("duration_ms", duration_ms)

        try:
            raw = self.template_builder(
                template_name,
                ctx.scene_id,
                int(duration_ms),
                seed=ctx.seed if overrides.get("seed") is None else int(overrides["seed"]),
                canvas_size=ctx.canvas_size,
            )
            raw = self._prune_unavailable_layers(raw, ctx.available_roles)
            raw = _apply_overrides(raw, overrides)
            plan = build_motion_plan(raw)
        except (MotionTemplateError, MotionPlanError) as exc:
            return MotionPlannerResult(
                scene_id=ctx.scene_id, ok=False, error=str(exc)
            )

        return MotionPlannerResult(
            scene_id=ctx.scene_id,
            ok=True,
            plan=plan,
            template_used=template_name,
            llm_used=llm_used,
        )

    # ------------------------------------------------------------------ #
    # Template resolution (unknown template fallback)
    # ------------------------------------------------------------------ #
    def _resolve_template(self, ctx: SceneMotionContext) -> str:
        # Preset forces a template (highest priority).
        preset_tpl = self.preset.get("template")
        if preset_tpl:
            return _allowlisted_or_safe(preset_tpl)
        # LLM recommendation, if it is on the allowlist.
        if ctx.llm_recommendation:
            return _allowlisted_or_safe(ctx.llm_recommendation)
        # The storyboard's own template, allowlisted too.
        if ctx.template_name:
            return _allowlisted_or_safe(ctx.template_name)
        return SAFE_TEMPLATE

    # ------------------------------------------------------------------ #
    # LLM (allow-list only)
    # ------------------------------------------------------------------ #
    async def _llm_overrides(
        self, ctx: SceneMotionContext, template_name: str
    ) -> dict:
        """Ask the LLM for template parameters; keep only allowlisted keys."""
        if not hasattr(self.llm_provider, "generate_json"):
            return {}
        response = await self.llm_provider.generate_json(
            system_prompt=(
                "You recommend motion parameters for a storyboard scene. "
                "You may only choose values from the provided allowlist. "
                "Never invent easing names, channels, or filters."
            ),
            user_prompt=_motion_user_prompt(ctx, template_name, list(TEMPLATE_ALLOWLIST)),
            schema={
                "type": "object",
                "properties": {
                    "template": {"type": "string"},
                    "seed": {"type": "integer"},
                    "easing": {"type": "string", "enum": sorted(ALLOWED_EASING_NAMES)},
                },
                "required": ["template"],
            },
            temperature=0.2,
            request_id=f"motion-{ctx.scene_id}",
        )
        return _sanitize_overrides(response)

    def _prune_unavailable_layers(self, raw: dict, available_roles: frozenset[str]) -> dict:
        """Drop layers whose asset_role has no prepared asset."""
        if not available_roles:
            return raw
        keep = []
        for layer in raw.get("layers", []):
            role = layer.get("asset_role", "")
            if role in available_roles:
                keep.append(layer)
            else:
                logger.debug("scene: dropping layer role %r (asset unavailable)", role)
        raw = dict(raw)
        raw["layers"] = keep or raw.get("layers", [])
        return raw

    # ------------------------------------------------------------------ #
    # Project-wide planning
    # ------------------------------------------------------------------ #
    async def plan_project(
        self,
        project_id: str,
        scenes: list[SceneMotionContext],
    ) -> MotionProjectResult:
        """Plan every scene; one bad scene does not stop the others."""
        result = MotionProjectResult(project_id=project_id)
        for ctx in scenes:
            result.scenes.append(await self.plan_scene(ctx))
        return result


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _allowlisted_or_safe(name: str) -> str:
    return name if name in TEMPLATE_ALLOWLIST else SAFE_TEMPLATE


def _sanitize_overrides(response: dict) -> dict:
    """Keep only allowlisted override keys and coerce their types."""
    out: dict[str, Any] = {}
    tpl = response.get("template")
    if isinstance(tpl, str) and tpl in TEMPLATE_ALLOWLIST:
        out["template"] = tpl
    seed = response.get("seed")
    if isinstance(seed, int) and not isinstance(seed, bool) and 0 <= seed <= 2**32 - 1:
        out["seed"] = seed
    easing = response.get("easing")
    if isinstance(easing, str) and easing in ALLOWED_EASING_NAMES:
        out["easing"] = easing
    return out


def _apply_overrides(raw: dict, overrides: dict) -> dict:
    if "easing" in overrides:
        # Apply the easing to every track that explicitly has one. This keeps
        # the LLM's choice bounded and validated by the schema.
        easing = overrides["easing"]
        for layer in raw.get("layers", []):
            transform = layer.get("transform", {})
            for track in transform.values():
                if isinstance(track, dict) and "easing" in track:
                    track["easing"] = easing
        camera = raw.get("camera", {})
        for track in camera.values():
            if isinstance(track, dict) and "easing" in track:
                track["easing"] = easing
    return raw


def _motion_user_prompt(ctx: SceneMotionContext, template: str, allowlist: list[str]) -> str:
    return (
        f"Scene {ctx.scene_id}, template {template!r}, voice {ctx.voice_duration_ms}ms, "
        f"assets {sorted(ctx.available_roles)}. Allowed templates: {allowlist}. "
        f"Return only template/seed/easing."
    )
