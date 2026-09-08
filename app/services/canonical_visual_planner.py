"""CLIProxy-compatible planner for the single canonical scene contract."""

from __future__ import annotations

import json
import time
from typing import Any

from app.schemas.semantic_scene import CanonicalScene, SemanticSceneError, build_canonical_scene

CANONICAL_VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["scenes"],
    "properties": {
        "scenes": {
            "type": "array",
            "items": {"type": "object"},
        }
    },
}


class CanonicalVisualPlanner:
    """Ask one LLM provider for entity/event/motion scene contracts."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    async def repair(
        self,
        *,
        payload: dict[str, Any],
        error: str,
        project_id: str,
        storyboard: dict[str, Any],
        voice_durations_ms: dict[str, int],
        temperature: float = 0.0,
    ) -> dict[str, CanonicalScene]:
        source_scenes = [item for item in storyboard.get("scenes", []) if isinstance(item, dict)]
        prompt = _visual_prompt(project_id, source_scenes, voice_durations_ms)
        repaired = await self.provider.generate_json(
            system_prompt=(
                "Repair invalid Vox canonical scene JSON. Preserve factual actions and relations. "
                "Every entity needs id, type/kind, asset URI, and transform or x/y. "
                "Every event needs at_ms/start_ms, duration_ms, type/action, and entity target. "
                "Return JSON only."
            ),
            user_prompt=(
                f"Canonical validation error: {error}\n"
                f"Invalid payload: {json.dumps(payload, ensure_ascii=False)}\n"
                f"Original request: {prompt}"
            ),
            schema=CANONICAL_VISUAL_SCHEMA,
            temperature=temperature,
            request_id=f"visual-repair-{int(time.time() * 1000)}",
        )
        return _validate_planned_scenes(
            repaired,
            project_id=project_id,
            source_scenes=source_scenes,
            voice_durations_ms=voice_durations_ms,
        )

    async def plan(
        self,
        *,
        project_id: str,
        storyboard: dict[str, Any],
        voice_durations_ms: dict[str, int],
        temperature: float = 0.2,
    ) -> dict[str, CanonicalScene]:
        source_scenes = [item for item in storyboard.get("scenes", []) if isinstance(item, dict)]
        if not source_scenes:
            raise SemanticSceneError("storyboard requires scenes")
        prompt = _visual_prompt(project_id, source_scenes, voice_durations_ms)
        system_prompt = (
            "You are the visual director for standalone Vox Studio. Return canonical "
            "object-first visual scenes. Typography may support facts but must not be "
            "the only visual representation. Use entities, relationships, and motion."
        )
        try:
            payload = await self.provider.generate_json(
                system_prompt=system_prompt,
                user_prompt=prompt,
                schema=CANONICAL_VISUAL_SCHEMA,
                temperature=temperature,
                request_id=f"visual-plan-{int(time.time() * 1000)}",
            )
        except Exception as exc:  # noqa: BLE001
            payload = await self.provider.generate_json(
                system_prompt=system_prompt,
                user_prompt=(
                    f"Previous response failed JSON parsing: {exc}. "
                    "Return compact strict JSON only; no markdown or commentary.\n\n"
                    f"{prompt}"
                ),
                schema=CANONICAL_VISUAL_SCHEMA,
                temperature=0.0,
                request_id=f"visual-plan-retry-{int(time.time() * 1000)}",
            )
        try:
            return _validate_planned_scenes(
                payload,
                project_id=project_id,
                source_scenes=source_scenes,
                voice_durations_ms=voice_durations_ms,
            )
        except SemanticSceneError as exc:
            return await self.repair(
                payload=payload,
                error=str(exc),
                project_id=project_id,
                storyboard=storyboard,
                voice_durations_ms=voice_durations_ms,
            )


def _validate_planned_scenes(
    payload: dict[str, Any],
    *,
    project_id: str,
    source_scenes: list[dict[str, Any]],
    voice_durations_ms: dict[str, int],
) -> dict[str, CanonicalScene]:
        planned = payload.get("scenes")
        if not isinstance(planned, list):
            raise SemanticSceneError("visual planner scenes must be a list")
        result: dict[str, CanonicalScene] = {}
        for raw in planned:
            if not isinstance(raw, dict):
                raise SemanticSceneError("visual planner scene must be an object")
            scene = build_canonical_scene(_normalize_model_scene(raw))
            expected = int(voice_durations_ms.get(scene.scene_id) or 0)
            if expected <= 0 or scene.duration_ms != expected:
                raise SemanticSceneError(f"canonical duration mismatch: {scene.scene_id}")
            if scene.project_id != project_id:
                raise SemanticSceneError(f"canonical project mismatch: {scene.scene_id}")
            result[scene.scene_id] = scene
        expected_ids = {str(item.get("scene_id") or "") for item in source_scenes}
        if set(result) != expected_ids:
            raise SemanticSceneError("canonical scene cardinality mismatch")
        return result


def _normalize_model_scene(raw: dict[str, Any]) -> dict[str, Any]:
    scene = json.loads(json.dumps(raw, ensure_ascii=False))
    scene["schema_version"] = "vox.scene/2.0"
    try:
        scene["revision"] = int(float(scene.get("revision") or 1))
    except (TypeError, ValueError):
        scene["revision"] = 1
    grammar = scene.get("grammar")
    if isinstance(grammar, dict):
        grammar = grammar.get("type") or grammar.get("name") or grammar.get("grammar")
    grammar = str(grammar or "")
    if grammar not in {
        "character_demonstration", "object_assembly", "map_route",
        "chart_progression", "document_evidence", "explanatory_hold",
    }:
        grammar = "explanatory_hold"
    scene["grammar"] = grammar
    scene["fps"] = 30
    scene["motion_fps"] = min(12, int(scene.get("motion_fps") or 12))
    normalized_entities: list[dict[str, Any]] = []
    for index, item in enumerate(scene.get("entities") or []):
        if not isinstance(item, dict):
            continue
        transform = item.get("transform") or {}
        position = transform.get("position") or [0, 0]
        if isinstance(position, dict):
            position = [position.get("x", 0), position.get("y", 0)]
        if not isinstance(position, (list, tuple)):
            position = [0, 0]
        entity_id = str(item.get("entity_id") or item.get("id") or f"entity_{index + 1:02d}")
        kind = str(item.get("kind") or item.get("type") or "object")
        role = str(item.get("role") or ("background" if kind == "background" or index == 0 else "object"))
        normalized_entities.append(
            {
                **item,
                "entity_id": entity_id,
                "kind": kind,
                "role": role,
                "asset": str(item.get("asset") or f"asset://{kind}/{entity_id}"),
                "x": int(position[0]) if position else 0,
                "y": int(position[1]) if len(position) > 1 else 0,
                "z": int(item.get("z") or index),
            }
        )
    scene["entities"] = normalized_entities
    for entity in scene["entities"]:
        if entity["role"] == "background":
            continue
        asset = str(entity.get("asset") or "")
        if asset.startswith("asset://typography/") or asset.startswith("asset://ui/"):
            entity["asset"] = f"asset://object/{entity['entity_id']}"
        entity.pop("text", None)
        entity.pop("style", None)
    normalized_events: list[dict[str, Any]] = []
    action_map = {
        "fade_in": "reveal",
        "fade_out": "focus",
        "transform": "move",
        "scale": "transform",
        "pulse": "highlight",
        "highlight": "highlight",
        "draw_line": "connect",
        "connect": "connect",
    }
    for index, item in enumerate(scene.get("events") or []):
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or item.get("entity_id") or item.get("subject") or "")
        raw_action = str(item.get("action") or item.get("type") or "reveal")
        if raw_action in action_map:
            action = action_map[raw_action]
        elif raw_action in {
            "layer_transform", "pose_sequence", "object_path", "secondary_loop",
            "path_draw", "traveling_marker", "chart_series", "counter_progress",
            "region_highlight", "document_focus", "state_swap", "focus_shift",
            "text_reveal", "explicit_hold", "exit_policy", "reveal", "move",
            "connect", "disconnect", "merge", "transform", "highlight", "focus",
        }:
            action = raw_action
        else:
            raise SemanticSceneError(f"unsupported action: {raw_action}")
        event = {
            **item,
            "event_id": str(item.get("event_id") or f"event_{index + 1:02d}"),
            "anchor": str(item.get("anchor") or scene.get("narration") or "visual event"),
            "start_ms": int(item.get("start_ms") if item.get("start_ms") is not None else item.get("at_ms") or 0),
            "duration_ms": int(item.get("duration_ms") or 400),
            "action": action,
            "target": target,
            "source": str(item.get("source") or ""),
        }
        target_transform = item.get("target_transform") or {}
        position = target_transform.get("position") or []
        if isinstance(position, dict):
            position = [position.get("x", 0), position.get("y", 0)]
        if action == "move" and len(position) >= 2:
            event["to_x"] = int(position[0])
            event["to_y"] = int(position[1])
        normalized_events.append(event)
    scene["events"] = sorted(normalized_events, key=lambda item: item["start_ms"])
    if scene["events"]:
        for event in scene["events"]:
            event["duration_ms"] = min(
                int(event["duration_ms"]),
                int(scene["duration_ms"]) - int(event["start_ms"]),
            )
    return scene


def _visual_prompt(
    project_id: str,
    scenes: list[dict[str, Any]],
    durations: dict[str, int],
) -> str:
    source = [
        {
            "scene_id": str(scene.get("scene_id") or ""),
            "narration": str(scene.get("narration_text") or ""),
            "purpose": str(scene.get("purpose") or ""),
            "duration_ms": int(durations.get(str(scene.get("scene_id") or "")) or 0),
        }
        for scene in scenes
    ]
    return (
        "Return {\"scenes\": [...]} using schema_version vox.scene/2.0. "
        "Each scene must include project_id, scene_id, revision, grammar, narration, "
        "duration_ms, fps, motion_fps, canvas, entities, and ordered events. "
        "Every scene needs a background entity. Factual actions must be represented "
        "by object/entity motion or relationships, not labels alone. Asset values are "
        "logical asset requests such as asset://jobs/profile and will be materialized "
        "by Vox after planning.\n\n"
        f"Project: {project_id}\n"
        f"Scenes: {json.dumps(source, ensure_ascii=False)}"
    )


__all__ = ["CANONICAL_VISUAL_SCHEMA", "CanonicalVisualPlanner"]
