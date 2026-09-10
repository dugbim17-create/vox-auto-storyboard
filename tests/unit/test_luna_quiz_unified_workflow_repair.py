from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from app.gui_qt import VoxQtApp
from app.services.quiz_style_packs import resolve_style_snapshot
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _question(qid: str, text: str) -> dict:
    return {
        "id": qid,
        "order": 1 if qid == "q1" else 2,
        "round_id": "warmup" if qid == "q1" else "visual",
        "format_key": "multiple_choice",
        "question": text,
        "choices": [
            {"id": "A", "text": "Đáp án A"},
            {"id": "B", "text": "Đáp án B"},
            {"id": "C", "text": "Đáp án C"},
            {"id": "D", "text": "Đáp án D"},
        ],
        "correct_id": "A",
        "answer_text": "Đáp án A",
        "explanation_text": "Giải thích không được tự ý xóa.",
        "fact_sources": ["https://example.test/source"],
        "approval_status": "draft",
    }


def _document() -> dict:
    return {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Repair fixture",
        "language": "vi-VN",
        "channel_profile": "fr-culture",
        "round_structure": {
            "schema_version": 1,
            "mode": "mixed",
            "rounds": [
                {
                    "id": "warmup",
                    "label": "Khởi động",
                    "format_key": "multiple_choice",
                    "count": 1,
                    "difficulty": "easy",
                },
                {
                    "id": "visual",
                    "label": "Nhìn kỹ",
                    "format_key": "photo_reveal",
                    "count": 1,
                    "difficulty": "medium",
                },
            ],
        },
        "visual_style": resolve_style_snapshot("clear-knowledge", locale="vi-VN", motion="medium"),
        "questions": [_question("q1", "Câu hỏi thứ nhất?"), _question("q2", "Câu hỏi thứ hai?")],
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


def test_preview_overlap_surfaces_error_without_dropping_explanation() -> None:
    # The production path has no content-dropping retry; exercise its seam
    # without opening a modal or relying on the flaky Windows Qt test runner.
    from app.gui_qt import VoxQtApp
    from app.services.quiz_engine_v2 import QuizVideoEngineV2

    controller = object.__new__(VoxQtApp)
    controller.window = type("Window", (), {})()
    controller.quiz_document = _document()
    controller.window.quiz_question_table = type("Table", (), {"currentRow": lambda self: 0})()
    controller.window.quiz_output_dir = type("Output", (), {"text": lambda self: "output/quiz-unified-workflow/test"})()
    controller.window.quiz_style_combo = type("Combo", (), {"currentData": lambda self: "clear-knowledge"})()
    controller.window.quiz_motion_combo = type("Combo", (), {"currentData": lambda self: "medium"})()
    controller.window.quiz_preview_aspect_combo = type("Combo", (), {"currentData": lambda self: "16:9"})()
    controller.window.quiz_preview_state_combo = type("Combo", (), {"currentData": lambda self: "question"})()
    original = QuizVideoEngineV2._render_question_card
    seen: list[dict] = []
    def fail_without_fallback(self, canvas, draw, time_value, event):
        seen.append(event["data"])
        raise ValueError("layout overlap: fixture")
    try:
        QuizVideoEngineV2._render_question_card = fail_without_fallback
        payload = controller._style_preview_document()
        try:
            controller._render_quiz_style_preview_sync(document=payload, aspect="16:9", state="question")
        except ValueError as exc:
            assert "layout overlap" in str(exc)
        else:
            raise AssertionError("layout overlap must be surfaced")
        assert seen and "explanation_text" in seen[0]
        assert controller.quiz_document["questions"][0]["explanation_text"]
    finally:
        QuizVideoEngineV2._render_question_card = original

def test_primary_create_action_passes_real_episode_context(monkeypatch) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    captured: dict = {}

    class FakeDialog:
        def __init__(self, parent=None):
            captured["created"] = True
            self.ai_prompt_input = type(
                "Field",
                (),
                {"setText": lambda self, value: captured.__setitem__("topic", value)},
            )()
            self.ai_count_spin = type(
                "Spin",
                (),
                {"setValue": lambda self, value: captured.__setitem__("count", value)},
            )()
            self.series_input = type(
                "Field",
                (),
                {"setText": lambda self, value: captured.__setitem__("series", value)},
            )()
            self.difficulty_input = type(
                "Combo",
                (),
                {"setCurrentText": lambda self, value: captured.__setitem__("difficulty", value)},
            )()
            self.minutes_input = type(
                "Spin",
                (),
                {"setValue": lambda self, value: captured.__setitem__("minutes", value)},
            )()
            self.channel_profile = ""
            self.episode_context = None
            self.parsed_document = None

        def exec(self):
            captured["context"] = self.episode_context
            return 0

    monkeypatch.setattr("app.ui_qt.quiz_json_dialog.QuizJsonDialog", FakeDialog)
    try:
        window.quiz_topic_input.setText("Địa lý Việt Nam")
        window.quiz_round_count.setValue(6)
        window.quiz_structure_combo.setCurrentIndex(window.quiz_structure_combo.findData("mixed"))
        window.quiz_channel_combo.setCurrentIndex(window.quiz_channel_combo.findData("fr-culture"))
        controller._create_quiz_content()
        assert captured["created"] is True
        assert captured["topic"] == "Địa lý Việt Nam"
        assert captured["count"] == 6
        assert captured["context"]["structure_mode"] == "mixed"
        assert sum(item["count"] for item in captured["context"]["round_structure"]["rounds"]) == 6
    finally:
        window.close()


def test_four_stages_contain_one_canonical_workflow_and_real_thumbnails() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        assert window.quiz_stage_stack.count() == 4
        assert window.quiz_stage_panels[0].findChild(type(window.quiz_topic_input)) is not None
        assert window.quiz_stage_panels[1].findChild(QTableWidget, "QuizQuestionTable") is window.quiz_question_table
        assert window.quiz_page.findChildren(QTableWidget, "QuizQuestionTable") == [window.quiz_question_table]
        assert window.quiz_style_thumbnail_list.property("thumbnail_source") == "production-engine-local"
        assert window.quiz_style_thumbnail_list.count() == 4
        for row in range(window.quiz_style_thumbnail_list.count()):
            item = window.quiz_style_thumbnail_list.item(row)
            assert item.icon().isNull() is False
            assert item.data(Qt.ItemDataRole.UserRole)
    finally:
        window.close()


def test_selected_question_drives_preview_without_mutating_other_questions(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    captured: list[str] = []
    try:
        from app.services.quiz_engine_v2 import QuizVideoEngineV2

        def fake_render(self, canvas, draw, time_value, event):
            captured.append(str(event["data"]["id"]))
            return canvas

        monkeypatch.setattr(QuizVideoEngineV2, "_render_question_card", fake_render)
        window.quiz_output_dir.setText(str(tmp_path))
        window.quiz_question_table.setCurrentCell(1, 2)
        controller._render_quiz_style_preview_sync(
            document=controller._style_preview_document(),
            aspect="16:9",
            state="question",
        )
        assert captured[-1] == "q2"
        assert controller.quiz_document["questions"][0]["question"] == "Câu hỏi thứ nhất?"
    finally:
        window.close()


def test_local_thumbnail_is_decodable_png() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        item = window.quiz_style_thumbnail_list.item(0)
        pixmap = item.icon().pixmap(160, 90)
        assert not pixmap.isNull()
        image = pixmap.toImage()
        assert image.width() > 0 and image.height() > 0
    finally:
        window.close()
