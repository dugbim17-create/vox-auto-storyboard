from __future__ import annotations

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


def _document(style_id: str = "clear-knowledge") -> dict:
    return {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Preview fixture",
        "language": "en-US",
        "channel_profile": "de-wissen",
        "visual_style": resolve_style_snapshot(style_id, locale="en-US", motion="medium"),
        "questions": [
            {
                "id": "q1",
                "question": "Which explanation fits?",
                "choices": [
                    {"id": "A", "text": "Magnetic heading"},
                    {"id": "B", "text": "Opening year"},
                ],
                "correct_id": "A",
                "answer_text": "Magnetic heading",
            }
        ],
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


def test_quiz_page_exposes_style_motion_baseline_preview_controls() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "QuizStyleCombo",
            "QuizMotionCombo",
            "QuizPreviewStateCombo",
            "QuizPreviewAspectCombo",
            "QuizPreviewButton",
            "QuizCancelStyleButton",
            "QuizPreviewImage",
        ):
            assert window.findChild(object, name) is not None, name
        assert window.quiz_style_combo.count() >= 4
        assert window.quiz_style_combo.itemData(0) == ""
        assert set(window.quiz_motion_combo.itemData(i) for i in range(window.quiz_motion_combo.count())) == {"low", "medium", "high"}
    finally:
        window.close()


