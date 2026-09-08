"""Tests for P2-T04 Prompt pack.

Covers the acceptance criteria:

- prompt snapshot tests (every prompt file loads, has expected content);
- no hard-coded model IDs in any prompt;
- style preset can be injected (Jinja2 render + inject_style helper).
"""

from __future__ import annotations

from app.services.prompts import (
    PROMPT_FILES,
    StylePreset,
    get_prompt_pack,
    inject_style,
    load_presets,
)

PACK = get_prompt_pack()


def test_all_prompt_files_present() -> None:
    assert set(PROMPT_FILES) == {
        "system_storyboard",
        "scene_planner",
        "image_prompt",
        "motion_prompt",
        "repair_json",
    }


def test_prompts_load_nonempty() -> None:
    for name in PROMPT_FILES:
        text = PACK.load(name)
        assert isinstance(text, str)
        assert len(text.strip()) > 50, f"{name} is suspiciously short"


def test_system_prompt_requires_json_only() -> None:
    text = PACK.load("system_storyboard").lower()
    assert "return only json" in text
    assert "json" in text
    assert "markdown" in text


def test_system_prompt_no_hardcoded_model() -> None:
    # AC: no model ID hard-coded in any prompt.
    for name in PROMPT_FILES:
        text = PACK.load(name)
        assert "gemini" not in text.lower(), f"{name} hard-codes a gemini model"
        assert "claude" not in text.lower(), f"{name} hard-codes a claude model"
        assert "gpt-" not in text.lower(), f"{name} hard-codes a gpt model"


def test_system_prompt_no_hardcoded_provider() -> None:
    text = PACK.load("system_storyboard").lower()
    assert "cliproxy" not in text
    assert "flowkit" not in text


def test_system_prompt_motion_rule_present() -> None:
    text = PACK.load("system_storyboard").lower()
    assert "ken burns" in text
    assert "three" in text  # three independent layers


def test_system_prompt_scene_duration_rule() -> None:
    text = PACK.load("system_storyboard").lower()
    assert "4–7 second" in text or "4–7 s" in text or "between 4 and 7" in text


def test_motion_prompt_lists_templates() -> None:
    text = PACK.load("motion_prompt")
    assert "01_subject_slide_headline_pop" in text
    assert "12_conclusion_lockup" in text


# --------------------------------------------------------------------------- #
# Style presets
# --------------------------------------------------------------------------- #
def test_default_presets_discovered() -> None:
    presets = load_presets()
    assert "editorial_collage" in presets
    assert "documentary" in presets
    assert "minimal_motion" in presets


def test_editorial_collage_content() -> None:
    preset = load_presets()["editorial_collage"]
    assert preset.visual_language == "editorial paper collage"
    assert "off-white" in preset.palette
    assert "paper grain" in preset.texture


def test_style_preset_injection() -> None:
    preset = StylePreset(
        "custom",
        {
            "visual_language": "v",
            "palette": ["a", "b"],
            "texture": ["t"],
            "typography": "f",
            "continuity_rules": ["c"],
        },
    )
    base = "System prompt"
    rendered = inject_style(base, preset)
    assert rendered.startswith(base)
    assert "## Active style preset: custom" in rendered
    assert "visual_language: v" in rendered
    assert "palette: a, b" in rendered
    assert "continuity_rules: c" in rendered


def test_style_preset_default_injection_into_system_prompt() -> None:
    # The system prompt is a Jinja2 template; render it with a preset to prove
    # the style preset path works end-to-end for the main prompt.
    presets = load_presets()
    editorial = presets["editorial_collage"]
    system_rendered = PACK.system_prompt(preset=editorial)
    assert "editorial" in system_rendered.lower()
    assert "off-white" in system_rendered
    assert "paper grain" in system_rendered

    injected = inject_style(PACK.load("system_storyboard"), editorial)
    assert "editorial paper collage" in injected
    assert "off-white" in injected


def test_render_unknown_prompt_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        PACK.render("does_not_exist")
