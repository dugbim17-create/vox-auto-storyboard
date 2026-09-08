from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_failed_image_outcome_cannot_be_reported_complete() -> None:
    from app.gui_qt import validate_image_generation_readback

    outcome = SimpleNamespace(
        ok=False,
        error="provider returned no image",
        generated=0,
        cached=0,
        selected_asset_id=None,
    )
    with pytest.raises(RuntimeError, match="provider returned no image"):
        validate_image_generation_readback(outcome, [])


def test_success_requires_selected_decodable_asset(tmp_path: Path) -> None:
    from PIL import Image

    from app.gui_qt import validate_image_generation_readback

    path = tmp_path / "selected.jpg"
    Image.new("RGB", (64, 36), "purple").save(path)
    outcome = SimpleNamespace(
        ok=True,
        error="",
        generated=1,
        cached=0,
        selected_asset_id="asset_selected",
    )
    asset = SimpleNamespace(
        asset_id="asset_selected",
        path=str(path),
        selected=True,
        width=64,
        height=36,
    )
    result = validate_image_generation_readback(outcome, [asset])
    assert result["selected_asset_id"] == "asset_selected"
    assert result["selected_path"] == str(path)
    assert result["width"] == 64
    assert result["height"] == 36


def test_image_service_selection_returns_persisted_asset_id(monkeypatch) -> None:
    from app.services.image_generation import ImageGenerationService
    from app.storage.repositories import AssetRepo, SceneRepo

    older = SimpleNamespace(
        id=1,
        asset_id="scene_001_composite_v001",
        role="composite",
        version=1,
        selected=False,
    )
    newest = SimpleNamespace(
        id=2,
        asset_id="scene_001_composite_v002",
        role="composite",
        version=2,
        selected=False,
    )
    monkeypatch.setattr(AssetRepo, "list", lambda *_args: [older, newest])
    monkeypatch.setattr(
        SceneRepo,
        "set_selected_image",
        lambda *_args: SimpleNamespace(selected_image_asset_id=newest.asset_id),
    )
    session = SimpleNamespace(commit=lambda: None)
    service = ImageGenerationService(SimpleNamespace(model="test"))
    selected = service._select_candidate(session, "project", "scene_001")
    assert selected == newest.asset_id
    assert newest.selected is True
    assert older.selected is False


def test_existing_selected_image_is_loaded_into_preview(tmp_path: Path) -> None:
    from PIL import Image

    from app.ui_qt.main_window import VoxStudioWindow

    _app()
    image_path = tmp_path / "preview.jpg"
    Image.new("RGB", (320, 180), "red").save(image_path)
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_visual_scene(
            {"scene_id": "scene_001", "image_prompt": "prompt"},
            [
                {
                    "id": 1,
                    "asset_id": "asset_1",
                    "role": "composite",
                    "path": str(image_path),
                    "provider": "test",
                    "version": 1,
                    "selected": True,
                }
            ],
        )
        assert window.generated_asset_list.count() == 1
        assert not window.image_preview.pixmap().isNull()
        assert window.image_preview.text() == ""
    finally:
        window.close()
