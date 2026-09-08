"""Persist and read back editable project style drafts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.schemas.style_contract import StyleDraftV1
from app.services.prompts import StylePreset, load_presets
from app.services.style_resolver import StyleResolver
from app.storage.asset_store import AssetStore
from app.storage.repositories import ProjectRepo


class StyleProjectService:
    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        presets: Mapping[str, StylePreset] | None = None,
    ) -> None:
        self.store = AssetStore(project_root)
        self.presets = dict(presets or load_presets())
        self.resolver = StyleResolver(self.presets)

    def save_draft(
        self,
        project_id: str,
        session: Any,
        *,
        preset: str,
        visual_language: str,
        palette: str,
        texture: str,
        typography: str = "",
        negative_prompt: str = "",
        continuity_rules: str = "",
        motion_profile: str = "default",
        renderer_theme: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = ProjectRepo.get(session, project_id)
        if project is None:
            raise ValueError(f"project not found: {project_id}")
        preset = preset.strip()
        if not preset:
            raise ValueError("style preset is empty")
        storyboard = self._load_storyboard(project_id)
        prior = self.load_draft(project_id)
        candidate = self.resolver.resolve_draft(
            project_id=project_id,
            project_preset=preset or project.style_preset,
            storyboard=storyboard,
            draft_payload={
                "schema_version": 1,
                "revision": int(prior.get("revision", 1) or 1),
                "preset": preset,
                "visual_language": visual_language,
                "palette": _split_csv(palette),
                "texture": _split_csv(texture),
                "typography": typography,
                "negative_prompt": _split_csv(negative_prompt),
                "continuity_rules": _split_csv(continuity_rules),
                "motion_profile": motion_profile,
                "renderer_theme": dict(renderer_theme or {}),
            },
        )
        if prior and prior.get("draft_hash") != candidate.draft_hash:
            candidate = StyleDraftV1.from_mapping(
                {**candidate.to_dict(), "revision": int(prior.get("revision", 1)) + 1}
            )
        candidate_payload = candidate.to_dict()
        self.store.write_manifest(project_id, "style.json", candidate_payload)
        project.style_preset = candidate.preset
        session.commit()
        loaded = self.load_draft(project_id)
        if loaded.get("draft_hash") != candidate.draft_hash:
            raise ValueError("style draft read-back hash mismatch")
        return loaded

    def save(
        self,
        project_id: str,
        session: Any,
        *,
        preset: str,
        visual_language: str,
        palette: str,
        texture: str,
    ) -> dict[str, Any]:
        """Backward-compatible draft save for older callers."""
        return self.save_draft(
            project_id,
            session,
            preset=preset,
            visual_language=visual_language,
            palette=palette,
            texture=texture,
        )

    def load_draft(self, project_id: str) -> dict[str, Any]:
        try:
            raw = self.store.read_project_file(project_id, "manifests/style.json")
            payload = json.loads(raw.decode("utf-8"))
            draft = StyleDraftV1.from_mapping(payload)
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        return draft.to_dict()

    def load(self, project_id: str) -> dict[str, Any]:
        """Backward-compatible alias."""
        return self.load_draft(project_id)

    def _load_storyboard(self, project_id: str) -> dict[str, Any]:
        try:
            raw = self.store.read_project_file(project_id, "manifests/storyboard.json")
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def _split_csv(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


__all__ = ["StyleProjectService"]
