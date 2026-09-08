"""Narration-synchronised accumulated visual-stage contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALLOWED_EVENT_ENTERS = (
    "none",
    "popup",
    "fade",
    "swipe_left",
    "swipe_right",
    "swipe_up",
    "page_flip",
    "stamp",
    "counter",
    "line_draw",
    "shake",
    "glow",
)
ALLOWED_EVENT_EXITS = ("none", "fade", "swipe_left", "swipe_right", "page_flip")


class VisualEventError(ValueError):
    """Raised when an accumulated visual-stage event is invalid."""


@dataclass(frozen=True)
class VisualEvent:
    """One information reveal inside a persistent visual stage."""

    event_id: str
    trigger: str
    start_ms: int
    duration_ms: int
    asset: str
    placement: str
    enter: str = "popup"
    exit: str = "none"
    persistent: bool = True
    z: int = 10
    sound_cue: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger": self.trigger,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "asset": self.asset,
            "placement": self.placement,
            "enter": self.enter,
            "exit": self.exit,
            "persistent": self.persistent,
            "z": self.z,
            "sound_cue": self.sound_cue,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class VisualStage:
    """A single composition whose information accumulates as narration advances."""

    stage_id: str
    narration: str
    duration_ms: int
    background: str
    events: tuple[VisualEvent, ...]
    canvas_width: int = 1920
    canvas_height: int = 1080
    style: str = "editorial_collage"

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def meaningful_event_count(self) -> int:
        return sum(1 for event in self.events if event.asset or event.trigger)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "narration": self.narration,
            "duration_ms": self.duration_ms,
            "background": self.background,
            "canvas": {"width": self.canvas_width, "height": self.canvas_height},
            "style": self.style,
            "events": [event.to_dict() for event in self.events],
        }


def build_visual_stage(data: dict[str, Any]) -> VisualStage:
    if not isinstance(data, dict):
        raise VisualEventError("visual stage must be an object")
    stage_id = str(data.get("stage_id") or "").strip()
    narration = str(data.get("narration") or "").strip()
    background = str(data.get("background") or "").strip()
    duration_ms = data.get("duration_ms")
    if not stage_id or not narration or not background:
        raise VisualEventError("stage_id, narration, and background are required")
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms <= 0:
        raise VisualEventError("duration_ms must be a positive integer")
    canvas = data.get("canvas") or {}
    events_raw = data.get("events")
    if not isinstance(events_raw, list) or not events_raw:
        raise VisualEventError("events must be a non-empty list")
    events: list[VisualEvent] = []
    ids: set[str] = set()
    for index, raw in enumerate(events_raw):
        if not isinstance(raw, dict):
            raise VisualEventError(f"events[{index}] must be an object")
        event_id = str(raw.get("event_id") or "").strip()
        trigger = str(raw.get("trigger") or "").strip()
        asset = str(raw.get("asset") or "").strip()
        placement = str(raw.get("placement") or "").strip()
        start_ms = raw.get("start_ms")
        event_duration = raw.get("duration_ms")
        if not event_id or event_id in ids:
            raise VisualEventError(f"events[{index}] has duplicate or empty event_id")
        ids.add(event_id)
        if not trigger or not asset or not placement:
            raise VisualEventError(f"events[{index}] needs trigger, asset, and placement")
        if not isinstance(start_ms, int) or start_ms < 0:
            raise VisualEventError(f"events[{index}].start_ms must be non-negative integer")
        if not isinstance(event_duration, int) or event_duration <= 0:
            raise VisualEventError(f"events[{index}].duration_ms must be positive integer")
        if start_ms + event_duration > duration_ms:
            raise VisualEventError(f"events[{index}] exceeds stage duration")
        enter = str(raw.get("enter") or "popup")
        exit_name = str(raw.get("exit") or "none")
        if enter not in ALLOWED_EVENT_ENTERS:
            raise VisualEventError(f"events[{index}] invalid enter effect: {enter}")
        if exit_name not in ALLOWED_EVENT_EXITS:
            raise VisualEventError(f"events[{index}] invalid exit effect: {exit_name}")
        z = raw.get("z", 10)
        if not isinstance(z, int) or z < 0:
            raise VisualEventError(f"events[{index}].z must be a non-negative integer")
        events.append(
            VisualEvent(
                event_id=event_id,
                trigger=trigger,
                start_ms=start_ms,
                duration_ms=event_duration,
                asset=asset,
                placement=placement,
                enter=enter,
                exit=exit_name,
                persistent=bool(raw.get("persistent", True)),
                z=z,
                sound_cue=str(raw.get("sound_cue") or ""),
                metadata=dict(raw.get("metadata") or {}),
            )
        )
    if any(event.start_ms < previous.start_ms for previous, event in zip(events, events[1:], strict=False)):
        raise VisualEventError("events must be ordered by start_ms")
    return VisualStage(
        stage_id=stage_id,
        narration=narration,
        duration_ms=duration_ms,
        background=background,
        events=tuple(events),
        canvas_width=int(canvas.get("width", 1920)),
        canvas_height=int(canvas.get("height", 1080)),
        style=str(data.get("style") or "editorial_collage"),
    )
