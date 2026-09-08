"""Canonical narration-anchored contracts for editorial scene timing.

The measured voice timeline is the only clock. Storyboard beats and visual
objects reference spoken phrases; this module resolves those semantic anchors
into deterministic millisecond and frame positions before motion planning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class EditorialTimelineError(ValueError):
    """Raised when editorial scene or voice timing cannot be resolved safely."""


@dataclass(frozen=True)
class WordTiming:
    text: str
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise EditorialTimelineError("word text must not be empty")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise EditorialTimelineError("word timing must have a positive duration")


@dataclass(frozen=True)
class NarrationAnchor:
    text: str
    start_ms: int
    end_ms: int
    start_word_index: int
    end_word_index: int


@dataclass(frozen=True)
class VoiceTimeline:
    scene_id: str
    duration_ms: int
    fps: int
    words: tuple[WordTiming, ...]

    @classmethod
    def build(
        cls,
        *,
        scene_id: str,
        duration_ms: int,
        fps: int,
        words: tuple[WordTiming, ...],
    ) -> VoiceTimeline:
        if not scene_id.strip():
            raise EditorialTimelineError("scene_id must not be empty")
        if duration_ms <= 0 or fps <= 0:
            raise EditorialTimelineError("duration_ms and fps must be positive")
        if not words:
            raise EditorialTimelineError("measured word timings are required")
        previous_end = 0
        for word in words:
            if word.start_ms < previous_end:
                raise EditorialTimelineError("word timings must not overlap or go backwards")
            if word.end_ms > duration_ms:
                raise EditorialTimelineError("word timing exceeds measured voice duration")
            previous_end = word.end_ms
        return cls(scene_id.strip(), int(duration_ms), int(fps), tuple(words))

    def resolve_anchor(self, phrase: str) -> NarrationAnchor:
        wanted = _tokens(phrase)
        if not wanted:
            raise EditorialTimelineError("narration anchor must contain spoken text")
        spoken = [_token(word.text) for word in self.words]
        width = len(wanted)
        for index in range(len(spoken) - width + 1):
            if spoken[index : index + width] == wanted:
                first = self.words[index]
                last = self.words[index + width - 1]
                return NarrationAnchor(
                    text=phrase,
                    start_ms=first.start_ms,
                    end_ms=last.end_ms,
                    start_word_index=index,
                    end_word_index=index + width - 1,
                )
        raise EditorialTimelineError(
            f"narration anchor {phrase!r} was not found in measured voice words"
        )

    def frame_at(self, time_ms: int) -> int:
        return int(round(time_ms / 1000.0 * self.fps))


@dataclass(frozen=True)
class BeatSpec:
    beat_id: str
    narration: str
    purpose: str

    def __post_init__(self) -> None:
        if not self.beat_id.strip() or not self.narration.strip() or not self.purpose.strip():
            raise EditorialTimelineError("beat id, narration, and purpose are required")


@dataclass(frozen=True)
class VisualEventSpec:
    event_id: str
    beat_id: str
    object_type: str
    layer_role: str
    narration_anchor: str
    duration_ms: int
    display_text: str = ""

    def __post_init__(self) -> None:
        required = (
            self.event_id,
            self.beat_id,
            self.object_type,
            self.layer_role,
            self.narration_anchor,
        )
        if any(not value.strip() for value in required):
            raise EditorialTimelineError("visual event fields must not be empty")
        if self.duration_ms <= 0:
            raise EditorialTimelineError("visual event duration_ms must be positive")


@dataclass(frozen=True)
class SceneSpec:
    scene_id: str
    narration: str
    beats: tuple[BeatSpec, ...]
    visual_events: tuple[VisualEventSpec, ...]

    def __post_init__(self) -> None:
        if not self.scene_id.strip() or not self.narration.strip():
            raise EditorialTimelineError("scene id and narration are required")
        if not self.beats:
            raise EditorialTimelineError("scene must contain at least one semantic beat")
        beat_ids = [beat.beat_id for beat in self.beats]
        if len(beat_ids) != len(set(beat_ids)):
            raise EditorialTimelineError("beat ids must be unique within a scene")
        known = set(beat_ids)
        for event in self.visual_events:
            if event.beat_id not in known:
                raise EditorialTimelineError(
                    f"visual event {event.event_id!r} references unknown beat {event.beat_id!r}"
                )


@dataclass(frozen=True)
class ResolvedVisualEvent:
    event_id: str
    beat_id: str
    object_type: str
    layer_role: str
    anchor: NarrationAnchor
    display_text: str
    start_ms: int
    end_ms: int
    start_frame: int
    end_frame: int


@dataclass(frozen=True)
class SceneEditorialTimeline:
    scene_id: str
    fps: int
    duration_ms: int
    visual_events: tuple[ResolvedVisualEvent, ...]


def build_scene_editorial_timeline(
    scene: SceneSpec,
    voice: VoiceTimeline,
) -> SceneEditorialTimeline:
    if scene.scene_id != voice.scene_id:
        raise EditorialTimelineError("scene and voice timeline ids do not match")
    resolved: list[ResolvedVisualEvent] = []
    for event in scene.visual_events:
        anchor = voice.resolve_anchor(event.narration_anchor)
        end_ms = anchor.start_ms + event.duration_ms
        if end_ms > voice.duration_ms:
            raise EditorialTimelineError(
                f"visual event {event.event_id!r} exceeds measured voice duration"
            )
        resolved.append(
            ResolvedVisualEvent(
                event_id=event.event_id,
                beat_id=event.beat_id,
                object_type=event.object_type,
                layer_role=event.layer_role,
                anchor=anchor,
                display_text=event.display_text or anchor.text,
                start_ms=anchor.start_ms,
                end_ms=end_ms,
                start_frame=voice.frame_at(anchor.start_ms),
                end_frame=voice.frame_at(end_ms),
            )
        )
    return SceneEditorialTimeline(
        scene_id=scene.scene_id,
        fps=voice.fps,
        duration_ms=voice.duration_ms,
        visual_events=tuple(resolved),
    )


def _token(value: str) -> str:
    matches = re.findall(r"\w+", value.casefold(), flags=re.UNICODE)
    return matches[0] if matches else ""


def _tokens(value: str) -> list[str]:
    return re.findall(r"\w+", value.casefold(), flags=re.UNICODE)
