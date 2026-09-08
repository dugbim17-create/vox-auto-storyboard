from __future__ import annotations

from pathlib import Path


def test_qt_entrypoint_exists_and_legacy_tk_is_not_default_target() -> None:
    launcher = Path("app/launcher.py").read_text(encoding="utf-8-sig")
    assert "from app.gui_qt import launch_qt" in launcher
    assert "launch_qt()" in launcher
    assert "from app.gui_native import launch_native" not in launcher


def test_qt_modules_are_declared_for_packaging() -> None:
    spec = Path("auto_storyboard.spec").read_text(encoding="utf-8-sig")
    for module in (
        "app.gui_qt",
        "app.ui_qt",
        "app.ui_qt.theme",
        "app.ui_qt.components",
        "app.ui_qt.main_window",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ):
        assert module in spec
