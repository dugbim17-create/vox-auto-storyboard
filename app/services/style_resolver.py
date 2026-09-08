"""Backward-compatible resolver for editable style drafts and applied snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas.style_contract import StyleDraftV1, StyleSnapshotV1
from app.services.prompts import StylePreset

_DEFAULT_PRESET = "editorial_collage"


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _first(*values: object, default: object = "") -> object:
    for value in values:
        if _present(value):
            return value
    return default


class StyleResolver:
    """Resolve draft preferences separately from production storyboard style."""

    def __init__(self, presets: Mapping[str, StylePreset] | None = None) -> None:
        self.presets = dict(presets or {})

    def resolve_draft(
        self,
        *,
        project_id: str,
        project_preset: str,
        storyboard: Mapping[str, Any] | None,
        draft_payload: Mapping[str, Any] | None = None,
    ) -> StyleDraftV1:
        draft = _mapping(draft_payload)
        anchor = _mapping(_mapping(storyboard).get("style_anchor"))
        preset_name = str(
            _first(draft.get("preset"), project_preset, default=_DEFAULT_PRESET)
        ).strip()
        preset = self.presets.get(preset_name)
        preset_values = preset.to_dict() if preset is not None else {}
        merged = {
            "schema_version": draft.get("schema_version", 1),
            "project_id": project_id,
            "revision": draft.get("revision", 1),
            "preset": preset_name,
            "visual_language": _first(
                draft.get("visual_language"),
                preset_values.get("visual_language"),
                anchor.get("visual_language"),
            ),
            "palette": _first(
                draft.get("palette"),
                preset_values.get("palette"),
                anchor.get("palette"),
                default=[],
            ),
            "texture": _first(
                draft.get("texture"),
                preset_values.get("texture"),
                anchor.get("texture"),
                default=[],
            ),
            "typography": _first(
                draft.get("typography"),
                preset_values.get("typography"),
                anchor.get("typography"),
            ),
            "negative_prompt": _first(
                draft.get("negative_prompt"),
                anchor.get("negative_prompt"),
                default=[],
            ),
            "continuity_rules": _first(
                draft.get("continuity_rules"),
                preset_values.get("continuity_rules"),
                anchor.get("continuity_rules"),
                default=[],
            ),
            "motion_profile": _first(
                draft.get("motion_profile"),
                anchor.get("motion_profile"),
                default="default",
            ),
            "renderer_theme": _first(
                draft.get("renderer_theme"),
                anchor.get("renderer_theme"),
                default={},
            ),
        }
        return StyleDraftV1.from_mapping(merged)

    def resolve_applied(
        self,
        storyboard: Mapping[str, Any] | None,
    ) -> StyleSnapshotV1:
        data = _mapping(storyboard)
        snapshot = _mapping(data.get("style_snapshot"))
        if snapshot:
            return StyleSnapshotV1.from_mapping(snapshot)
        anchor = _mapping(data.get("style_anchor"))
        preset_name = str(
            _first(
                anchor.get("preset"),
                data.get("style_preset"),
                default=_DEFAULT_PRESET,
            )
        ).strip()
        draft = StyleDraftV1.from_mapping(
            {
                "schema_version": 1,
                "project_id": str(data.get("project_id") or ""),
                "revision": 1,
                "preset": preset_name,
                "visual_language": anchor.get("visual_language", ""),
                "palette": anchor.get("palette", []),
                "texture": anchor.get("texture", []),
                "typography": anchor.get("typography", ""),
                "negative_prompt": anchor.get("negative_prompt", []),
                "continuity_rules": anchor.get("continuity_rules", []),
                "motion_profile": anchor.get("motion_profile", "default"),
                "renderer_theme": anchor.get("renderer_theme", {}),
            }
        )
        return StyleSnapshotV1.from_draft(draft, style_revision=1)


__all__ = ["StyleResolver"]
