"""Versioned canonical contract for deterministic semantic scenes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

ALLOWED_GRAMMARS = {
    "character_demonstration",
    "object_assembly",
    "map_route",
    "chart_progression",
    "document_evidence",
    "explanatory_hold",
}
ALLOWED_ACTIONS = {
    "layer_transform",
    "pose_sequence",
    "object_path",
    "secondary_loop",
    "path_draw",
    "traveling_marker",
    "chart_series",
    "counter_progress",
    "region_highlight",
    "document_focus",
    "state_swap",
    "focus_shift",
    "text_reveal",
    "explicit_hold",
    "exit_policy",
    "reveal",
    "move",
    "connect",
    "disconnect",
    "merge",
    "transform",
    "highlight",
    "focus",
}


class SemanticSceneError(ValueError):
    """Raised when a semantic scene contract is invalid."""


@dataclass(frozen=True)
class CanonicalEntity:
    entity_id: str
    kind: str
    role: str
    asset: str
    sha256: str
    x: int
    y: int
    z: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    anchor: str
    start_ms: int
    duration_ms: int
    action: str
    target: str
    source: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CanonicalScene:
    schema_version: str
    project_id: str
    scene_id: str
    revision: int
    grammar: str
    narration: str
    duration_ms: int
    fps: int
    motion_fps: int
    canvas_width: int
    canvas_height: int
    entities: tuple[CanonicalEntity, ...]
    events: tuple[CanonicalEvent, ...]
    sha256: str

    @property
    def entity_ids(self) -> tuple[str, ...]:
        return tuple(entity.entity_id for entity in self.entities)

    @property
    def visual_action_count(self) -> int:
        return len(self.events)

    @property
    def background_entity(self) -> CanonicalEntity:
        return next(entity for entity in self.entities if entity.role == "background")

    def to_render_plan(self) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        for event in self.events:
            action = dict(event.payload)
            action.update(
                {
                    "action_id": event.event_id,
                    "type": event.action,
                    "subject": event.target,
                    "target": event.target,
                    "source": event.source,
                    "start_ms": event.start_ms,
                    "end_ms": event.start_ms + event.duration_ms,
                    "narration_anchor": event.anchor,
                }
            )
            actions.append(action)
        return {
            "schema_version": "vox.semantic.plan/2",
            "scene_id": self.scene_id,
            "grammar": self.grammar,
            "duration_ms": self.duration_ms,
            "fps": self.fps,
            "motion_fps": self.motion_fps,
            "canvas": {"width": self.canvas_width, "height": self.canvas_height},
            "assets": {entity.entity_id: entity.asset for entity in self.entities},
            "placements": {entity.entity_id: [entity.x, entity.y] for entity in self.entities},
            "z_order": {entity.entity_id: entity.z for entity in self.entities},
            "procedural_actions": actions,
            "canonical_scene_sha256": self.sha256,
        }


def _canonical_sha256(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SemanticSceneSpec:
    payload: dict[str, Any]
    sha256: str

    @property
    def scene_id(self) -> str:
        return str(self.payload["scene_id"])

    def to_canonical_scene(self) -> CanonicalScene:
        payload = self.payload
        entities = [
            {
                "entity_id": asset["asset_id"],
                "kind": asset.get("kind") or "rgba_image",
                "role": asset.get("role") or "object",
                "asset": asset.get("path") or "",
                "sha256": asset.get("sha256") or "",
                "x": int((asset.get("placement") or [0, 0])[0]),
                "y": int((asset.get("placement") or [0, 0])[1]),
                "z": int(asset.get("z") or 10),
            }
            for asset in payload["assets"]
        ]
        events: list[dict[str, Any]] = []
        cursor = 0
        for beat in payload["beats"]:
            for action in beat["actions"]:
                event = dict(action)
                event.update(
                    {
                        "event_id": action["action_id"],
                        "anchor": beat["anchor"],
                        "start_ms": int(action.get("start_ms", cursor)),
                        "action": action["type"],
                        "target": action.get("subject") or (action.get("variants") or [""])[0],
                    }
                )
                events.append(event)
                cursor = event["start_ms"] + int(event["duration_ms"])
        return build_canonical_scene(
            {
                "schema_version": "vox.scene/2.0",
                "project_id": payload["project_id"],
                "scene_id": payload["scene_id"],
                "revision": payload["revision"],
                "grammar": payload["grammar"],
                "narration": " ".join(str(beat["anchor"]) for beat in payload["beats"]),
                "duration_ms": payload["duration_ms"],
                "fps": payload["fps"],
                "motion_fps": payload["motion_fps"],
                "canvas": payload.get("canvas") or {},
                "entities": entities,
                "events": events,
            }
        )


def build_semantic_scene_spec(data: Any) -> SemanticSceneSpec:
    if not isinstance(data, dict):
        raise SemanticSceneError("semantic scene must be an object")
    payload = json.loads(json.dumps(data, ensure_ascii=False))
    if payload.get("schema_version") != "vox.scene/1.0":
        raise SemanticSceneError("schema_version must be vox.scene/1.0")
    for key in ("project_id", "scene_id", "grammar"):
        if not str(payload.get(key) or "").strip():
            raise SemanticSceneError(f"{key} is required")
    if payload["grammar"] not in ALLOWED_GRAMMARS:
        raise SemanticSceneError(f"unsupported grammar: {payload['grammar']}")
    for key in ("revision", "duration_ms", "fps", "motion_fps"):
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise SemanticSceneError(f"{key} must be a positive integer")
    if payload["motion_fps"] > payload["fps"]:
        raise SemanticSceneError("motion_fps must not exceed fps")
    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        raise SemanticSceneError("assets must be a non-empty list")
    asset_ids: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise SemanticSceneError("asset must be an object")
        asset_id = str(asset.get("asset_id") or "")
        if not asset_id or asset_id in asset_ids:
            raise SemanticSceneError("asset_id must be non-empty and unique")
        asset_ids.add(asset_id)
        digest = str(asset.get("sha256") or "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise SemanticSceneError(f"asset {asset_id} has invalid sha256")
    beats = payload.get("beats")
    if not isinstance(beats, list) or not beats:
        raise SemanticSceneError("beats must be a non-empty list")
    beat_ids: set[str] = set()
    action_ids: set[str] = set()
    for beat in beats:
        beat_id = str(beat.get("beat_id") or "")
        if not beat_id or beat_id in beat_ids:
            raise SemanticSceneError("beat_id must be non-empty and unique")
        beat_ids.add(beat_id)
        if not str(beat.get("anchor") or "").strip():
            raise SemanticSceneError(f"beat {beat_id} needs narration anchor")
        actions = beat.get("actions")
        if not isinstance(actions, list) or not actions:
            raise SemanticSceneError(f"beat {beat_id} needs actions")
        for action in actions:
            action_id = str(action.get("action_id") or "")
            if not action_id or action_id in action_ids:
                raise SemanticSceneError("action_id must be non-empty and unique")
            action_ids.add(action_id)
            if action.get("type") not in ALLOWED_ACTIONS:
                raise SemanticSceneError(f"unsupported action: {action.get('type')}")
            duration = action.get("duration_ms")
            if not isinstance(duration, int) or duration <= 0:
                raise SemanticSceneError(f"action {action_id} needs positive duration_ms")
            for reference in (action.get("subject"), *(action.get("variants") or [])):
                if reference and reference not in asset_ids:
                    raise SemanticSceneError(f"action {action_id} references unknown asset {reference}")
    return SemanticSceneSpec(payload=payload, sha256=_canonical_sha256(payload))


def build_canonical_scene(data: Any) -> CanonicalScene:
    if not isinstance(data, dict):
        raise SemanticSceneError("canonical scene must be an object")
    payload = json.loads(json.dumps(data, ensure_ascii=False))
    if payload.get("schema_version") != "vox.scene/2.0":
        raise SemanticSceneError("schema_version must be vox.scene/2.0")
    for key in ("project_id", "scene_id", "grammar", "narration"):
        if not str(payload.get(key) or "").strip():
            raise SemanticSceneError(f"{key} is required")
    duration_ms = payload.get("duration_ms")
    fps = payload.get("fps")
    motion_fps = payload.get("motion_fps")
    if not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in (duration_ms, fps, motion_fps)):
        raise SemanticSceneError("duration_ms, fps, and motion_fps must be positive integers")
    if motion_fps > fps:
        raise SemanticSceneError("motion_fps must not exceed fps")
    raw_entities = payload.get("entities")
    raw_events = payload.get("events")
    if not isinstance(raw_entities, list) or not raw_entities:
        raise SemanticSceneError("entities must be a non-empty list")
    if not isinstance(raw_events, list) or not raw_events:
        raise SemanticSceneError("events must be a non-empty list")
    entities: list[CanonicalEntity] = []
    entity_ids: set[str] = set()
    for raw in raw_entities:
        entity_id = str(raw.get("entity_id") or "").strip()
        asset = str(raw.get("asset") or "").strip()
        if not entity_id or entity_id in entity_ids or not asset:
            raise SemanticSceneError("entity needs unique entity_id and asset")
        entity_ids.add(entity_id)
        entities.append(
            CanonicalEntity(
                entity_id=entity_id,
                kind=str(raw.get("kind") or "object"),
                role=str(raw.get("role") or "object"),
                asset=asset,
                sha256=str(raw.get("sha256") or ""),
                x=int(raw.get("x", 0)),
                y=int(raw.get("y", 0)),
                z=int(raw.get("z", 10)),
                metadata=dict(raw.get("metadata") or {}),
            )
        )
    if not any(entity.role == "background" for entity in entities):
        raise SemanticSceneError("canonical scene requires a background entity")
    events: list[CanonicalEvent] = []
    previous_start = -1
    event_ids: set[str] = set()
    for raw in raw_events:
        event_id = str(raw.get("event_id") or "").strip()
        action = str(raw.get("action") or raw.get("type") or "").strip()
        target = str(raw.get("target") or raw.get("subject") or "").strip()
        source = str(raw.get("source") or "").strip()
        start_ms = raw.get("start_ms")
        event_duration = raw.get("duration_ms")
        if not event_id or event_id in event_ids or action not in ALLOWED_ACTIONS:
            raise SemanticSceneError("event needs unique event_id and supported action")
        if target and target not in entity_ids or source and source not in entity_ids:
            raise SemanticSceneError(f"event {event_id} references unknown entity")
        if not isinstance(start_ms, int) or start_ms < previous_start:
            raise SemanticSceneError("events must be ordered by start_ms")
        if not isinstance(event_duration, int) or event_duration <= 0 or start_ms + event_duration > duration_ms:
            raise SemanticSceneError(f"event {event_id} has invalid timing")
        event_ids.add(event_id)
        previous_start = start_ms
        reserved = {"event_id", "anchor", "start_ms", "duration_ms", "action", "type", "target", "subject", "source"}
        events.append(
            CanonicalEvent(
                event_id=event_id,
                anchor=str(raw.get("anchor") or payload["narration"]),
                start_ms=start_ms,
                duration_ms=event_duration,
                action=action,
                target=target,
                source=source,
                payload={key: value for key, value in raw.items() if key not in reserved},
            )
        )
    canvas = payload.get("canvas") or {}
    return CanonicalScene(
        schema_version="vox.scene/2.0",
        project_id=str(payload["project_id"]),
        scene_id=str(payload["scene_id"]),
        revision=int(payload.get("revision") or 1),
        grammar=str(payload["grammar"]),
        narration=str(payload["narration"]),
        duration_ms=duration_ms,
        fps=fps,
        motion_fps=motion_fps,
        canvas_width=int(canvas.get("width", 1920)),
        canvas_height=int(canvas.get("height", 1080)),
        entities=tuple(entities),
        events=tuple(events),
        sha256=_canonical_sha256(payload),
    )


__all__ = [
    "ALLOWED_ACTIONS",
    "ALLOWED_GRAMMARS",
    "CanonicalEntity",
    "CanonicalEvent",
    "CanonicalScene",
    "SemanticSceneError",
    "SemanticSceneSpec",
    "build_canonical_scene",
    "build_semantic_scene_spec",
]
