"""Micro-beat planning engine for fast-paced, high-retention Vox documentary videos."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

TARGET_BEAT_DURATION_MS = 2400
MIN_BEAT_DURATION_MS = 1800
MAX_BEAT_DURATION_MS = 3200


@dataclass(frozen=True)
class MicroBeat:
    """A single 2.0s - 2.8s visual beat within an editorial scene."""

    index: int
    start_ms: int
    duration_ms: int
    visual_action: str  # photo_drop, highlighter_sweep, arrow_tracer, radar_sweep, stamp_impact, counter_roll, paper_tear
    primary_element: str  # photo_plate, document_card, tactical_map, counter_odometer, stamp
    sound_cue: str  # whoosh, paper_slide, marker_sweep, pop, camera_click, stamp_thud, typewriter
    headline: str = ""
    highlight_text: str = ""


@dataclass(frozen=True)
class SceneBeatPlan:
    """The sequence of micro-beats composing a scene."""

    scene_id: str
    total_duration_ms: int
    beat_count: int
    beats: list[MicroBeat] = field(default_factory=list)


class MicroBeatPlanner:
    """Decomposes scene narrations and durations into high-retention micro-beats."""

    @staticmethod
    def plan_scene_beats(
        scene_id: str,
        duration_ms: int,
        *,
        template_name: str = "editorial_collage",
        headline: str = "",
        key_phrase: str = "",
    ) -> SceneBeatPlan:
        """Partition a scene's duration into 2 to 4 timed micro-beats."""
        dur = max(2000, duration_ms)
        beat_count = max(2, min(4, int(math.ceil(dur / float(TARGET_BEAT_DURATION_MS)))))
        beat_len = dur // beat_count

        beats: list[MicroBeat] = []
        current_t = 0

        # Action sequence based on template flavor
        if "map" in template_name or "radar" in template_name:
            actions = [
                ("photo_drop", "tactical_map", "whoosh"),
                ("radar_sweep", "radar_beam", "pop"),
                ("arrow_tracer", "tactical_arrow", "whoosh"),
                ("stamp_impact", "stamp", "camera_click"),
            ]
        elif "stat" in template_name or "number" in template_name or "finance" in template_name:
            actions = [
                ("photo_drop", "finance_terminal", "whoosh"),
                ("counter_roll", "counter_odometer", "typewriter"),
                ("graph_draw", "growth_curve", "pop"),
                ("stamp_impact", "stamp", "camera_click"),
            ]
        elif "document" in template_name or "highlight" in template_name:
            actions = [
                ("photo_drop", "photo_plate", "paper_slide"),
                ("highlighter_sweep", "document_card", "marker_sweep"),
                ("circle_draw", "evidence_circle", "pop"),
                ("stamp_impact", "stamp", "camera_click"),
            ]
        else:  # Standard editorial collage
            actions = [
                ("photo_drop", "photo_plate", "whoosh"),
                ("card_slide", "document_card", "paper_slide"),
                ("highlighter_sweep", "document_card", "marker_sweep"),
                ("stamp_impact", "stamp", "camera_click"),
            ]

        for i in range(beat_count):
            this_dur = (dur - current_t) if i == beat_count - 1 else beat_len
            action_info = actions[min(i, len(actions) - 1)]

            beats.append(
                MicroBeat(
                    index=i + 1,
                    start_ms=current_t,
                    duration_ms=this_dur,
                    visual_action=action_info[0],
                    primary_element=action_info[1],
                    sound_cue=action_info[2],
                    headline=headline if i == 0 else "",
                    highlight_text=key_phrase if i == 1 else "",
                )
            )
            current_t += this_dur

        return SceneBeatPlan(
            scene_id=scene_id,
            total_duration_ms=dur,
            beat_count=len(beats),
            beats=beats,
        )
