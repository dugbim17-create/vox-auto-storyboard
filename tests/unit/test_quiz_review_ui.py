from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from test_quiz_phase1_contract import quiz_fixture

from app.schemas.quiz import approve_quiz_project
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_quiz_review_page_exposes_phase2_controls() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        assert window.quiz_topic_input.objectName() == "QuizTopicInput"
        assert window.research_quiz_button.text() == "Tạo pilot 5 câu"
        assert window.save_quiz_draft_button.text() == "Lưu nháp"
        assert window.approve_quiz_button.text() == "Duyệt 5 câu"
        assert window.quiz_approval_fingerprint.objectName() == "QuizApprovalFingerprint"
        assert window.quiz_question_table.columnCount() == 8
        assert window.quiz_question_table.horizontalHeaderItem(1).text() == "Câu hỏi"
        assert window.quiz_question_table.horizontalHeaderItem(6).text() == "Nguồn"
        assert window.nav_buttons["quiz"].text().endswith("Quiz")
    finally:
        window.close()


def test_five_question_draft_is_editable_but_not_renderable() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        document = quiz_fixture()
        window.set_quiz_document(document)

        assert window.quiz_question_table.rowCount() == 5
        assert window.render_quiz_button.isEnabled() is False
        assert "Câu 1/5" in window.quiz_preview.toPlainText()
        item = window.quiz_question_table.item(0, 1)
        assert item.flags() & Qt.ItemFlag.ItemIsEditable
        item.setText("Câu hỏi đã sửa?")
        window.quiz_question_table.item(0, 2).setText("Phương án A mới")
        window.quiz_question_table.item(0, 5).setText("A")
        window.quiz_question_table.item(0, 6).setText("https://official.test/new")

        edited = window.read_quiz_review(document)

        assert edited["questions"][0]["question"] == "Câu hỏi đã sửa?"
        assert edited["questions"][0]["choices"][0]["text"] == "Phương án A mới"
        assert edited["questions"][0]["correct_choice_id"] == "A"
        assert edited["questions"][0]["answer_text"] == "Phương án A mới"
        assert edited["questions"][0]["fact_sources"][0]["url"] == "https://official.test/new"
    finally:
        window.close()


def test_approved_five_question_document_enables_pilot_render() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        approved = approve_quiz_project(
            quiz_fixture(), approved_at="2026-08-10T00:00:00Z"
        )

        window.set_quiz_document(approved)

        assert window.render_quiz_button.isEnabled() is True
        assert window.render_quiz_button.text() == "Render pilot 5 câu"
        assert window.quiz_output_dir.text() == "output/quiz-pilot-5"
    finally:
        window.close()


def test_edit_invalidates_prior_approval_in_review_readback() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        approved = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")
        window.set_quiz_document(approved)
        window.quiz_question_table.item(0, 1).setText("Nội dung đã thay đổi?")

        edited = window.read_quiz_review(approved)

        assert edited["approval"] == {
            "status": "draft",
            "approved_at": None,
            "content_fingerprint": None,
        }
        assert edited["questions"][0]["approval_status"] == "draft"
        assert edited["questions"][0]["content_fingerprint"] is None
    finally:
        window.close()


def test_approved_thirty_question_document_enables_scale_render() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        raw = json.loads(
            Path("presets/quiz_30_vi_fixture.json").read_text(encoding="utf-8")
        )
        approved = approve_quiz_project(raw, approved_at="2026-08-10T00:00:00Z")
        window.set_quiz_document(approved)

        assert window.quiz_question_table.rowCount() == 30
        assert window.render_quiz_button.isEnabled() is True
        assert window.render_quiz_button.text() == "Render bản 30 câu"
        assert window.quiz_output_dir.text() == "output/quiz-30"
        assert window.quiz_review_card.title_label.text() == "QUIZ MODE · BẢN 30 CÂU"
        assert window.approve_quiz_button.text() == "Duyệt 30 câu"
    finally:
        window.close()
