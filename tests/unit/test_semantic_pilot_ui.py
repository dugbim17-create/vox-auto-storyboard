from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui_qt import VoxQtApp
from app.ui_qt.main_window import VoxStudioWindow


def test_acceptance_page_exposes_provider_free_semantic_pilot_controls() -> None:
    app = QApplication.instance() or QApplication([])
    window = VoxStudioWindow(autoload=False)
    try:
        assert window.render_semantic_pilot_button.text() == "Render semantic pilot · 0 provider calls"
        assert window.semantic_pilot_status.text() == "Chưa render semantic candidate"
        assert not window.open_semantic_pilot_button.isEnabled()
        assert window.semantic_pilot_artifact.text() == "Chưa có artifact"
    finally:
        window.close()
        app.processEvents()


def test_gui_controller_reads_back_real_semantic_artifact(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    result = VoxQtApp._render_semantic_pilot_sync(tmp_path)

    assert result["provider_calls"] == 0
    assert Path(result["final_mp4"]).is_file()
    assert len(result["final_sha256"]) == 64
    app.processEvents()
