"""Safe background source resolution for opt-in Quiz style packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.services.quiz_style_packs import get_style_pack


class BackgroundSpecError(ValueError):
    """Raised when a background source is missing or outside an approved root."""


def resolve_background(
    style: Mapping[str, Any] | None,
    *,
    local_path: str | Path | None = None,
    approved_root: str | Path | None = None,
) -> dict[str, Any]:
    style_data = dict(style or {})
    style_id = str(style_data.get("id") or "clear-knowledge")
    pack = get_style_pack(style_id)
    snapshot = pack["snapshot"]
    background = snapshot["background"]
    if local_path is None:
        return {
            "kind": "procedural",
            "texture": str(background.get("texture") or "subtle-texture"),
            "source": None,
            "mascot": False,
        }
    if approved_root is None:
        raise BackgroundSpecError("local background requires an approved root")
    root = Path(approved_root).resolve()
    candidate = Path(local_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BackgroundSpecError("local background is outside approved root") from exc
    if not candidate.exists():
        raise BackgroundSpecError(f"local background missing: {candidate}")
    if not candidate.is_file():
        raise BackgroundSpecError(f"local background must be a file: {candidate}")
    return {
        "kind": "local",
        "texture": str(background.get("texture") or "approved-local"),
        "source": str(candidate),
        "mascot": False,
    }


__all__ = ["BackgroundSpecError", "resolve_background"]
