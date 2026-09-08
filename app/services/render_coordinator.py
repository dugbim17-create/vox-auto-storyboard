"""Single scene-render dispatch seam shared by GUI, CLI and retries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.render_lineage import build_scene_render_lineage, write_lineage_manifest
from app.storage.asset_store import AssetStore, sha256_file


@dataclass(frozen=True)
class CoordinatedSceneResult:
    project_id: str
    scene_id: str
    renderer: str
    renderer_version: str
    output_path: Path
    sha256: str
    lineage_path: Path


class RenderCoordinator:
    def __init__(self, *, renderer: Any, project_root: str | Path | None = None) -> None:
        self.renderer = renderer
        self.store = AssetStore(project_root)

    def render_scene(
        self,
        *,
        project_id: str,
        scene_id: str,
        selected_asset: Any,
    ) -> CoordinatedSceneResult:
        storyboard = self._read_json(
            self.store.subdir(project_id, "manifests") / "storyboard.json"
        )
        style = storyboard.get("style_snapshot")
        if not isinstance(style, dict):
            style = {}
        visual_hash = str(style.get("visual_hash") or "")
        asset_hash = str(getattr(selected_asset, "visual_style_hash", "") or "")
        if visual_hash and asset_hash != visual_hash:
            raise ValueError(
                f"stale selected image: asset={asset_hash or 'unknown'} applied={visual_hash}"
            )
        motion_path = (
            self.store.subdir(project_id, "manifests") / "motion" / f"{scene_id}.json"
        )
        envelope = self._read_json(motion_path)
        payload = envelope.get("payload") if envelope.get("kind") == "motion_plan" else envelope
        motion_style = envelope.get("style") if isinstance(envelope.get("style"), dict) else {}
        expected_motion = str(style.get("motion_hash") or "")
        actual_motion = str(motion_style.get("motion_hash") or "")
        if expected_motion and actual_motion != expected_motion:
            raise ValueError(
                f"stale motion plan: plan={actual_motion or 'unknown'} applied={expected_motion}"
            )
        if not isinstance(payload, dict):
            raise ValueError(f"invalid motion plan: {scene_id}")

        output, _probe = self.renderer.render_scene(
            project_id,
            scene_id,
            payload,
            project_root=self.store.base,
        )
        output_path = Path(output)
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise ValueError(f"renderer produced no scene artifact: {output_path}")
        output_hash = sha256_file(output_path)
        lineage = build_scene_render_lineage(
            project_id=project_id,
            scene_id=scene_id,
            renderer=str(getattr(self.renderer, "renderer_name", "ffmpeg")),
            renderer_version=str(getattr(self.renderer, "renderer_version", "unknown")),
            style_snapshot=style,
            motion_plan_sha256=str(envelope.get("payload_sha256") or sha256_file(motion_path)),
            selected_asset_id=str(getattr(selected_asset, "asset_id", "")),
            selected_asset_sha256=str(getattr(selected_asset, "sha256", "")),
            output_path=str(output_path),
            output_sha256=output_hash,
        )
        lineage_path = (
            self.store.subdir(project_id, "manifests") / "render" / f"{scene_id}.json"
        )
        write_lineage_manifest(lineage_path, lineage)
        return CoordinatedSceneResult(
            project_id=project_id,
            scene_id=scene_id,
            renderer=lineage["renderer"]["name"],
            renderer_version=lineage["renderer"]["version"],
            output_path=output_path,
            sha256=output_hash,
            lineage_path=lineage_path,
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ValueError(f"manifest missing: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"manifest invalid: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"manifest invalid: {path}")
        return payload


__all__ = ["CoordinatedSceneResult", "RenderCoordinator"]
