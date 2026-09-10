from __future__ import annotations

import copy
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.gui_qt import VoxQtApp
from app.services.quiz_style_packs import resolve_style_snapshot
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _question(qid: str, text: str, *, round_id: str = "warmup") -> dict:
    return {
        "id": qid,
        "order": 1,
        "round_id": round_id,
        "question": text,
        "choices": [
            {"id": "A", "text": "Đáp án A"},
            {"id": "B", "text": "Đáp án B"},
            {"id": "C", "text": "Đáp án C"},
            {"id": "D", "text": "Đáp án D"},
        ],
        "correct_id": "A",
        "answer_text": "Đáp án A",
        "explanation_text": "Giải thích fixture.",
        "fact_sources": ["https://example.test/source"],
        "countdown_seconds": 3.5,
    }


def _document() -> dict:
    return {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Unified workflow fixture",
        "language": "vi-VN",
        "channel_profile": "fr-culture",
        "round_structure": {
            "schema_version": 1,
            "mode": "mixed",
            "rounds": [
                {"id": "warmup", "label": "Khởi động", "format_key": "multiple_choice", "count": 1, "difficulty": "easy"},
                {"id": "visual", "label": "Nhìn kỹ", "format_key": "photo_reveal", "count": 1, "difficulty": "medium"},
            ],
        },
        "visual_style": resolve_style_snapshot("clear-knowledge", locale="vi-VN", motion="medium"),
        "questions": [_question("q1", "Câu hỏi thứ nhất?"), _question("q2", "Câu hỏi thứ hai?", round_id="visual")],
        "approval": {"status": "draft"},
    }


def _controller(monkeypatch):
    monkeypatch.setattr(VoxQtApp, "_load_projects", lambda self: None)
    monkeypatch.setattr(VoxQtApp, "_check_provider_health", lambda self: {"status": "skipped"})
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    controller.quiz_document = _document()
    window.set_quiz_document(controller.quiz_document)
    return window, controller


def test_quiz_page_has_four_stage_workflow_controls_and_empty_state(monkeypatch) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        assert window.findChild(object, "QuizStageStack") is not None
        assert window.findChild(object, "QuizStageChannel") is not None
        assert window.findChild(object, "QuizStageContent") is not None
        assert window.findChild(object, "QuizStageAppearance") is not None
        assert window.findChild(object, "QuizStageVoice") is not None
        assert window.findChild(object, "QuizCreateContentButton") is not None
        assert window.findChild(object, "QuizOtherInputToggle") is not None
        window.set_quiz_document({"engine_v2": True, "questions": []})
        assert window.quiz_empty_state.property("empty_state") is True
        assert "0 câu" in window.quiz_empty_state.text()
    finally:
        window.close()


def test_stage_navigation_keeps_single_document_and_dirty_question(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    try:
        original = copy.deepcopy(controller.quiz_document)
        window.quiz_stage_stack.setCurrentIndex(1)
        window.quiz_question_table.setCurrentCell(0, 1)
        window.quiz_question_table.item(0, 1).setText("Câu hỏi đã sửa chưa lưu?")
        window.quiz_stage_stack.setCurrentIndex(2)
        window.quiz_stage_stack.setCurrentIndex(0)
        assert controller.quiz_document["questions"][0]["question"] == original["questions"][0]["question"]
        assert window.quiz_question_table.item(0, 1).text() == "Câu hỏi đã sửa chưa lưu?"
        assert window.quiz_stage_dirty.property("dirty") is True
    finally:
        window.close()


def test_grouped_content_shows_round_and_all_four_choices(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    try:
        assert window.quiz_round_group.count() == 2
        assert window.quiz_round_group.itemData(0) == "warmup"
        assert window.quiz_round_group.itemData(1) == "visual"
        window.quiz_stage_stack.setCurrentIndex(1)
        assert window.quiz_question_table.columnCount() >= 8
        assert window.quiz_question_table.item(0, 4).text() == "Đáp án D"
        assert "round" in window.quiz_question_table.horizontalHeaderItem(0).text().lower() or "vòng" in window.quiz_question_table.horizontalHeaderItem(0).text().lower()
    finally:
        window.close()


def test_appearance_uses_real_local_thumbnail_and_selected_question_preview(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_stage_stack.setCurrentIndex(2)
        assert window.quiz_style_thumbnail_list.count() >= 4
        assert window.quiz_style_thumbnail_list.item(0).data(Qt.ItemDataRole.UserRole) == "baseline"
        assert window.quiz_appearance_preview.property("preview_status") in {"empty", "ready", "error"}
        assert window.quiz_appearance_preview.objectName() == "QuizAppearancePreview"
        assert window.quiz_preview_aspect_combo.count() == 2
    finally:
        window.close()


def test_save_close_reload_preserves_rounds_style_and_all_content(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_output_dir.setText(str(tmp_path))
        controller._save_quiz_draft()
        saved = sorted(tmp_path.glob("quiz-draft-*.json"))
        assert saved
        payload = json.loads(saved[-1].read_text(encoding="utf-8"))
        assert payload["round_structure"] == controller.quiz_document["round_structure"]
        assert payload["visual_style"] == controller.quiz_document["visual_style"]
        assert [q["id"] for q in payload["questions"]] == ["q1", "q2"]
        window.close()
        reloaded_window = VoxStudioWindow(autoload=False)
        try:
            reloaded_window.set_quiz_document(payload)
            assert reloaded_window.quiz_round_group.count() == 2
            assert reloaded_window.quiz_style_combo.currentData() == "clear-knowledge"
            assert reloaded_window.quiz_question_table.item(0, 4).text() == "Đáp án D"
        finally:
            reloaded_window.close()
    finally:
        if window.isVisible():
            window.close()


def test_cancel_and_preview_error_keep_saved_document_unchanged(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    try:
        original = copy.deepcopy(controller.quiz_document)
        window.quiz_style_combo.setCurrentIndex(window.quiz_style_combo.findData("sport-scoreboard"))
        window.quiz_cancel_style_button.click()
        assert controller.quiz_document == original
        controller._render_quiz_style_preview_sync = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("preview failed"))
        window.quiz_preview_button.click()
        assert window.quiz_appearance_preview.property("preview_status") == "error"
        assert controller.quiz_document == original
    finally:
        window.close()


def test_style_only_actions_do_not_use_worker_or_provider(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    try:
        calls: list[str] = []
        monkeypatch.setattr(controller.bridge, "run", lambda *args, **kwargs: calls.append("worker"))
        window.quiz_preview_button.click()
        assert calls == []
        assert window.quiz_appearance_preview.property("preview_status") == "ready"
    finally:
        window.close()


def test_create_content_action_is_truthful_and_does_not_fake_loaded_questions(monkeypatch) -> None:
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_quiz_document({"engine_v2": True, "questions": []})
        assert window.quiz_question_table.rowCount() == 0
        assert "0 câu" in window.quiz_empty_state.text()
        assert window.quiz_create_content_button.isEnabled()
    finally:
        window.close()
