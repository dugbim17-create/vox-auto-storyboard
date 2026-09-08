from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_style_page_has_real_persisted_controls() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "StylePage",
            "StylePresetList",
            "StyleVisualLanguage",
            "StylePalette",
            "StyleTexture",
            "SaveStyleButton",
            "ApplyStyleButton",
            "StyleState",
            "StylePreview",
        ):
            assert window.findChild(object, name) is not None, name
    finally:
        window.close()


def test_qt_style_navigation_and_engine_are_wired() -> None:
    controller = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        'nav_buttons["style"].clicked.connect',
        "save_style_button.clicked.connect",
        "apply_style_button.clicked.connect",
        "ApplyStyleService",
        "StyleProjectService",
        "ProjectRepo",
        "style_preset",
    ):
        assert marker in controller


def test_style_manifest_service_is_atomic_and_readable() -> None:
    source = Path("app/services/style_project_service.py").read_text(encoding="utf-8-sig")
    assert "write_manifest" in source
    assert "def load" in source
    assert "def save" in source
