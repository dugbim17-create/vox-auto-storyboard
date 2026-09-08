from __future__ import annotations

from app.schemas.editorial_timeline import (
    BeatSpec,
    SceneSpec,
    VisualEventSpec,
    VoiceTimeline,
    WordTiming,
    build_scene_editorial_timeline,
)


def test_visual_event_is_anchored_to_the_spoken_phrase_frame() -> None:
    scene = SceneSpec(
        scene_id="scene_001",
        narration="The number jumps to 42 percent today.",
        beats=(
            BeatSpec(
                beat_id="beat_reveal",
                narration="The number jumps to 42 percent today.",
                purpose="reveal",
            ),
        ),
        visual_events=(
            VisualEventSpec(
                event_id="event_counter",
                beat_id="beat_reveal",
                object_type="counter",
                layer_role="evidence",
                narration_anchor="42 percent",
                duration_ms=900,
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

    event = timeline.visual_events[0]
    assert event.anchor.start_ms == 960
    assert event.anchor.end_ms == 1_430
    assert event.start_frame == 29
    assert event.end_frame == 56
    assert event.object_type == "counter"
    assert event.layer_role == "evidence"
