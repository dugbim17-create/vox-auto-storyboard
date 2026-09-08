"""Durable project-level visual prompt and asset selection operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.asset_store import AssetStore


class VisualProjectService:
    def __init__(self, *, project_root: str | Path | None = None) -> None:
        self.store = AssetStore(project_root)

    def update_storyboard_prompt(
        self,
        project_id: str,
        scene_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("image prompt is empty")
        path = self.store.subdir(project_id, "manifests") / "storyboard.json"
        if not path.is_file():
            raise ValueError(f"storyboard manifest not found: {project_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        scenes = payload.get("scenes")
        if not isinstance(scenes, list):
            raise ValueError("storyboard scenes are invalid")
        target = next(
            (scene for scene in scenes if isinstance(scene, dict) and scene.get("scene_id") == scene_id),
            None,
        )
        if target is None:
            raise ValueError(f"scene not found in storyboard: {scene_id}")
        target["image_prompt"] = prompt
        self.store.write_manifest(project_id, "storyboard.json", payload)
        return target


__all__ = ["VisualProjectService"]
