"""Prompt pack loader (P2-T04).

Loads the markdown prompt pack from ``prompts/`` and the style presets from
``presets/``. Prompts are Jinja2 templates so style presets can be injected
into the system prompt at call time. No model IDs, provider names, ports or
credentials are hard-coded in any prompt file — the orchestrator injects them
separately.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"
PRESETS_DIR = REPO_ROOT / "presets"

# Prompt pack filenames (P2-T04).
PROMPT_FILES = {
    "system_storyboard": "system_storyboard.md",
    "scene_planner": "scene_planner.md",
    "image_prompt": "image_prompt.md",
    "motion_prompt": "motion_prompt.md",
    "repair_json": "repair_json.md",
}

class PromptPackError(ValueError):
    """Raised when a prompt file or preset cannot be loaded."""


class PromptPack:
    """Loads and renders prompt templates from ``prompts/``."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = (prompts_dir or PROMPTS_DIR).resolve()
        if not self.prompts_dir.is_dir():
            raise PromptPackError(f"prompts dir missing: {self.prompts_dir}")
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._cache: dict[str, str] = {}

    def load(self, name: str) -> str:
        """Return the raw (unrendered) prompt text for a pack key."""
        if name not in PROMPT_FILES:
            raise PromptPackError(f"unknown prompt: {name}")
        if name not in self._cache:
            path = self.prompts_dir / PROMPT_FILES[name]
            if not path.is_file():
                raise PromptPackError(f"missing prompt file: {path}")
            self._cache[name] = path.read_text(encoding="utf-8")
        return self._cache[name]

    def render(self, name: str, **context: Any) -> str:
        """Render a prompt template with the given Jinja2 context."""
        template = self._env.get_template(PROMPT_FILES[name])
        return template.render(**context)

    def system_prompt(self, preset: StylePreset | None = None) -> str:
        """Render the main storyboard system prompt, injecting a style preset.

        This is the end-to-end "style preset inject được" path: the injected
        ``style_block`` is produced by :func:`inject_style` so it stays
        consistent with what :func:`inject_style` emits elsewhere.
        """
        context: dict[str, Any] = {}
        if preset is not None:
            context["style_block"] = inject_style("", preset).strip()
        return self._env.get_template(PROMPT_FILES["system_storyboard"]).render(**context)


class StylePreset:
    """A named style preset loaded from ``presets/*.yaml``."""

    def __init__(self, name: str, data: dict[str, Any]) -> None:
        self.name = name
        self.data = data

    @property
    def visual_language(self) -> str:
        return str(self.data.get("visual_language", ""))

    @property
    def palette(self) -> list[str]:
        return list(self.data.get("palette", []))

    @property
    def texture(self) -> list[str]:
        return list(self.data.get("texture", []))

    @property
    def typography(self) -> str:
        return str(self.data.get("typography", ""))

    @property
    def continuity_rules(self) -> list[str]:
        return list(self.data.get("continuity_rules", []))

    def to_dict(self) -> dict[str, Any]:
        return {
            "visual_language": self.visual_language,
            "palette": self.palette,
            "texture": self.texture,
            "typography": self.typography,
            "continuity_rules": self.continuity_rules,
        }


def load_presets(presets_dir: Path | None = None) -> dict[str, StylePreset]:
    """Discover and load every ``presets/*.yaml`` as a ``StylePreset``."""
    directory = (presets_dir or PRESETS_DIR).resolve()
    result: dict[str, StylePreset] = {}
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.warning("preset yaml error %s: %s", path, exc)
            continue
        name = str(data.get("name") or path.stem)
        result[name] = StylePreset(name=name, data=data)
    return result


def _style_block(preset: StylePreset) -> str:
    """Render the style preset body used by both inject_style and the Jinja2
    system-prompt template."""
    return "\n".join(
        [
            f"- visual_language: {preset.visual_language}",
            f"- palette: {', '.join(preset.palette)}",
            f"- texture: {', '.join(preset.texture)}",
            f"- typography: {preset.typography}",
            f"- continuity_rules: {', '.join(preset.continuity_rules)}",
        ]
    )


def inject_style(prompt: str, preset: StylePreset) -> str:
    """Append a rendered style preset block to a prompt for the LLM.

    This is the mechanism used by services to ensure every prompt carries the
    same visual language (P2-T04: style preset inject được).
    """
    return f"{prompt}\n\n## Active style preset: {preset.name}\n{_style_block(preset)}"


_default_pack: PromptPack | None = None


def get_prompt_pack() -> PromptPack:
    """Singleton accessor for the project's prompt pack."""
    global _default_pack
    if _default_pack is None:
        _default_pack = PromptPack()
    return _default_pack
