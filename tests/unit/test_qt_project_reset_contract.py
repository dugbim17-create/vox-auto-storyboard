from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_clear_project_content_removes_all_project_bound_state() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    window.set_project_content(
        {"title": "A", "script_text": "one two"},
        [{"scene_id": "scene_001", "purpose": "hook", "narration_text": "one", "estimated_duration_seconds": 2}],
    )
    window.image_preview.setPixmap(QPixmap(8, 8))
    window.voice_result_list.addItem("voice")
    window.caption_table.setRowCount(1)
    window.set_render_state(progress=100, prerequisites="done", artifact="final.mp4")

    window.clear_project_content()

    assert window.topic_input.text() == ""
    assert window.script_editor.toPlainText() == ""
    assert window.scene_list.count() == 0
    assert window.visual_scene_list.count() == 0
    assert window.generated_asset_list.count() == 0
    assert window.image_preview.pixmap().isNull()
    assert window.voice_result_list.count() == 0
    assert window.caption_table.rowCount() == 0
    assert window.render_progress.value() == 0
    assert window.final_artifact_path.text() == "Chưa có final.mp4"
    assert window.saved_badge.text() == "Chưa tải project"
