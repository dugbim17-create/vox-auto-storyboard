"""Semantic object-first stage contract for explanatory VOX animation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ACTIONS = frozenset({"reveal", "move", "connect", "disconnect", "merge", "transform", "highlight", "focus"})
TEXT_KINDS = frozenset({"label", "text", "caption"})
RELATIONSHIP_ACTIONS = frozenset({"connect", "merge"})


class SemanticStageError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticEntity:
    entity_id: str
    kind: str
    asset: str
    x: int
    y: int
    z: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "kind": self.kind,
            "asset": self.asset,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SemanticMutation:
    event_id: str
    start_ms: int
    duration_ms: int
    action: str
    target: str
    source: str = ""
    to_x: int | None = None
    to_y: int | None = None
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "action": self.action,
            "target": self.target,
            "source": self.source,
            "to_x": self.to_x,
            "to_y": self.to_y,
            "label": self.label,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SemanticVisualStage:
    stage_id: str
    narration: str
    duration_ms: int
    background: str
    entities: tuple[SemanticEntity, ...]
    events: tuple[SemanticMutation, ...]
    canvas_width: int = 1920
    canvas_height: int = 1080

    @property
    def visual_action_count(self) -> int:
        return len(self.events)

    @property
    def text_only_event_count(self) -> int:
        kinds = {entity.entity_id: entity.kind for entity in self.entities}
        return sum(1 for event in self.events if kinds.get(event.target) in TEXT_KINDS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "narration": self.narration,
            "duration_ms": self.duration_ms,
            "background": self.background,
            "canvas": {"width": self.canvas_width, "height": self.canvas_height},
            "entities": [entity.to_dict() for entity in self.entities],
            "events": [event.to_dict() for event in self.events],
        }

    def to_canonical_scene(self, *, project_id: str, revision: int = 1):
        from app.schemas.semantic_scene import build_canonical_scene

        entities = [
            {
                **entity.to_dict(),
                "role": "object",
                "sha256": "",
            }
            for entity in self.entities
        ]
        entities.insert(
            0,
            {
                "entity_id": "background",
                "kind": "background",
                "role": "background",
                "asset": self.background,
                "sha256": "",
                "x": 0,
                "y": 0,
                "z": 0,
            },
        )
        events = [
            {
                **event.to_dict(),
                "anchor": self.narration,
            }
            for event in self.events
        ]
        return build_canonical_scene(
            {
                "schema_version": "vox.scene/2.0",
                "project_id": project_id,
                "scene_id": self.stage_id,
                "revision": revision,
                "grammar": "explanatory_hold",
                "narration": self.narration,
                "duration_ms": self.duration_ms,
                "fps": 30,
                "motion_fps": 12,
                "canvas": {"width": self.canvas_width, "height": self.canvas_height},
                "entities": entities,
                "events": events,
            }
        )


def build_semantic_stage(data: dict[str, Any]) -> SemanticVisualStage:
    if not isinstance(data, dict):
        raise SemanticStageError("semantic stage must be an object")
    stage_id = str(data.get("stage_id") or "").strip()
    narration = str(data.get("narration") or "").strip()
    background = str(data.get("background") or "").strip()
    duration_ms = data.get("duration_ms")
    if not stage_id or not narration or not background:
        raise SemanticStageError("stage_id, narration, and background are required")
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms <= 0:
        raise SemanticStageError("duration_ms must be a positive integer")
    raw_entities = data.get("entities")
    raw_events = data.get("events")
    if not isinstance(raw_entities, list) or not raw_entities:
        raise SemanticStageError("entities must be a non-empty list")
    if not isinstance(raw_events, list) or not raw_events:
        raise SemanticStageError("events must be a non-empty list")
    entities: list[SemanticEntity] = []
    entity_ids: set[str] = set()
    for index, raw in enumerate(raw_entities):
        if not isinstance(raw, dict):
            raise SemanticStageError(f"entities[{index}] must be an object")
        entity_id = str(raw.get("entity_id") or "").strip()
        kind = str(raw.get("kind") or "").strip()
        asset = str(raw.get("asset") or "").strip()
        if not entity_id or entity_id in entity_ids or not kind or not asset:
            raise SemanticStageError(f"entities[{index}] needs unique id, kind, and asset")
        entity_ids.add(entity_id)
        entities.append(
            SemanticEntity(
                entity_id=entity_id,
                kind=kind,
                asset=asset,
                x=int(raw.get("x", 0)),
                y=int(raw.get("y", 0)),
                z=int(raw.get("z", 10)),
                metadata=dict(raw.get("metadata") or {}),
            )
        )
    if not any(entity.kind not in TEXT_KINDS for entity in entities):
        raise SemanticStageError("stage requires a non-text semantic entity")
    events: list[SemanticMutation] = []
    previous_start = -1
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            raise SemanticStageError(f"events[{index}] must be an object")
        event_id = str(raw.get("event_id") or "").strip()
        action = str(raw.get("action") or "").strip()
        target = str(raw.get("target") or "").strip()
        source = str(raw.get("source") or "").strip()
        start_ms = raw.get("start_ms")
        event_duration = raw.get("duration_ms")
        if not event_id or action not in ACTIONS:
            raise SemanticStageError(f"events[{index}] invalid event_id/action")
        if target not in entity_ids or (source and source not in entity_ids):
            raise SemanticStageError(f"events[{index}] references unknown entity")
        if not isinstance(start_ms, int) or start_ms < previous_start:
            raise SemanticStageError("events must be ordered by start_ms")
        if not isinstance(event_duration, int) or event_duration <= 0 or start_ms + event_duration > duration_ms:
            raise SemanticStageError(f"events[{index}] invalid timing")
        previous_start = start_ms
        events.append(
            SemanticMutation(
                event_id=event_id,
                start_ms=start_ms,
                duration_ms=event_duration,
                action=action,
                target=target,
                source=source,
                to_x=int(raw["to_x"]) if raw.get("to_x") is not None else None,
                to_y=int(raw["to_y"]) if raw.get("to_y") is not None else None,
                label=str(raw.get("label") or ""),
                metadata=dict(raw.get("metadata") or {}),
            )
        )
    if data.get("requires_relationship_visualization") and not any(event.action in RELATIONSHIP_ACTIONS for event in events):
        raise SemanticStageError("stage requires a relationship mutation")
    canvas = data.get("canvas") or {}
    return SemanticVisualStage(
        stage_id=stage_id,
        narration=narration,
        duration_ms=duration_ms,
        background=background,
        entities=tuple(entities),
        events=tuple(events),
        canvas_width=int(canvas.get("width", 1920)),
        canvas_height=int(canvas.get("height", 1080)),
    )


__all__ = ["SemanticEntity", "SemanticMutation", "SemanticStageError", "SemanticVisualStage", "build_semantic_stage"]
