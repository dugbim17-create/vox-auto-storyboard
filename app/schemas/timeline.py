"""Canonical voice-first scene timeline contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_LEAD_IN_MS = 120
DEFAULT_LEAD_OUT_MS = 220


class TimelineError(ValueError):
    """Raised when a scene or project timeline is invalid."""


@dataclass(frozen=True)
class SceneTimeline:
    """Timing for one scene, using the measured voice as its source of truth."""

    scene_id: str
    voice_duration_ms: int
    fps: int
    lead_in_ms: int = DEFAULT_LEAD_IN_MS
    lead_out_ms: int = DEFAULT_LEAD_OUT_MS
    start_ms: int = 0

    @classmethod
    def from_voice(
        cls,
        scene_id: str,
        voice_duration_ms: int,
        fps: int,
        *,
        lead_in_ms: int = DEFAULT_LEAD_IN_MS,
        lead_out_ms: int = DEFAULT_LEAD_OUT_MS,
        start_ms: int = 0,
    ) -> SceneTimeline:
        if not isinstance(scene_id, str) or not scene_id.strip():
            raise TimelineError("scene_id must not be empty")
        if isinstance(voice_duration_ms, bool) or voice_duration_ms <= 0:
            raise TimelineError("voice_duration_ms must be positive")
        if isinstance(fps, bool) or fps <= 0:
            raise TimelineError("fps must be positive")
        if isinstance(lead_in_ms, bool) or lead_in_ms < 0:
            raise TimelineError("lead_in_ms must be non-negative")
        if isinstance(lead_out_ms, bool) or lead_out_ms < 0:
            raise TimelineError("lead_out_ms must be non-negative")
        if isinstance(start_ms, bool) or start_ms < 0:
            raise TimelineError("start_ms must be non-negative")
        return cls(
            scene_id=scene_id.strip(),
            voice_duration_ms=int(voice_duration_ms),
            fps=int(fps),
            lead_in_ms=int(lead_in_ms),
            lead_out_ms=int(lead_out_ms),
            start_ms=int(start_ms),
        )

    @property
    def visual_duration_ms(self) -> int:
        return self.voice_duration_ms + self.lead_in_ms + self.lead_out_ms

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.visual_duration_ms

    @property
    def voice_start_ms(self) -> int:
        return self.start_ms + self.lead_in_ms

    @property
    def voice_end_ms(self) -> int:
        return self.voice_start_ms + self.voice_duration_ms

    @property
    def frame_count(self) -> int:
        return int(round(self.visual_duration_ms / 1000.0 * self.fps))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "voice_duration_ms": self.voice_duration_ms,
            "fps": self.fps,
            "lead_in_ms": self.lead_in_ms,
            "lead_out_ms": self.lead_out_ms,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "voice_start_ms": self.voice_start_ms,
            "voice_end_ms": self.voice_end_ms,
            "visual_duration_ms": self.visual_duration_ms,
            "frame_count": self.frame_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneTimeline:
        return cls.from_voice(
            scene_id=data["scene_id"],
            voice_duration_ms=int(data["voice_duration_ms"]),
            fps=int(data["fps"]),
            lead_in_ms=int(data.get("lead_in_ms", DEFAULT_LEAD_IN_MS)),
            lead_out_ms=int(data.get("lead_out_ms", DEFAULT_LEAD_OUT_MS)),
            start_ms=int(data.get("start_ms", 0)),
        )


@dataclass(frozen=True)
class ProjectTimeline:
    """Ordered scene timelines with contiguous global boundaries."""

    scenes: tuple[SceneTimeline, ...]
    fps: int

    @classmethod
    def from_voice_durations(
        cls,
        scene_durations: list[tuple[str, int]] | tuple[tuple[str, int], ...],
        fps: int,
        *,
        lead_in_ms: int = DEFAULT_LEAD_IN_MS,
        lead_out_ms: int = DEFAULT_LEAD_OUT_MS,
    ) -> ProjectTimeline:
        if not scene_durations:
            raise TimelineError("project must contain at least one scene")
        seen: set[str] = set()
        scenes: list[SceneTimeline] = []
        cursor = 0
        for scene_id, duration_ms in scene_durations:
            if scene_id in seen:
                raise TimelineError(f"duplicate scene_id: {scene_id}")
            seen.add(scene_id)
            scene = SceneTimeline.from_voice(
                scene_id,
                duration_ms,
                fps,
                lead_in_ms=lead_in_ms,
                lead_out_ms=lead_out_ms,
                start_ms=cursor,
            )
            scenes.append(scene)
            cursor = scene.end_ms
        return cls(scenes=tuple(scenes), fps=int(fps))

    @property
    def duration_ms(self) -> int:
        return self.scenes[-1].end_ms

    @property
    def frame_count(self) -> int:
        return int(round(self.duration_ms / 1000.0 * self.fps))

    def scene(self, scene_id: str) -> SceneTimeline:
        for scene in self.scenes:
            if scene.scene_id == scene_id:
                return scene
        raise TimelineError(f"scene not found in timeline: {scene_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fps": self.fps,
            "duration_ms": self.duration_ms,
            "frame_count": self.frame_count,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectTimeline:
        scenes = tuple(SceneTimeline.from_dict(item) for item in data["scenes"])
        if not scenes:
            raise TimelineError("project must contain at least one scene")
        timeline = cls(scenes=scenes, fps=int(data["fps"]))
        expected_start = 0
        for scene in timeline.scenes:
            if scene.start_ms != expected_start:
                raise TimelineError("scene boundaries are not contiguous")
            expected_start = scene.end_ms
        return timeline
