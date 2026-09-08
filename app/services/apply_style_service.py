"""Explicitly apply a saved style draft to the production storyboard revision."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.schemas.storyboard import validate_storyboard
from app.schemas.style_contract import StyleDraftV1, StyleSnapshotV1
from app.services.artifact_freshness import summarize_assets
from app.services.prompts import StylePreset, load_presets
from app.services.style_project_service import StyleProjectService
from app.storage.asset_store import AssetStore
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo, StateEventRepo


class ApplyStyleService:
    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        presets: Mapping[str, StylePreset] | None = None,
    ) -> None:
        self.store = AssetStore(project_root)
        self.presets = dict(presets or load_presets())

    def apply(self, project_id: str, session: Any) -> dict[str, Any]:
        project = ProjectRepo.get(session, project_id)
        if project is None:
            raise ValueError(f"project not found: {project_id}")
        storyboard = self._load_storyboard(project_id)
        draft_payload = StyleProjectService(
            project_root=self.store.base,
            presets=self.presets,
        ).load_draft(project_id)
        if not draft_payload:
            raise ValueError("style draft not found; save the draft before applying")
        draft = StyleDraftV1.from_mapping(draft_payload)
        snapshot = StyleSnapshotV1.from_draft(
            draft,
            style_revision=draft.revision,
        )
        candidate = dict(storyboard)
        candidate["style_anchor"] = {
            "preset": snapshot.preset,
            "visual_language": snapshot.visual_language,
            "palette": list(snapshot.palette),
            "texture": list(snapshot.texture),
            "typography": snapshot.typography or "none",
            "negative_prompt": list(snapshot.negative_prompt),
            "continuity_rules": list(snapshot.continuity_rules),
            "motion_profile": snapshot.motion_profile,
            "renderer_theme": dict(snapshot.renderer_theme),
        }
        candidate["style_snapshot"] = snapshot.to_dict()
        validate_storyboard(candidate)
        self.store.write_manifest(project_id, "storyboard.json", candidate)
        project.style_preset = snapshot.preset
        StateEventRepo.record(
            session,
            project_id=project_id,
            from_state=project.status,
            to_state=project.status,
            reason=f"style applied revision={snapshot.style_revision} visual={snapshot.visual_hash}",
        )
        session.commit()
        readback = self._load_storyboard(project_id)
        applied = readback.get("style_snapshot") if isinstance(readback, dict) else None
        if not isinstance(applied, dict) or applied.get("visual_hash") != snapshot.visual_hash:
            raise ValueError("applied style read-back hash mismatch")
        selected_assets = [
            AssetRepo.get_selected_for_scene(session, project_id, scene.scene_id)
            for scene in SceneRepo.list(session, project_id)
        ]
        result = StyleSnapshotV1.from_mapping(applied).to_dict()
        result["freshness"] = summarize_assets(
            selected_assets,
            applied_visual_hash=snapshot.visual_hash,
        )
        return result

    def _load_storyboard(self, project_id: str) -> dict[str, Any]:
        try:
            raw = self.store.read_project_file(project_id, "manifests/storyboard.json")
        except OSError as exc:
            raise ValueError(f"storyboard manifest not found: {project_id}") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("storyboard manifest is invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("storyboard manifest is invalid")
        return payload


__all__ = ["ApplyStyleService"]
