"""Storyboard JSON Schema validation (P2-T03).

Loads ``storyboard.schema.json`` and validates generated storyboard objects
against it using ``jsonschema``. In addition to JSON-schema structural rules,
we enforce workflow rules from MASTER_PLAN section 17.1 that cannot be
expressed (cost-effectively) in a pure JSON schema:

- ``scenes`` count clamp (section 7.2): 4..20;
- ``scene_id`` values are unique;
- ``order`` is a contiguous sequence 1..N;
- ``script_span`` does not decrease across scenes (approximate ordering check).

The schema itself encodes: required props (summary, style_anchor, characters,
locations, scenes), per-scene requirements (narration_text, image_prompt,
visual_summary, motion_template, estimated_duration_seconds), and scene-count
bounds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parent / "storyboard.schema.json"
MIN_SCENES = 4
MAX_SCENES = 20


class StoryboardValidationError(ValueError):
    """Raised when a storyboard fails schema or workflow validation."""


def load_schema() -> dict[str, Any]:
    """Load and cache the storyboard JSON schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


_SCHEMA: dict[str, Any] | None = None


def get_schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = load_schema()
    return _SCHEMA


def validate_storyboard(storyboard: dict[str, Any]) -> None:
    """Validate a storyboard dict. Raises ``StoryboardValidationError`` on failure.

    Includes both the JSON-schema check and the workflow rules in section 17.1
    (unique scene ids, contiguous order, scene count clamp).
    """
    try:
        jsonschema.validate(instance=storyboard, schema=get_schema())
    except jsonschema.ValidationError as exc:
        raise StoryboardValidationError(f"schema: {exc.message}") from exc

    scenes = storyboard.get("scenes", [])

    # scene count clamp (section 7.2)
    if not (MIN_SCENES <= len(scenes) <= MAX_SCENES):
        raise StoryboardValidationError(
            f"scene count {len(scenes)} outside [{MIN_SCENES}, {MAX_SCENES}]"
        )

    # scene ids unique
    ids = [scene.get("scene_id") for scene in scenes]
    if len(set(ids)) != len(ids):
        raise StoryboardValidationError("scene ids must be unique")

    # order contiguous 1..N
    orders = [scene.get("order") for scene in scenes]
    if orders != list(range(1, len(scenes) + 1)):
        raise StoryboardValidationError(
            f"scene order must be contiguous 1..{len(scenes)}, got {orders}"
        )

    # script_span start_char non-decreasing (approximate coverage sanity check)
    last_end = -1
    for scene in scenes:
        span = scene.get("script_span", {})
        start = span.get("start_char")
        end = span.get("end_char")
        if start is None or end is None:
            continue
        if start < last_end:
            raise StoryboardValidationError(
                f"{scene.get('scene_id')} script_span start {start} overlaps "
                f"previous end {last_end}"
            )
        last_end = max(last_end, end or 0)


def is_valid_storyboard(storyboard: dict[str, Any]) -> bool:
    """Return True when the storyboard passes validation (non-raising)."""
    try:
        validate_storyboard(storyboard)
    except StoryboardValidationError:
        return False
    return True
