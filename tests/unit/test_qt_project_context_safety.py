from __future__ import annotations

import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.gui_qt import QtWorkerBridge, VoxQtApp
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_select_placeholder_clears_active_project() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window)
    controller.project_id = "project-a"
    window.set_projects([], selected_id=None)

    controller._select_project(0)

    assert controller.project_id is None


def test_busy_reference_count_waits_for_all_workers() -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    bridge = QtWorkerBridge()
    slow_release = threading.Event()
    completed: list[str] = []
    bridge.succeeded.connect(lambda label, _result: completed.append(label))

    bridge.run("slow", lambda: slow_release.wait(2) or "slow")
    bridge.run("fast", lambda: "fast")

    deadline = 100
    while "fast" not in completed and deadline:
        app.processEvents()
        threading.Event().wait(0.01)
        deadline -= 1
    assert "fast" in completed
    assert bridge.active_count == 1

    slow_release.set()
    deadline = 100
    while "slow" not in completed and deadline:
        app.processEvents()
        threading.Event().wait(0.01)
        deadline -= 1
    assert bridge.active_count == 0
