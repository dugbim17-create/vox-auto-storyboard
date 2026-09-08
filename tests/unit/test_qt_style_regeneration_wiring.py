from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_style_regeneration_buttons_are_wired_to_real_controller_actions() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "regenerate_style_scene_button.clicked.connect" in source
    assert "regenerate_all_style_images_button.clicked.connect" in source
    assert "def _regenerate_style_scene" in source
    assert "def _regenerate_all_style_images" in source
    assert "generate_style_all_images" in source


def test_bulk_button_is_disabled_while_running_and_can_be_restored() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_style_regeneration_running(True, current=2, total=5)
        assert window.regenerate_all_style_images_button.isEnabled() is False
        assert "2/5" in window.regenerate_all_style_images_button.text()
        window.set_style_regeneration_running(False)
        assert window.regenerate_all_style_images_button.isEnabled() is True
    finally:
        window.close()


def test_bulk_confirmation_copy_contains_exact_call_budget() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        assert "20 provider calls" in window.style_regeneration_confirmation_text(
            scene_count=4,
            role_count=5,
        )
        assert "chạy tuần tự" in window.style_regeneration_confirmation_text(
            scene_count=4,
            role_count=5,
        ).lower()
    finally:
        window.close()
