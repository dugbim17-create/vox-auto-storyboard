"""Unit tests for AutoSFXService."""

from __future__ import annotations

from pathlib import Path

from app.services.sfx_service import AutoSFXService, SFXEvent


def test_derive_scene_sfx_events_for_templates() -> None:
    events = AutoSFXService.derive_scene_sfx_events(
        "07_document_highlight",
        duration_ms=4000,
        visual_events=[{"start_ms": 1500, "enter": "popup"}],
        transition_out="paper_tear",
    )
    types = [e.sfx_type for e in events]
    assert "paper_slide" in types
    assert "marker_sweep" in types
    assert "pop" in types
    # Check that events are sorted by start_ms
    start_times = [e.start_ms for e in events]
    assert start_times == sorted(start_times)


def test_render_scene_sfx_track_creates_wav(tmp_path: Path) -> None:
    service = AutoSFXService()
    events = [
        SFXEvent(sfx_type="whoosh", start_ms=0, volume_db=-6.0),
        SFXEvent(sfx_type="pop", start_ms=200, volume_db=-4.0),
    ]
    out_wav = tmp_path / "sfx.wav"
    result = service.render_scene_sfx_track(events, duration_ms=1000, output_path=out_wav)
    assert result.is_file()
    assert result.stat().st_size > 1000


def test_render_empty_events_creates_silent_track(tmp_path: Path) -> None:
    service = AutoSFXService()
    out_wav = tmp_path / "silent.wav"
    result = service.render_scene_sfx_track([], duration_ms=500, output_path=out_wav)
    assert result.is_file()
    assert result.stat().st_size > 500


def test_mix_sfx_with_voice(tmp_path: Path) -> None:
    service = AutoSFXService()
    voice_wav = tmp_path / "voice.wav"
    sfx_wav = tmp_path / "sfx.wav"
    mixed_wav = tmp_path / "mixed.wav"

    service.render_scene_sfx_track([], duration_ms=500, output_path=voice_wav)
    service.render_scene_sfx_track([SFXEvent(sfx_type="pop", start_ms=100)], duration_ms=500, output_path=sfx_wav)

    result = service.mix_sfx_with_voice(voice_wav, sfx_wav, mixed_wav)
    assert result.is_file()
    assert result.stat().st_size > 1000
