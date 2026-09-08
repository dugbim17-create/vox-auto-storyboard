from __future__ import annotations

from app.schemas.editorial_timeline import (
    BeatSpec,
    SceneSpec,
    VisualEventSpec,
    VoiceTimeline,
    WordTiming,
    build_scene_editorial_timeline,
)
from app.services.editorial_motion import apply_editorial_events
from app.services.motion_templates import build_template


def test_resolved_narration_event_replaces_placeholder_with_timed_content() -> None:
    scene = SceneSpec(
        scene_id="scene_001",
        narration="The number jumps to 42 percent today.",
        beats=(BeatSpec("beat_reveal", "42 percent", "reveal"),),
        visual_events=(
            VisualEventSpec(
                event_id="event_counter",
                beat_id="beat_reveal",
                object_type="counter",
                layer_role="evidence",
                narration_anchor="42 percent",
                duration_ms=900,
                display_text="42%",
            ),
        ),
    )
    voice = VoiceTimeline.build(
        scene_id="scene_001",
        duration_ms=2_000,
        fps=30,
        words=(
            WordTiming("The", 0, 160),
            WordTiming("number", 180, 410),
            WordTiming("jumps", 430, 650),
            WordTiming("to", 680, 780),
            WordTiming("42", 960, 1_080),
            WordTiming("percent", 1_100, 1_430),
            WordTiming("today", 1_500, 1_820),
        ),
    )
    timeline = build_scene_editorial_timeline(scene, voice)
    template = build_template(
        "01_subject_slide_headline_pop",
        "scene_001",
        2_000,
        seed=3,
        canvas_size=(360, 640),
    )

    plan = apply_editorial_events(template, timeline)

    assert all(item["text"] != "HEADLINE" for item in plan["text_animations"])
    counter = next(item for item in plan["text_animations"] if item["event_id"] == "event_counter")
    assert counter["text"] == "42%"
    assert counter["start_ms"] == 960
    assert counter["end_ms"] == 1_860
    assert counter["narration_anchor"] == "42 percent"
