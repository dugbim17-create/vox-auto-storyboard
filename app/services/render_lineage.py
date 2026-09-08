"""Renderer-neutral lineage manifests for motion, scene and final artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _style_lineage(style_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = style_snapshot if isinstance(style_snapshot, dict) else {}
    return {
        "style_revision": int(snapshot.get("style_revision") or 0),
        "visual_hash": str(snapshot.get("visual_hash") or ""),
        "motion_hash": str(snapshot.get("motion_hash") or ""),
        "render_theme_hash": str(snapshot.get("render_theme_hash") or ""),
    }


def build_motion_lineage_envelope(
    motion_plan: dict[str, Any],
    *,
    style_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "motion_plan",
        "scene_id": str(motion_plan.get("scene_id") or ""),
        "style": _style_lineage(style_snapshot),
        "payload_sha256": _sha256_payload(motion_plan),
        "payload": motion_plan,
    }


def build_scene_render_lineage(
    *,
    project_id: str,
    scene_id: str,
    renderer: str,
    renderer_version: str,
    style_snapshot: dict[str, Any] | None,
    motion_plan_sha256: str,
    selected_asset_id: str,
    selected_asset_sha256: str,
    output_path: str,
    output_sha256: str,
    visual_stage_sha256: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "scene_render",
        "project_id": project_id,
        "scene_id": scene_id,
        "renderer": {"name": renderer, "version": renderer_version},
        "style": _style_lineage(style_snapshot),
        "inputs": {
            "motion_plan_sha256": motion_plan_sha256,
            "visual_stage_sha256": visual_stage_sha256,
            "selected_asset_id": selected_asset_id,
            "selected_asset_sha256": selected_asset_sha256,
        },
        "output": {"path": output_path, "sha256": output_sha256},
    }


def build_final_render_lineage(
    *,
    project_id: str,
    style_snapshot: dict[str, Any] | None,
    scene_outputs: list[dict[str, str]],
    audio_sha256: str,
    subtitle_sha256: str,
    output_path: str,
    output_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "final_render",
        "project_id": project_id,
        "style": _style_lineage(style_snapshot),
        "scenes": scene_outputs,
        "audio_sha256": audio_sha256,
        "subtitle_sha256": subtitle_sha256,
        "output": {"path": output_path, "sha256": output_sha256},
    }


def write_lineage_manifest(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    candidate = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        candidate.write_bytes(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        )
        os.replace(candidate, target)
    finally:
        candidate.unlink(missing_ok=True)
    return target


__all__ = [
    "build_final_render_lineage",
    "build_motion_lineage_envelope",
    "build_scene_render_lineage",
    "write_lineage_manifest",
]
