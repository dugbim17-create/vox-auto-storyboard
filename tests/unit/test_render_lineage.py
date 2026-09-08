from __future__ import annotations

import json
from pathlib import Path

from app.services.render_lineage import (
    build_final_render_lineage,
    build_motion_lineage_envelope,
    build_scene_render_lineage,
    write_lineage_manifest,
)


def _style() -> dict:
    return {
        "schema_version": 1,
        "style_revision": 4,
        "visual_hash": "visual-A",
        "motion_hash": "motion-A",
        "render_theme_hash": "theme-A",
    }


def test_motion_lineage_envelope_preserves_plan_and_style_hashes() -> None:
    plan = {"scene_id": "scene_001", "duration_ms": 1000, "fps": 30, "layers": []}
    envelope = build_motion_lineage_envelope(plan, style_snapshot=_style())
    assert envelope["kind"] == "motion_plan"
    assert envelope["style"] == {
        "style_revision": 4,
        "visual_hash": "visual-A",
        "motion_hash": "motion-A",
        "render_theme_hash": "theme-A",
    }
    assert envelope["payload"] == plan
    assert len(envelope["payload_sha256"]) == 64


def test_scene_lineage_captures_renderer_and_all_current_inputs() -> None:
    result = build_scene_render_lineage(
        project_id="p1",
        scene_id="scene_001",
        renderer="ffmpeg",
        renderer_version="system",
        style_snapshot=_style(),
        motion_plan_sha256="motion-file-hash",
        selected_asset_id="asset-1",
        selected_asset_sha256="image-hash",
        output_path="scene_001.mp4",
        output_sha256="video-hash",
    )
    assert result["renderer"] == {"name": "ffmpeg", "version": "system"}
    assert result["inputs"]["selected_asset_sha256"] == "image-hash"
    assert result["style"]["render_theme_hash"] == "theme-A"
    assert result["output"]["sha256"] == "video-hash"


def test_final_lineage_captures_scene_audio_subtitle_and_style_hashes() -> None:
    result = build_final_render_lineage(
        project_id="p1",
        style_snapshot=_style(),
        scene_outputs=[{"scene_id": "scene_001", "sha256": "scene-hash"}],
        audio_sha256="audio-hash",
        subtitle_sha256="srt-hash",
        output_path="final.mp4",
        output_sha256="final-hash",
    )
    assert result["scenes"] == [{"scene_id": "scene_001", "sha256": "scene-hash"}]
    assert result["audio_sha256"] == "audio-hash"
    assert result["subtitle_sha256"] == "srt-hash"
    assert result["style"]["visual_hash"] == "visual-A"


def test_lineage_manifest_write_is_atomic_and_readable(tmp_path: Path) -> None:
    path = tmp_path / "manifests" / "scene.json"
    payload = {"kind": "scene_render", "scene_id": "scene_001"}
    write_lineage_manifest(path, payload)
    assert json.loads(path.read_text("utf-8")) == payload
    assert not list(path.parent.glob("*.tmp"))
