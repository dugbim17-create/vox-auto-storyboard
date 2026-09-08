"""Script analysis pipeline service (P2-T05).

Normalizes a raw narration/script and turns it into a validated, persisted
storyboard via an LLM planner. Follows MASTER_PLAN section 7 (duration/scene
estimation) and section 7.3 (planner -> validate -> repair loop).

Pipeline steps:

1. normalize script;
2. word count;
3. estimate duration (2.7–3.3 words/s, default 3.0);
4. estimate scene count (clamp 4..20, section 7.2);
5. planner call (LLM generates storyboard JSON);
6. schema validate;
7. repair call (repair_json prompt, max 2 attempts) if validation fails;
8. persist (storyboard.json manifest + DB scenes + project status).

The ``planner`` argument is duck-typed against the ``LLMProvider`` protocol so
tests can inject a fake LLM and run the whole pipeline without a network call.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.state_machine import StateMachine
from app.schemas.storyboard import StoryboardValidationError, validate_storyboard
from app.services.canonical_visual_planner import CanonicalVisualPlanner
from app.services.prompts import get_prompt_pack
from app.storage.asset_store import AssetStore
from app.storage.repositories import SceneRepo

logger = logging.getLogger(__name__)

# Section 7.1 / 7.2 defaults.
DEFAULT_WORDS_PER_SECOND = 3.0
MIN_WORDS_PER_SECOND = 2.7
MAX_WORDS_PER_SECOND = 3.3
TARGET_SCENE_SECONDS = 5.5
MIN_SCENES = 4
MAX_SCENES = 20

# Planner may deviate up to ~25% from the heuristic scene count (section 7.2).
SCENE_COUNT_TOLERANCE = 0.25

MAX_REPAIR_ATTEMPTS = 2


class ScriptAnalysisError(Exception):
    """Raised when the pipeline cannot produce a valid storyboard."""


@dataclass
class ScriptAnalysis:
    """Result of running the script-analysis pipeline."""

    project_id: str
    storyboard: dict[str, Any]
    storyboard_path: Path
    scene_count: int
    word_count: int
    estimated_duration_seconds: float
    estimated_scene_count_heuristic: int
    planner_calls: int = 0
    repair_calls: int = 0
    elapsed_ms: int = 0
    warnings: list[str] = field(default_factory=list)


class ScriptAnalyzer:
    """Orchestrates the script -> storyboard pipeline for one project."""

    def __init__(
        self,
        planner_provider: Any,
        *,
        words_per_second: float = DEFAULT_WORDS_PER_SECOND,
        style_preset: Any = None,
        target_scene_seconds: float = TARGET_SCENE_SECONDS,
    ) -> None:
        self.planner = planner_provider
        self.pack = getattr(planner_provider, "prompt_pack", None) or get_prompt_pack()
        self.words_per_second = _clamp_float(words_per_second, MIN_WORDS_PER_SECOND, MAX_WORDS_PER_SECOND)
        self.target_scene_seconds = target_scene_seconds
        self.style_preset = style_preset

    # ------------------------------------------------------------------ #
    # Pipeline entrypoint
    # ------------------------------------------------------------------ #
    async def analyze(
        self,
        project_id: str,
        script_text: str,
        session: Any,
        *,
        project_root: str | Path | None = None,
        temperature: float = 0.2,
    ) -> ScriptAnalysis:
        """Run the full pipeline for a project. Commits when successful."""
        start = time.monotonic()
        normalized = normalize_script(script_text)
        word_count = count_words(normalized)
        voice_seconds = word_count / self.words_per_second
        heuristic_scenes = estimate_scene_count(voice_seconds, self.target_scene_seconds)

        # --- planner call (step 5) ---
        plan = await self._planner_call(normalized, heuristic_scenes, temperature=temperature)
        plan = _normalize_storyboard(plan)

        # --- validate (step 6); repair loop (step 7) ---
        plan, repair_calls = await self._validate_with_repair(plan, temperature=temperature)

        # --- persist (step 8) ---
        storyboard_path = self._persist_manifest(project_id, plan, normalized, project_root)
        self._persist_db(project_id, plan, session)

        return ScriptAnalysis(
            project_id=project_id,
            storyboard=plan,
            storyboard_path=storyboard_path,
            scene_count=len(plan["scenes"]),
            word_count=word_count,
            estimated_duration_seconds=voice_seconds,
            estimated_scene_count_heuristic=heuristic_scenes,
            planner_calls=1,
            repair_calls=repair_calls,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    async def plan_canonical_visuals(
        self,
        storyboard: dict[str, Any],
        *,
        project_id: str,
        voice_durations_ms: dict[str, int],
        project_root: str | Path | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Use the configured CLIProxy-compatible model for canonical visuals."""
        scenes = await CanonicalVisualPlanner(self.planner).plan(
            project_id=project_id,
            storyboard=storyboard,
            voice_durations_ms=voice_durations_ms,
            temperature=temperature,
        )
        by_id = {
            str(scene.get("scene_id") or ""): scene
            for scene in storyboard.get("scenes", [])
            if isinstance(scene, dict)
        }
        for scene_id, canonical in scenes.items():
            by_id[scene_id]["canonical_visual_scene"] = _canonical_payload(canonical)
        AssetStore(project_root).write_manifest(
            project_id,
            "canonical_scenes.json",
            {
                "schema_version": "vox.scene-set/1.0",
                "kind": "canonical_scenes",
                "project_id": project_id,
                "scenes": [_canonical_payload(scenes[scene_id]) for scene_id in sorted(scenes)],
            },
        )
        return storyboard

    async def plan_scenes_v3(
        self,
        storyboard: dict[str, Any],
        *,
        evidence_pack: Any,
        project_id: str,
        voice_durations_ms: dict[str, int] | None = None,
        project_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """Production v3 planning route integrating SceneDirectorV3 (Phase 2B)."""
        import shutil
        import tempfile

        from app.schemas.scene_spec_v3 import ALLOWED_SCENE_GRAMMARS, SceneSpecV3
        from app.schemas.story_evidence import StoryEvidenceError, StoryEvidencePack
        from app.services.scene_director_v3 import SceneDirectorV3
        from app.services.scene_spec_validator import SceneValidationError

        # Strict mapping normalization and project_id matching
        if isinstance(evidence_pack, dict):
            pack_obj = StoryEvidencePack.from_mapping_strict(evidence_pack)
        elif isinstance(evidence_pack, StoryEvidencePack):
            pack_obj = evidence_pack
            pack_obj.validate_pack()
        else:
            raise TypeError(f"evidence_pack must be StoryEvidencePack or dict, got {type(evidence_pack).__name__}")

        sb_proj = str(storyboard.get("project_id") or "")
        if sb_proj and sb_proj != project_id:
            raise StoryEvidenceError(
                f"Storyboard project_id '{sb_proj}' does not match requested project_id '{project_id}'.",
                reason_code="PROJECT_ID_MISMATCH",
            )
        if pack_obj.project_id != project_id:
            raise StoryEvidenceError(
                f"EvidencePack project_id '{pack_obj.project_id}' does not match requested project_id '{project_id}'.",
                reason_code="PROJECT_ID_MISMATCH",
            )

        voice_durations_ms = voice_durations_ms or {}
        staged_specs: list[tuple[dict[str, Any], SceneSpecV3]] = []

        # Stage 1: Validate in memory using a fresh director
        temp_stage_dir = Path(tempfile.mkdtemp(prefix="vox_v3_stage_"))
        try:
            stage_director = SceneDirectorV3(storage_root=temp_stage_dir)
            for scene in storyboard.get("scenes", []):
                if not isinstance(scene, dict):
                    raise SceneValidationError("Malformed scene: scene entry must be a dictionary.", reason_code="MALFORMED_SCENE")
                scene_id = str(scene.get("scene_id") or "").strip()
                if not scene_id:
                    raise SceneValidationError("Scene requires non-empty scene_id.", reason_code="INVALID_SCENE_ID")

                dur_ms = int(voice_durations_ms.get(scene_id) or float(scene.get("estimated_duration_seconds") or 4.0) * 1000)

                raw_grammar = scene.get("grammar") or scene.get("motion_template")
                if not raw_grammar or raw_grammar not in ALLOWED_SCENE_GRAMMARS:
                    raise SceneValidationError(
                        f"Invalid scene grammar '{raw_grammar}' for scene '{scene_id}'. Production v3 route rejects unsupported grammars without fallback.",
                        reason_code="INVALID_SCENE_GRAMMAR",
                        scene_id=scene_id,
                    )
                grammar = str(raw_grammar)
                visual_thesis = str(scene.get("visual_thesis") or scene.get("visual_summary") or "").strip()
                if not visual_thesis:
                    raise SceneValidationError(
                        f"Scene '{scene_id}' requires a non-empty visual_thesis.",
                        reason_code="INVALID_VISUAL_THESIS",
                        scene_id=scene_id,
                    )

                actions = scene.get("actions") or []
                params = scene.get("params") or {}
                grammar_contract = scene.get("grammar_contract")
                purpose = str(scene.get("purpose") or "body")
                source_unit_ids = scene.get("source_unit_ids")
                evidence_ids = scene.get("evidence_ids")
                must_show = scene.get("must_show")
                must_not_invent = scene.get("must_not_invent")
                asset_requirements = scene.get("asset_requirements")
                authority_order = scene.get("authority_order")
                start_state = scene.get("start_state")
                end_state = scene.get("end_state")
                hold_policy = scene.get("hold_policy")
                exit_policy = scene.get("exit_policy")
                composition = scene.get("composition")
                continuity_in = scene.get("continuity_in")
                continuity_out = scene.get("continuity_out")
                renderer_profile = str(scene.get("renderer_profile") or "vox_classic")
                seed_policy = scene.get("seed_policy")
                narration_anchors = scene.get("narration_anchors")
                fps = int(scene.get("fps") or 30)
                motion_fps = int(scene.get("motion_fps") or 12)

                spec = stage_director.plan_scene(
                    project_id=project_id,
                    scene_id=scene_id,
                    script_text=str(scene.get("narration_text") or ""),
                    evidence_pack=pack_obj,
                    grammar=grammar,
                    visual_thesis=visual_thesis,
                    duration_ms=dur_ms,
                    purpose=purpose,
                    source_unit_ids=source_unit_ids,
                    evidence_ids=evidence_ids,
                    must_show=must_show,
                    must_not_invent=must_not_invent,
                    asset_requirements=asset_requirements,
                    authority_order=authority_order,
                    actions=actions,
                    grammar_contract=grammar_contract,
                    params=params,
                    start_state=start_state,
                    end_state=end_state,
                    hold_policy=hold_policy,
                    exit_policy=exit_policy,
                    composition=composition,
                    continuity_in=continuity_in,
                    continuity_out=continuity_out,
                    renderer_profile=renderer_profile,
                    seed_policy=seed_policy,
                    narration_anchors=narration_anchors,
                    fps=fps,
                    motion_fps=motion_fps,
                )
                staged_specs.append((scene, spec))

            # Stage 2: All scenes validated! Promote to production storage atomically
            prod_root = Path(project_root) if project_root else None
            prod_director = SceneDirectorV3(storage_root=prod_root)
            v3_specs: list[dict[str, Any]] = []
            for scene, spec in staged_specs:
                prod_director.persist_scene_spec(spec, project_root=prod_root)
                scene["scene_spec_v3"] = spec.to_dict()
                v3_specs.append(spec.to_dict())

            store = AssetStore(project_root)
            store.write_manifest(
                project_id,
                "scenes_v3.json",
                {
                    "schema_version": "scene_spec_set/3.0",
                    "project_id": project_id,
                    "scenes": v3_specs,
                },
            )
            return storyboard
        finally:
            shutil.rmtree(temp_stage_dir, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # Sub-steps
    # ------------------------------------------------------------------ #
    async def _planner_call(self, script: str, heuristic_scenes: int, *, temperature: float) -> dict:
        system_prompt = self._system_prompt()
        user_prompt = _planner_user_prompt(
            script=script,
            heuristic_scenes=heuristic_scenes,
            scene_planner=self.pack.load("scene_planner"),
        )
        return await self.planner.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=STORYBOARD_SCHEMA,
            temperature=temperature,
            request_id=f"plan-{int(time.time() * 1000)}",
        )

    async def _validate_with_repair(self, plan: dict, *, temperature: float) -> tuple[dict, int]:
        """Validate and repair up to MAX_REPAIR_ATTEMPTS times."""
        repair_calls = 0
        error = _validate_full(plan)
        while error is not None and repair_calls < MAX_REPAIR_ATTEMPTS:
            repair_calls += 1
            repaired = await self._repair_call(plan, error, temperature=temperature)
            if repaired is not None:
                plan = repaired
            error = _validate_full(plan)
        if error is not None:
            raise ScriptAnalysisError(
                f"storyboard failed validation after {MAX_REPAIR_ATTEMPTS} repairs: {error}"
            )
        return plan, repair_calls

    async def _repair_call(self, storyboard: dict, error: str, *, temperature: float) -> dict | None:
        user_prompt = _repair_user_prompt(
            storyboard=storyboard,
            error=error,
            repair_prompt=self.pack.load("repair_json"),
        )
        try:
            return await self.planner.generate_json(
                system_prompt="You are a JSON repair assistant. Return only corrected JSON.",
                user_prompt=user_prompt,
                schema=STORYBOARD_SCHEMA,
                temperature=temperature,
                request_id=f"repair-{int(time.time() * 1000)}",
            )
        except Exception:  # noqa: BLE001 - a failed repair is not fatal here
            return None

    def _system_prompt(self) -> str:
        if self.style_preset is not None:
            return self.pack.system_prompt(preset=self.style_preset)
        return self.pack.load("system_storyboard")

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _persist_manifest(
        self, project_id: str, storyboard: dict, script_text: str, project_root: str | Path | None
    ) -> Path:
        store = AssetStore(project_root)
        store.init_project(project_id)
        storyboard["project_id"] = project_id
        storyboard.setdefault("script_text", script_text)
        path, _ = store.write_manifest(project_id, "storyboard.json", storyboard)
        return path

    def _persist_db(self, project_id: str, storyboard: dict, session: Any) -> None:
        state = StateMachine(session)

        # Move project INGESTED -> SCRIPT_ANALYZED (first step; STORYBOARD_DRAFTED
        # is recorded as a separate forward step below).
        try:
            state.transition_project(project_id, "SCRIPT_ANALYZED", reason="script analyzed")
        except Exception as exc:  # noqa: BLE001
            logger.warning("project transition to SCRIPT_ANALYZED skipped: %s", exc)

        # Replace any prior scenes (idempotent re-planning).
        for old in SceneRepo.list(session, project_id):
            session.delete(old)

        for scene in storyboard.get("scenes", []):
            span = scene.get("script_span", {})
            SceneRepo.add(
                session,
                project_id,
                scene_id=scene["scene_id"],
                order=scene.get("order"),
                script_start_char=span.get("start_char", 0),
                script_end_char=span.get("end_char", 0),
                narration_text=scene.get("narration_text", ""),
                purpose=scene.get("purpose", ""),
                estimated_duration_seconds=scene.get("estimated_duration_seconds", 0.0),
                visual_summary=scene.get("visual_summary", ""),
                image_prompt=scene.get("image_prompt", ""),
                negative_constraints=json.dumps(scene.get("negative_constraints", []), ensure_ascii=False),
                motion_prompt=_stringify(scene.get("motion_prompt", "")),
                motion_template=scene.get("motion_template", ""),
                transition_out=_stringify(scene.get("transition_out", "hard_cut")),
                status="PLANNED",
            )
        session.commit()

        try:
            state.transition_project(project_id, "STORYBOARD_DRAFTED", reason="scenes persisted")
        except Exception as exc:  # noqa: BLE001
            logger.warning("project transition to STORYBOARD_DRAFTED skipped: %s", exc)
        session.commit()


def _canonical_payload(scene: Any) -> dict[str, Any]:
    return {
        "schema_version": scene.schema_version,
        "project_id": scene.project_id,
        "scene_id": scene.scene_id,
        "revision": scene.revision,
        "grammar": scene.grammar,
        "narration": scene.narration,
        "duration_ms": scene.duration_ms,
        "fps": scene.fps,
        "motion_fps": scene.motion_fps,
        "canvas": {"width": scene.canvas_width, "height": scene.canvas_height},
        "entities": [
            {
                "entity_id": entity.entity_id,
                "kind": entity.kind,
                "role": entity.role,
                "asset": entity.asset,
                "sha256": entity.sha256,
                "x": entity.x,
                "y": entity.y,
                "z": entity.z,
                "metadata": dict(entity.metadata),
            }
            for entity in scene.entities
        ],
        "events": [
            {
                "event_id": event.event_id,
                "anchor": event.anchor,
                "start_ms": event.start_ms,
                "duration_ms": event.duration_ms,
                "action": event.action,
                "target": event.target,
                "source": event.source,
                **dict(event.payload),
            }
            for event in scene.events
        ],
    }


def normalize_script(text: str) -> str:
    """Normalize whitespace and strip leading/trailing blank lines."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def count_words(text: str) -> int:
    """Word count for Vietnamese (space-delimited tokens)."""
    stripped = text.strip()
    return len(stripped.split()) if stripped else 0


def estimate_scene_count(voice_seconds: float, target_scene_seconds: float = TARGET_SCENE_SECONDS) -> int:
    """Section 7.2: clamp(round(voice_seconds / scene_seconds), 4, 20)."""
    return _clamp(voice_seconds / target_scene_seconds)


def _clamp(value: float, lo: int = MIN_SCENES, hi: int = MAX_SCENES) -> int:
    return max(lo, min(hi, int(round(value))))


def _clamp_float(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _validate_full(storyboard: dict) -> str | None:
    try:
        validate_storyboard(storyboard)
        return None
    except StoryboardValidationError as exc:
        return str(exc)


def _planner_user_prompt(script: str, heuristic_scenes: int, scene_planner: str) -> str:
    return (
        f"# Planner instructions\n{scene_planner}\n\n"
        f"The heuristic target is about {heuristic_scenes} scenes. "
        "You may deviate up to 25% if the content structure requires it.\n\n"
        f"## Script\n{script}\n\n"
        "Produce the storyboard JSON now."
    )


def _normalize_storyboard(storyboard: dict) -> dict:
    """Coerce common LLM field-shape deviations back to the schema's preferred
    form so validation passes without burning repair attempts on trivial
    type normalization.

    - ``style_anchor.palette`` / ``texture``: comma-joined string -> [items]
    - ``style_anchor.continuity_rules``: string -> [string]
    - ``characters`` / ``locations``: auto-id missing ``character_id`` /
      ``location_id`` (schema only requires ``name``)
    - ``scene.motion_prompt`` / ``scene.transition_out``: kept (object allowed)
    - ``scene.purpose`` empty -> "body"
    """
    style_anchor = storyboard.get("style_anchor")
    if isinstance(style_anchor, dict):
        for key in ("palette", "texture", "continuity_rules"):
            value = style_anchor.get(key)
            if isinstance(value, str):
                style_anchor[key] = _split_list(value)
    for i, character in enumerate(storyboard.get("characters", [])):
        if isinstance(character, dict) and not character.get("character_id"):
            character["character_id"] = f"char_{i + 1:03d}"
    for i, location in enumerate(storyboard.get("locations", [])):
        if isinstance(location, dict) and not location.get("location_id"):
            location["location_id"] = f"loc_{i + 1:03d}"
    for scene in storyboard.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        if not scene.get("purpose"):
            scene["purpose"] = "body"
        motion_prompt = scene.get("motion_prompt")
        if isinstance(motion_prompt, dict):
            preferred = (
                motion_prompt.get("subject_motion")
                or motion_prompt.get("camera_motion")
                or motion_prompt.get("description")
            )
            if preferred:
                scene["motion_prompt"] = str(preferred)
            else:
                parts = [str(value) for value in motion_prompt.values() if value]
                scene["motion_prompt"] = "; ".join(parts)
        elif motion_prompt is None:
            scene["motion_prompt"] = ""
        if scene.get("transition_out") is None:
            scene["transition_out"] = "hard_cut"
    return storyboard


def _split_list(value: str) -> list[str]:
    """Split a comma-joined string of list items into trimmed strings."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _stringify(value: Any) -> str:
    """Turn dict/list values into compact JSON (for DB Text columns)."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _repair_user_prompt(storyboard: dict, error: str, repair_prompt: str) -> str:
    return (
        f"# Repair instructions\n{repair_prompt}\n\n"
        f"## Validation error\n{error}\n\n"
        "## Failing JSON\n"
        f"{json.dumps(storyboard, ensure_ascii=False)}\n\n"
        "Return the corrected JSON now."
    )


def join_storyboard_evidence(
    storyboard: dict[str, Any],
    evidence_pack: Any,
    scene_bindings: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Join StoryEvidencePack and scene evidence bindings into a storyboard dict.

    F4: Validates pack, project matching, and referenced scene evidence integrity.
    Preserves all existing storyboard structure.
    """
    from app.schemas.story_evidence import StoryEvidenceError, StoryEvidencePack

    # Parse and validate pack
    if isinstance(evidence_pack, dict):
        pack_obj = StoryEvidencePack.from_dict(evidence_pack)
    elif isinstance(evidence_pack, StoryEvidencePack):
        pack_obj = evidence_pack
    else:
        raise StoryEvidenceError(
            f"evidence_pack must be a StoryEvidencePack instance or dict, got {type(evidence_pack).__name__}.",
            reason_code="INVALID_EVIDENCE_PACK",
        )

    pack_obj.validate_pack()

    # Validate project_id match
    sb_proj = str(storyboard.get("project_id") or "")
    if sb_proj and sb_proj != pack_obj.project_id:
        raise StoryEvidenceError(
            f"Storyboard project_id '{sb_proj}' does not match StoryEvidencePack project_id '{pack_obj.project_id}'.",
            reason_code="PROJECT_ID_MISMATCH",
        )

    result = json.loads(json.dumps(storyboard, ensure_ascii=False))
    result["evidence_pack"] = pack_obj.to_dict()

    scene_bindings = scene_bindings or {}
    for scene in result.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id") or "")
        binding = scene_bindings.get(scene_id)
        if binding:
            ev_ids = list(binding.get("evidence_ids") or [])
            # F4: Verify all referenced evidence_ids exist in pack
            for ev_id in ev_ids:
                claim = pack_obj.get_claim(ev_id)
                if claim is None:
                    raise StoryEvidenceError(
                        f"Scene '{scene_id}' references unknown evidence_id '{ev_id}' not found in StoryEvidencePack.",
                        reason_code="UNKNOWN_EVIDENCE_ID",
                    )

            # F4: Verify scene must_show entities belong to referenced claims
            must_show_ids = list(binding.get("must_show") or [])
            if must_show_ids:
                allowed_entity_ids: set[str] = set()
                for ev_id in ev_ids:
                    cl = pack_obj.get_claim(ev_id)
                    if cl:
                        allowed_entity_ids.update(cl.must_show)
                        allowed_entity_ids.update(e.entity_id for e in cl.entities)
                for m_id in must_show_ids:
                    if m_id not in allowed_entity_ids:
                        raise StoryEvidenceError(
                            f"Scene '{scene_id}' declares must_show entity '{m_id}' not found in referenced claims {ev_ids}.",
                            reason_code="UNDECLARED_MUST_SHOW",
                        )

            if "evidence_ids" in binding:
                scene["evidence_ids"] = ev_ids
            if "must_show" in binding:
                scene["must_show"] = must_show_ids
            if "must_not_invent" in binding:
                scene["must_not_invent"] = list(binding["must_not_invent"])
            if "claim_risk" in binding:
                scene["claim_risk"] = str(binding["claim_risk"])
            if "asset_policy" in binding:
                scene["asset_policy"] = str(binding["asset_policy"])

    return result


STORYBOARD_SCHEMA = {
    "type": "object",
    "required": ["summary", "style_anchor", "characters", "locations", "scenes"],
}
