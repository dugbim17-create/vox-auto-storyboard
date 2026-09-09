from __future__ import annotations

from pathlib import Path

import pytest

from app.services.quiz_background import (
    BackgroundSpecError,
    resolve_background,
)


def test_default_background_is_deterministic_procedural_and_does_not_scan_user_data() -> None:
    background = resolve_background({"id": "clear-knowledge"})

    assert background == resolve_background({"id": "clear-knowledge"})
    assert background["kind"] == "procedural"
    assert background["texture"] in {"low-noise-grid", "restrained-stadium-lines", "paper-and-field-notes"}
    assert background["source"] is None


def test_approved_local_background_requires_explicit_safe_path(tmp_path: Path) -> None:
    permitted = tmp_path / "approved.png"
    permitted.write_bytes(b"fixture")

    result = resolve_background(
        {"id": "clear-knowledge"},
        local_path=permitted,
        approved_root=tmp_path,
    )
    assert result["kind"] == "local"
    assert result["source"] == str(permitted.resolve())

    with pytest.raises(BackgroundSpecError, match="approved root"):
        resolve_background({"id": "clear-knowledge"}, local_path=Path("C:/Windows/not-approved.png"), approved_root=tmp_path)


def test_background_rejects_missing_or_directory_source(tmp_path: Path) -> None:
    with pytest.raises(BackgroundSpecError, match="missing"):
        resolve_background({"id": "clear-knowledge"}, local_path=tmp_path / "missing.png", approved_root=tmp_path)
    directory = tmp_path / "folder"
    directory.mkdir()
    with pytest.raises(BackgroundSpecError, match="file"):
        resolve_background({"id": "clear-knowledge"}, local_path=directory, approved_root=tmp_path)


def test_mascot_defaults_off_for_new_style_packs() -> None:
    assert resolve_background({"id": "clear-knowledge"})["mascot"] is False
