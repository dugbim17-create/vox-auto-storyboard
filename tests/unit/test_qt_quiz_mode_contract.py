from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.gui_qt import VoxQtApp
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_quiz_mode_is_visible_additive_navigation_surface() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        assert "quiz" in window.nav_buttons
        window.show_page("quiz")
        assert window.page_stack.currentWidget() is window.quiz_page
        for name in (
            "QuizPage",
            "QuizFilePath",
            "LoadQuizButton",
            "QuizQuestionTable",
            "QuizPreview",
            "QuizOutputDir",
            "RenderQuizButton",
            "QuizProgress",
            "QuizStatus",
            "QuizArtifactPath",
        ):
            assert window.findChild(object, name) is not None, name
    finally:
        window.close()


def test_real_load_click_reviews_exact_30_questions_without_provider_calls(monkeypatch) -> None:
    app = _app()
    monkeypatch.setattr(VoxQtApp, "_load_projects", lambda self: None)
    monkeypatch.setattr(VoxQtApp, "_check_provider_health", lambda self: {"status": "skipped"})
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        window.show()
        window.show_page("quiz")
        window.quiz_file_path.setText("presets/quiz_30_vi_fixture.json")

        QTest.mouseClick(window.load_quiz_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        assert window.quiz_question_table.rowCount() == 30
        assert window.quiz_question_table.item(0, 0).text() == "1"
        assert "Thủ đô" in window.quiz_preview.toPlainText()
        assert "30 câu" in window.quiz_status.text()
        assert controller.quiz_document is not None
        assert controller.bridge.active_count == 0
    finally:
        window.close()


def test_real_load_click_reports_five_question_pilot_not_legacy_30(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app()
    monkeypatch.setattr(VoxQtApp, "_load_projects", lambda self: None)
    monkeypatch.setattr(
        VoxQtApp, "_check_provider_health", lambda self: {"status": "skipped"}
    )
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        raw = controller._research_quiz_sync(
            "Địa lý Việt Nam", Path("presets/quiz_5_vi_candidates_verified.json")
        )
        target = tmp_path / "approved.json"
        target.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        window.quiz_file_path.setText(str(target))
        QTest.mouseClick(window.load_quiz_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        assert window.quiz_question_table.rowCount() == 5
        assert "Pilot 5 câu đã được kiểm tra" in window.statusBar().currentMessage()
        assert "30 câu" not in window.statusBar().currentMessage()
        assert controller.quiz_document is not None
    finally:
        window.close()


def test_quiz_ui_wires_resumable_pilot_composer_and_never_live_tts() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        'nav_buttons["quiz"].clicked.connect',
        "load_quiz_button.clicked.connect",
        "render_quiz_button.clicked.connect",
        "QuizPilotLedger",
        "QuizPilotComposer",
        "pending pilot artifacts",
        'bridge.run("render_quiz"',
        'label == "render_quiz"',
    ):
        assert marker in source
    render_seam = source[source.index("def _render_quiz") : source.index("def _on_success")]
    assert "OmniVoice" not in render_seam
    assert "synthetic_sine" not in render_seam
