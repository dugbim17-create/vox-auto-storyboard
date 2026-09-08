"""Tests for the canonical voice-first timeline contract."""

from __future__ import annotations

import pytest

from app.schemas.timeline import ProjectTimeline, SceneTimeline, TimelineError


def test_scene_timeline_derives_visual_duration_and_frame_count() -> None:
    timeline = SceneTimeline.from_voice(
        "scene_001",
        voice_duration_ms=3000,
        fps=30,
    )

    assert timeline.voice_duration_ms == 3000
    assert timeline.lead_in_ms == 120
    assert timeline.lead_out_ms == 220
    assert timeline.visual_duration_ms == 3340
    assert timeline.frame_count == 100
    assert timeline.start_ms == 0
    assert timeline.end_ms == 3340


def test_project_timeline_assigns_contiguous_global_scene_boundaries() -> None:
    project = ProjectTimeline.from_voice_durations(
        [
            ("scene_001", 3000),
            ("scene_002", 2000),
            ("scene_003", 4000),
        ],
        fps=30,
    )

    assert [(s.scene_id, s.start_ms, s.end_ms) for s in project.scenes] == [
        ("scene_001", 0, 3340),
        ("scene_002", 3340, 5680),
        ("scene_003", 5680, 10020),
    ]
    assert project.duration_ms == 10020
    assert project.frame_count == 301


def test_timeline_rejects_invalid_inputs() -> None:
    with pytest.raises(TimelineError, match="voice_duration_ms"):
        SceneTimeline.from_voice("scene_001", 0, fps=30)
    with pytest.raises(TimelineError, match="fps"):
        SceneTimeline.from_voice("scene_001", 1000, fps=0)
    with pytest.raises(TimelineError, match="lead_in_ms"):
        SceneTimeline.from_voice("scene_001", 1000, fps=30, lead_in_ms=-1)
    with pytest.raises(TimelineError, match="scene_id"):
        SceneTimeline.from_voice("", 1000, fps=30)


def test_project_timeline_rejects_duplicate_or_empty_scene_ids() -> None:
    with pytest.raises(TimelineError, match="at least one"):
        ProjectTimeline.from_voice_durations([], fps=30)
    with pytest.raises(TimelineError, match="duplicate"):
        ProjectTimeline.from_voice_durations(
            [("scene_001", 1000), ("scene_001", 1000)], fps=30
        )


def test_project_timeline_round_trip_dict() -> None:
    project = ProjectTimeline.from_voice_durations(
        [("scene_001", 1000)], fps=24
    )

    restored = ProjectTimeline.from_dict(project.to_dict())

    assert restored == project
    assert restored.to_dict()["duration_ms"] == 1340
    assert restored.to_dict()["scenes"][0]["frame_count"] == 32


def test_scene_timeline_keeps_custom_lead_values() -> None:
    timeline = SceneTimeline.from_voice(
        "scene_001",
        voice_duration_ms=1000,
        fps=25,
        lead_in_ms=80,
        lead_out_ms=120,
    )

    assert timeline.visual_duration_ms == 1200
    assert timeline.frame_count == 30
    assert timeline.end_ms == 1200
