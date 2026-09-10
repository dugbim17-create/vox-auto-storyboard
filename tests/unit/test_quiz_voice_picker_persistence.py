from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui_qt import VoxQtApp
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _document() -> dict:
    return {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Voice picker fixture",
        "language": "de-DE",
        "channel_profile": "de-football",
        "questions": [
            {
                "id": "q1",
                "question": "Welche Stadt liegt in Deutschland?",
                "choices": [
                    {"id": "A", "text": "München"},
                    {"id": "B", "text": "Paris"},
                    {"id": "C", "text": "Rom"},
                    {"id": "D", "text": "Madrid"},
                ],
                "correct_id": "A",
                "reveal_image_path": "fixture.png",
            }
        ],
        "settings": {"piper_voice": "de_DE-thorsten-high", "piper_speed": 1.12},
        "approval": {"status": "draft"},
    }


def test_picker_filters_exact_locale_and_persists_voice_and_speed(tmp_path: Path) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        controller.quiz_document = _document()
        window.set_quiz_document(controller.quiz_document)
        assert window.quiz_voice_combo.property("voice_locale") == "de-DE"
        assert window.quiz_voice_combo.property("voice_status") == "ready"
        assert window.quiz_voice_combo.currentData() == "de_DE-thorsten-high"
        assert window.quiz_voice_combo.findData("en_US-ryan-high") < 0
        window.quiz_output_dir.setText(str(tmp_path))
        window.quiz_speed_spin.setValue(1.24)
        saved = controller._save_quiz_draft_sync()
        assert saved["settings"]["piper_voice"] == "de_DE-thorsten-high"
        assert saved["settings"]["piper_locale"] == "de-DE"
        assert saved["settings"]["piper_speed"] == 1.24
    finally:
        window.close()


def test_picker_marks_japan_blocked_without_cross_locale_fallback() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        index = window.quiz_channel_combo.findData("locale-ja-JP")
        assert index >= 0
        window.quiz_channel_combo.setCurrentIndex(index)
        assert window.quiz_voice_combo.property("voice_locale") == "ja-JP"
        assert window.quiz_voice_combo.property("voice_status") == "blocked"
        assert window.quiz_voice_combo.currentData() == ""
        assert "Thiếu Piper exact-locale" in window.quiz_voice_combo.currentText()
    finally:
        window.close()


def test_locale_switch_replaces_old_voice_instead_of_retaining_it() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        de_index = window.quiz_channel_combo.findData("de-football")
        fr_index = window.quiz_channel_combo.findData("fr-culture")
        window.quiz_channel_combo.setCurrentIndex(de_index)
        assert window.quiz_voice_combo.currentData() == "de_DE-thorsten-high"
        window.quiz_channel_combo.setCurrentIndex(fr_index)
        assert window.quiz_voice_combo.currentData() == "fr_FR-siwis-medium"
        assert window.quiz_voice_combo.findData("de_DE-thorsten-high") < 0
    finally:
        window.close()
