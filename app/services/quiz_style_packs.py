"""Pure, validated registry and immutable snapshots for Quiz Phase B styles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

STYLE_IDS = (
    "sport-scoreboard",
    "editorial-culture",
    "clear-knowledge",
)
STYLE_VERSION = 1
MOTION_LEVELS = ("low", "medium", "high")


class StylePackError(ValueError):
    """Raised when a visual style selection or snapshot is unsafe or invalid."""


_STYLE_PACKS: dict[str, dict[str, Any]] = {
    "sport-scoreboard": {
        "id": "sport-scoreboard",
        "version": STYLE_VERSION,
        "motion": "medium",
        "mascot": False,
        "snapshot": {
            "palette": {
                "background": "navy",
                "panel": "scoreboard-blue",
                "accent": "yellow",
                "accent_secondary": "signal-red",
                "text": "warm-white",
            },
            "typography": {
                "display": "compact-bold-sans",
                "body": "clear-sans",
                "hierarchy": "score-question-choices",
            },
            "spacing": {"density": "compact", "gutter": 24, "safe_margin": 48},
            "shapes": {"panels": "hard-rounded", "markers": "block", "rules": "broadcast"},
            "background": {"kind": "procedural", "texture": "restrained-stadium-lines"},
            "motion_rules": {"question": "fast-enter", "countdown": "emphasize", "answer": "score-reveal", "amplitude": {"low": 0.35, "medium": 0.7, "high": 1.0}},
        },
    },
    "editorial-culture": {
        "id": "editorial-culture",
        "version": STYLE_VERSION,
        "motion": "medium",
        "mascot": False,
        "snapshot": {
            "palette": {
                "background": "warm-paper",
                "panel": "ivory",
                "accent": "editorial-red",
                "accent_secondary": "deep-teal",
                "text": "charcoal",
            },
            "typography": {
                "display": "editorial-bold",
                "body": "humanist-sans",
                "hierarchy": "headline-caption-fact",
            },
            "spacing": {"density": "open", "gutter": 32, "safe_margin": 56},
            "shapes": {"panels": "rule-led", "markers": "textual", "rules": "print-editorial"},
            "background": {"kind": "procedural", "texture": "paper-and-field-notes"},
            "motion_rules": {"question": "calm-reveal", "countdown": "subtle", "answer": "fact-unfold", "amplitude": {"low": 0.35, "medium": 0.7, "high": 1.0}},
        },
    },
    "clear-knowledge": {
        "id": "clear-knowledge",
        "version": STYLE_VERSION,
        "motion": "medium",
        "mascot": False,
        "snapshot": {
            "palette": {
                "background": "pale-sage",
                "panel": "clean-white",
                "accent": "teal",
                "accent_secondary": "orange",
                "text": "deep-charcoal",
            },
            "typography": {
                "display": "readable-bold-sans",
                "body": "clear-sans",
                "hierarchy": "question-rule-evidence-takeaway",
            },
            "spacing": {"density": "generous", "gutter": 32, "safe_margin": 56},
            "shapes": {"panels": "soft-rounded", "markers": "circle", "rules": "quiet"},
            "background": {"kind": "procedural", "texture": "low-noise-grid"},
            "motion_rules": {"question": "clear-enter", "countdown": "steady", "answer": "takeaway-reveal", "amplitude": {"low": 0.35, "medium": 0.7, "high": 1.0}},
        },
    },
}


def _validate_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n\x00"):
        raise StylePackError(f"invalid {field}")
    return value.strip()


def _validate_motion(motion: object) -> str:
    value = _validate_text(motion, "motion")
    if value not in MOTION_LEVELS:
        raise StylePackError(f"invalid motion: {value}")
    return value


def _validate_snapshot(snapshot: object) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping) or not snapshot:
        raise StylePackError("invalid snapshot")
    clean = deepcopy(dict(snapshot))
    serialized = repr(clean).lower()
    if any(token in serialized for token in ("javascript:", "file://", "..\\", "../", "<script", "import ", "__")):
        raise StylePackError("unsafe snapshot")
    for key in ("palette", "typography", "spacing", "shapes", "background", "motion_rules"):
        if key not in clean or not isinstance(clean[key], Mapping) or not clean[key]:
            raise StylePackError(f"invalid snapshot.{key}")
    if not isinstance(clean["spacing"].get("safe_margin"), int) or not 0 <= clean["spacing"]["safe_margin"] <= 240:
        raise StylePackError("invalid snapshot spacing.safe_margin")
    return clean


def get_style_pack(style_id: str) -> dict[str, Any]:
    key = str(style_id or "").strip()
    if not key or key not in _STYLE_PACKS:
        raise StylePackError(f"Unknown visual style: {key}")
    return deepcopy(_STYLE_PACKS[key])


def resolve_style_snapshot(
    style_id: str,
    *,
    locale: str = "en-US",
    motion: str = "medium",
    mascot: bool = False,
    snapshot_override: Mapping[str, Any] | None = None,
    version: int | None = None,
) -> dict[str, Any]:
    pack = get_style_pack(style_id)
    locale_value = _validate_text(locale, "locale")
    if len(locale_value) < 2 or " " in locale_value:
        raise StylePackError("invalid locale")
    motion_value = _validate_motion(motion)
    if not isinstance(mascot, bool):
        raise StylePackError("mascot must be boolean")
    if version is not None and (isinstance(version, bool) or not isinstance(version, int)):
        raise StylePackError("invalid visual style version")
    if version is not None and version != pack["version"]:
        raise StylePackError(
            f"unsupported visual style version {version}; supported version is {pack['version']}"
        )
    snapshot = _validate_snapshot(snapshot_override) if snapshot_override is not None else deepcopy(pack["snapshot"])
    return {
        "id": pack["id"],
        "version": pack["version"],
        "motion": motion_value,
        "mascot": mascot,
        "locale": locale_value,
        "snapshot": snapshot,
    }


__all__ = [
    "MOTION_LEVELS",
    "STYLE_IDS",
    "STYLE_VERSION",
    "StylePackError",
    "get_style_pack",
    "resolve_style_snapshot",
]
