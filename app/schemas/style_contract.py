"""Versioned project style draft and applied storyboard snapshot contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

STYLE_SCHEMA_VERSION = 1


class StyleContractError(ValueError):
    """Raised when a style draft or snapshot cannot be normalized safely."""


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    items = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def _canonical_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _canonical_value(item) for key, item in sorted(value.items())}


def _canonical_value(value: object) -> Any:
    if isinstance(value, Mapping):
        return _canonical_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        _canonical_mapping(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class StyleDraftV1:
    schema_version: int
    project_id: str
    revision: int
    preset: str
    visual_language: str
    palette: tuple[str, ...]
    texture: tuple[str, ...]
    typography: str
    negative_prompt: tuple[str, ...]
    continuity_rules: tuple[str, ...]
    motion_profile: str
    renderer_theme: dict[str, Any]
    draft_hash: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> StyleDraftV1:
        version = int(data.get("schema_version", STYLE_SCHEMA_VERSION))
        if version != STYLE_SCHEMA_VERSION:
            raise StyleContractError(f"unsupported schema_version: {version}")
        preset = _clean_text(data.get("preset"))
        if not preset:
            raise StyleContractError("style preset is empty")
        creative = {
            "schema_version": version,
            "preset": preset,
            "visual_language": _clean_text(data.get("visual_language")),
            "palette": _clean_list(data.get("palette")),
            "texture": _clean_list(data.get("texture")),
            "typography": _clean_text(data.get("typography")),
            "negative_prompt": _clean_list(data.get("negative_prompt")),
            "continuity_rules": _clean_list(data.get("continuity_rules")),
            "motion_profile": _clean_text(data.get("motion_profile")) or "default",
            "renderer_theme": _canonical_mapping(data.get("renderer_theme")),
        }
        return cls(
            project_id=_clean_text(data.get("project_id")),
            revision=max(1, int(data.get("revision", 1))),
            draft_hash=_digest(creative),
            **creative,
        )

    def creative_values(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "preset": self.preset,
            "visual_language": self.visual_language,
            "palette": list(self.palette),
            "texture": list(self.texture),
            "typography": self.typography,
            "negative_prompt": list(self.negative_prompt),
            "continuity_rules": list(self.continuity_rules),
            "motion_profile": self.motion_profile,
            "renderer_theme": _canonical_mapping(self.renderer_theme),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "revision": self.revision,
            **self.creative_values(),
            "draft_hash": self.draft_hash,
        }


@dataclass(frozen=True)
class StyleSnapshotV1:
    schema_version: int
    style_revision: int
    preset: str
    visual_language: str
    palette: tuple[str, ...]
    texture: tuple[str, ...]
    typography: str
    negative_prompt: tuple[str, ...]
    continuity_rules: tuple[str, ...]
    motion_profile: str
    renderer_theme: dict[str, Any]
    visual_hash: str
    motion_hash: str
    render_theme_hash: str

    @classmethod
    def from_draft(cls, draft: StyleDraftV1, *, style_revision: int) -> StyleSnapshotV1:
        visual_payload = {
            "schema_version": draft.schema_version,
            "preset": draft.preset,
            "visual_language": draft.visual_language,
            "palette": draft.palette,
            "texture": draft.texture,
            "typography": draft.typography,
            "negative_prompt": draft.negative_prompt,
            "continuity_rules": draft.continuity_rules,
        }
        motion_payload = {
            "schema_version": draft.schema_version,
            "motion_profile": draft.motion_profile,
        }
        render_payload = {
            "schema_version": draft.schema_version,
            "renderer_theme": draft.renderer_theme,
            "typography": draft.typography,
        }
        return cls(
            schema_version=draft.schema_version,
            style_revision=max(1, int(style_revision)),
            preset=draft.preset,
            visual_language=draft.visual_language,
            palette=draft.palette,
            texture=draft.texture,
            typography=draft.typography,
            negative_prompt=draft.negative_prompt,
            continuity_rules=draft.continuity_rules,
            motion_profile=draft.motion_profile,
            renderer_theme=_canonical_mapping(draft.renderer_theme),
            visual_hash=_digest(visual_payload),
            motion_hash=_digest(motion_payload),
            render_theme_hash=_digest(render_payload),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> StyleSnapshotV1:
        draft = StyleDraftV1.from_mapping(
            {
                **data,
                "revision": data.get("style_revision", 1),
                "project_id": "",
            }
        )
        return cls.from_draft(draft, style_revision=int(data.get("style_revision", 1)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "style_revision": self.style_revision,
            "preset": self.preset,
            "visual_language": self.visual_language,
            "palette": list(self.palette),
            "texture": list(self.texture),
            "typography": self.typography,
            "negative_prompt": list(self.negative_prompt),
            "continuity_rules": list(self.continuity_rules),
            "motion_profile": self.motion_profile,
            "renderer_theme": _canonical_mapping(self.renderer_theme),
            "visual_hash": self.visual_hash,
            "motion_hash": self.motion_hash,
            "render_theme_hash": self.render_theme_hash,
        }


__all__ = [
    "STYLE_SCHEMA_VERSION",
    "StyleContractError",
    "StyleDraftV1",
    "StyleSnapshotV1",
]