def test_style_preview_uses_unsaved_values_and_does_not_call_provider(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    calls: list[str] = []
    original = controller._render_quiz_style_preview_sync

    def guarded(**kwargs):
        calls.append("preview")
        return original(**kwargs)

    monkeypatch.setattr(controller, "_render_quiz_style_preview_sync", guarded)
    try:
        window.quiz_style_combo.setCurrentIndex(window.quiz_style_combo.findData("editorial-culture"))
        window.quiz_motion_combo.setCurrentIndex(window.quiz_motion_combo.findData("low"))
        window.quiz_preview_state_combo.setCurrentIndex(window.quiz_preview_state_combo.findData("reveal"))
        window.quiz_preview_aspect_combo.setCurrentIndex(window.quiz_preview_aspect_combo.findData("9:16"))
        QTest.mouseClick(window.quiz_preview_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert calls == ["preview"]
        assert window.quiz_preview_image.property("preview_status") == "ready"
        assert not window.quiz_preview_image.pixmap().isNull()
        assert window.quiz_preview_image.pixmap().width() > 0
        assert controller.quiz_document["visual_style"]["id"] == "clear-knowledge"
        assert controller.quiz_document["visual_style"]["motion"] == "medium"
    finally:
        window.close()


def test_preview_failure_marks_stale_and_does_not_keep_old_current_image(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    try:
        controller._render_quiz_style_preview_sync = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("fixture failure"))
        QTest.mouseClick(window.quiz_preview_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert window.quiz_preview_image.property("preview_status") == "error"
        assert "fixture failure" in window.quiz_style_preview_status.text()
        assert window.quiz_preview_image.pixmap().isNull()
    finally:
        window.close()


def test_cancel_style_preview_leaves_document_unchanged(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    original = json.loads(json.dumps(controller.quiz_document, ensure_ascii=False))
    try:
        window.quiz_style_combo.setCurrentIndex(window.quiz_style_combo.findData("sport-scoreboard"))
        window.quiz_motion_combo.setCurrentIndex(window.quiz_motion_combo.findData("high"))
        QTest.mouseClick(window.quiz_cancel_style_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert controller.quiz_document == original
        assert window.quiz_style_combo.currentData() == original["visual_style"]["id"]
        assert window.quiz_motion_combo.currentData() == original["visual_style"]["motion"]
    finally:
        window.close()


def test_save_style_preview_roundtrips_snapshot_without_provider(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_output_dir.setText(str(tmp_path))
        window.quiz_style_combo.setCurrentIndex(window.quiz_style_combo.findData("sport-scoreboard"))
        window.quiz_motion_combo.setCurrentIndex(window.quiz_motion_combo.findData("high"))
        QTest.mouseClick(window.quiz_save_style_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert controller.quiz_document["visual_style"]["id"] == "sport-scoreboard"
        assert controller.quiz_document["visual_style"]["motion"] == "high"
        saved = sorted(tmp_path.glob("quiz-draft-*.json"))
        assert saved
        payload = json.loads(saved[-1].read_text(encoding="utf-8"))
        assert payload["visual_style"]["id"] == "sport-scoreboard"
        assert payload["visual_style"]["motion"] == "high"
    finally:
        window.close()


def test_reopen_restores_saved_style_controls_and_exact_preview(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_output_dir.setText(str(tmp_path))
        window.quiz_style_combo.setCurrentIndex(window.quiz_style_combo.findData("editorial-culture"))
        window.quiz_motion_combo.setCurrentIndex(window.quiz_motion_combo.findData("high"))
        QTest.mouseClick(window.quiz_save_style_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        saved = sorted(tmp_path.glob("quiz-draft-*.json"))[-1]
        reloaded = json.loads(saved.read_text(encoding="utf-8"))
        window.set_quiz_document(reloaded)
        assert window.quiz_style_combo.currentData() == "editorial-culture"
        assert window.quiz_motion_combo.currentData() == "high"
        QTest.mouseClick(window.quiz_preview_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert window.quiz_preview_image.property("preview_status") == "ready"
    finally:
        window.close()


def test_style_only_preview_does_not_start_worker_or_provider(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    try:
        calls: list[str] = []
        monkeypatch.setattr(controller.bridge, "run", lambda *args, **kwargs: calls.append("worker"))
        original_preview = controller._render_quiz_style_preview_sync

        def guarded(**kwargs):
            calls.append("render")
            return original_preview(**kwargs)

        monkeypatch.setattr(controller, "_render_quiz_style_preview_sync", guarded)
        window.quiz_style_combo.setCurrentIndex(window.quiz_style_combo.findData("clear-knowledge"))
        QTest.mouseClick(window.quiz_preview_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert calls == ["render"]
        assert window.quiz_preview_image.property("preview_status") == "ready"
    finally:
        window.close()


def test_baseline_selection_removes_style_snapshot_on_save(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_output_dir.setText(str(tmp_path))
        window.quiz_style_combo.setCurrentIndex(0)
        QTest.mouseClick(window.quiz_save_style_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert "visual_style" not in controller.quiz_document
        saved = sorted(tmp_path.glob("quiz-draft-*.json"))
        assert saved
        payload = json.loads(saved[-1].read_text(encoding="utf-8"))
        assert "visual_style" not in payload
    finally:
        window.close()


def test_style_preview_uses_current_first_question_without_persisting_preview(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_output_dir.setText(str(tmp_path))
        controller.quiz_document["questions"][0]["question"] = "A current first question?"
        QTest.mouseClick(window.quiz_preview_button, Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert window.quiz_preview_image.property("preview_status") == "ready"
        assert not list(tmp_path.glob("quiz-draft-*.json"))
    finally:
        window.close()


def test_style_preview_uses_production_engine_dispatch(monkeypatch) -> None:
    window, controller = _controller(monkeypatch)
    calls: list[str] = []
    from app.services.quiz_engine_v2 import QuizVideoEngineV2

    original = QuizVideoEngineV2._render_question_card

    def guarded(self, *args, **kwargs):
        calls.append("production-dispatch")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(QuizVideoEngineV2, "_render_question_card", guarded)
    try:
        controller._render_quiz_style_preview_sync(
            document=controller._style_preview_document(),
            aspect="16:9",
            state="question",
        )
        assert calls == ["production-dispatch"]
    finally:
        window.close()


def test_style_preview_writes_non_overwriting_identity_path(monkeypatch, tmp_path: Path) -> None:
    window, controller = _controller(monkeypatch)
    try:
        window.quiz_output_dir.setText(str(tmp_path))
        first = controller._render_quiz_style_preview_sync(
            document=controller._style_preview_document(),
            aspect="16:9",
            state="question",
        )
        second = controller._render_quiz_style_preview_sync(
            document=controller._style_preview_document(),
            aspect="16:9",
            state="question",
        )
        assert first["path"] != second["path"]
        assert Path(first["path"]).is_file()
        assert Path(second["path"]).is_file()
        assert "clear-knowledge" in Path(first["path"]).name
        assert "medium" in Path(first["path"]).name
    finally:
        window.close()
