from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_window_exposes_real_project_and_script_actions() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "OpenProjectButton",
            "SaveScriptButton",
            "CreateStoryboardButton",
            "RegenerateStoryboardButton",
        ):
            assert window.findChild(object, name) is not None, name
        assert window.script_editor is not None
        assert window.script_editor.isReadOnly() is False
    finally:
        window.close()


def test_qt_controller_wires_all_script_controls() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        "project_selector.currentIndexChanged.connect",
        "open_project_button.clicked.connect",
        "save_script_button.clicked.connect",
        "create_storyboard_button.clicked.connect",
        "regenerate_storyboard_button.clicked.connect",
        "def _load_projects",
        "def _load_project",
        "def _save_script",
        "def _refresh_project_view",
    ):
        assert marker in source


def test_qt_project_read_model_contains_persisted_scenes_not_demo_rows() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "ProjectRepo.list" in source
    assert "SceneRepo.list" in source
    assert "script_text" in source
    assert "SCENES" not in Path("app/ui_qt/main_window.py").read_text(encoding="utf-8-sig")


def test_qt_busy_state_locks_primary_actions() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "def _set_busy" in source
    assert "setEnabled(not busy)" in source
    assert "finally" in source or "_on_failure" in source
