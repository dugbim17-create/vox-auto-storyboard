"""Compile canonical semantic scenes against measured narration timing."""

from __future__ import annotations

from typing import Any

from app.schemas.editorial_timeline import VoiceTimeline
from app.schemas.semantic_scene import SemanticSceneError, SemanticSceneSpec


def compile_semantic_scene(
    spec: SemanticSceneSpec,
    voice: VoiceTimeline,
) -> dict[str, Any]:
    payload = spec.payload
    if spec.scene_id != voice.scene_id:
        raise SemanticSceneError("scene and voice timeline ids do not match")
    if int(payload["duration_ms"]) != voice.duration_ms:
        raise SemanticSceneError("scene duration must equal measured voice duration")
    if int(payload["fps"]) != voice.fps:
        raise SemanticSceneError("scene fps must equal voice timeline fps")
    actions: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    for beat in payload["beats"]:
        anchor = voice.resolve_anchor(str(beat["anchor"]))
        for raw in beat["actions"]:
            duration_ms = int(raw["duration_ms"])
            end_ms = anchor.start_ms + duration_ms
            if end_ms > voice.duration_ms:
                raise SemanticSceneError(f"action {raw['action_id']} exceeds voice duration")
            action = dict(raw)
            action.update(
                {
                    "beat_id": beat["beat_id"],
                    "narration_anchor": anchor.text,
                    "start_ms": anchor.start_ms,
                    "end_ms": end_ms,
                    "start_frame": voice.frame_at(anchor.start_ms),
                    "end_frame": voice.frame_at(end_ms),
                }
            )
            actions.append(action)
            checkpoints.append(
                {
                    "action_id": action["action_id"],
                    "before_frame": action["start_frame"],
                    "action_frame": round((action["start_frame"] + action["end_frame"]) / 2),
                    "after_frame": action["end_frame"],
                    "hold_policy": beat.get("hold_policy", "action_required"),
                }
            )
    return {
        "schema_version": 2,
        "kind": "semantic_motion_plan",
        "scene_id": spec.scene_id,
        "scene_spec_sha256": spec.sha256,
        "duration_ms": voice.duration_ms,
        "fps": voice.fps,
        "motion_fps": int(payload["motion_fps"]),
        "grammar": payload["grammar"],
        "assets": [dict(item) for item in payload["assets"]],
        "procedural_actions": actions,
        "checkpoints": checkpoints,
    }


__all__ = ["compile_semantic_scene"]
