from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_project_content_updates_script_stats_from_real_data() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    window.set_project_content(
        {"title": "A", "script_text": "một hai ba bốn"},
        [
            {"scene_id": "s1", "purpose": "hook", "narration_text": "một", "estimated_duration_seconds": 2},
            {"scene_id": "s2", "purpose": "body", "narration_text": "hai", "estimated_duration_seconds": 3},
        ],
    )

    assert window.script_card.title_label.text() == "KỊCH BẢN · 2 CẢNH"
    assert window.scene_count_stat.value.text() == "2"
    assert window.duration_stat.value.text() == "00:05"
    assert window.word_count_stat.value.text() == "4"
    assert window.saved_badge.text() == "Đã tải"
