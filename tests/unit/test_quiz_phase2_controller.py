from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from test_quiz_phase1_contract import quiz_fixture

from app.gui_qt import VoxQtApp
from app.schemas.quiz import approve_quiz_project
from app.storage import database
from app.storage.repositories import QuizProjectRepo
from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _candidate_file(tmp_path: Path) -> Path:
    path = tmp_path / "candidates.json"
    questions = quiz_fixture(8)["questions"]
    for question in questions:
        question["fact_sources"][0]["authority"] = "official"
    path.write_text(json.dumps({"questions": questions}, ensure_ascii=False), encoding="utf-8")
    return path


def test_research_persists_five_question_draft_and_reopens(tmp_path: Path) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    path = _candidate_file(tmp_path)
    try:
        first = controller._research_quiz_sync("Địa lý Việt Nam", path)
        second = controller._research_quiz_sync("Địa lý Việt Nam", path)

        assert first["project_id"] == second["project_id"]
        assert first["questions"] == second["questions"]
        assert first["approval"]["status"] == "draft"
        assert len(first["questions"]) == 5
        with database.create_session() as session:
            stored = QuizProjectRepo.get_document(session, first["project_id"])
        assert stored == first
    finally:
        window.close()


def test_save_draft_reads_edits_and_persists(tmp_path: Path) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        document = controller._research_quiz_sync("Địa lý Việt Nam", _candidate_file(tmp_path))
        controller.quiz_document = document
        window.set_quiz_document(document)
        window.quiz_question_table.item(0, 1).setText("Câu đã chỉnh trong UI?")

        saved = controller._save_quiz_draft_sync()

        assert saved["questions"][0]["question"] == "Câu đã chỉnh trong UI?"
        assert saved["approval"]["status"] == "draft"
        with database.create_session() as session:
            assert QuizProjectRepo.get_document(session, saved["project_id"]) == saved
    finally:
        window.close()


def test_approve_persists_fingerprint_and_readback(tmp_path: Path) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        document = controller._research_quiz_sync("Địa lý Việt Nam", _candidate_file(tmp_path))
        controller.quiz_document = document
        window.set_quiz_document(document)

        approved = controller._approve_quiz_sync(approved_at="2026-08-10T00:00:00Z")

        fingerprint = approved["approval"]["content_fingerprint"]
        assert approved["approval"]["status"] == "approved"
        assert len(fingerprint) == 64
        with database.create_session() as session:
            reloaded = QuizProjectRepo.get_document(session, approved["project_id"])
        assert reloaded["approval"]["content_fingerprint"] == fingerprint
    finally:
        window.close()


def test_phase2_buttons_are_wired() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8")

    assert "research_quiz_button.clicked.connect(self._research_quiz)" in source
    assert "save_quiz_draft_button.clicked.connect(self._save_quiz_draft)" in source
    assert "approve_quiz_button.clicked.connect(self._approve_quiz)" in source


def test_research_success_populates_review_ui(tmp_path: Path) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        payload = controller._research_quiz_sync("Địa lý Việt Nam", _candidate_file(tmp_path))

        controller._on_success("research_quiz", payload)

        assert controller.quiz_document == payload
        assert window.quiz_question_table.rowCount() == 5
        assert "5 câu" in window.quiz_status.text()
    finally:
        window.close()


def _make_dummy_pilot_artifacts(
    output: Path,
    item_ids: list[str],
    fingerprint: str,
    topic: str = "Địa lý Việt Nam",
) -> None:
    import hashlib
    import subprocess

    output.mkdir(parents=True, exist_ok=True)
    dummy = output / "_source_clip.mp4"
    if not dummy.is_file():
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1280x720:rate=30",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            "0.1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-shortest",
            str(dummy),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    dummy_bytes = dummy.read_bytes()
    dummy_size = len(dummy_bytes)
    dummy_sha = hashlib.sha256(dummy_bytes).hexdigest()

    items = []
    for item_id in item_ids:
        clip_path = output / f"{item_id}.mp4"
        clip_path.write_bytes(dummy_bytes)
        items.append(
            {
                "item_id": item_id,
                "path": str(clip_path.resolve()),
                "status": "validated",
                "bytes": dummy_size,
                "sha256": dummy_sha,
                "probe": {
                    "duration_ms": 100,
                    "fps": 30.0,
                    "width": 1280,
                    "height": 720,
                    "pix_fmt": "yuv420p",
                    "has_audio": True,
                },
            }
        )
    question_ids = [i for i in item_ids if i not in ("intro", "outro")]
    ledger = {
        "schema_version": "quiz_pilot_ledger_v1",
        "topic": topic,
        "content_fingerprint": fingerprint,
        "question_ids": question_ids,
        "items": items,
    }
    (output / "pilot-ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_approved_pilot_render_reuses_validated_artifacts_without_tts(tmp_path: Path) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    output = tmp_path / "pilot"
    try:
        document = controller._research_quiz_sync(
            "Địa lý Việt Nam", Path("presets/quiz_5_vi_candidates_verified.json")
        )
        controller.quiz_document = document
        window.set_quiz_document(document)
        approved = controller._approve_quiz_sync(approved_at="2026-08-10T00:00:00Z")
        controller.quiz_document = approved
        window.set_quiz_document(approved)
        fp = approved["approval"]["content_fingerprint"]
        _make_dummy_pilot_artifacts(
            output, ["intro", "q001", "q002", "q003", "q004", "q005", "outro"], fp
        )
        window.quiz_output_dir.setText(str(output))
        result = controller._render_quiz_sync()
        assert Path(result["final_mp4"]).is_file()
        assert result["question_count"] == 5
        assert result["provider_calls"] == 0
        assert result["tts_calls"] == 0
        assert result["pending_items"] == []
    finally:
        window.close()


def test_pilot_render_fails_closed_when_validated_artifact_is_missing(tmp_path: Path) -> None:
    import pytest
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    output = tmp_path / "pilot"
    try:
        document = controller._research_quiz_sync(
            "Địa lý Việt Nam", Path("presets/quiz_5_vi_candidates_verified.json")
        )
        controller.quiz_document = document
        window.set_quiz_document(document)
        controller.quiz_document = controller._approve_quiz_sync(
            approved_at="2026-08-10T00:00:00Z"
        )
        window.set_quiz_document(controller.quiz_document)
        fp = controller.quiz_document["approval"]["content_fingerprint"]
        _make_dummy_pilot_artifacts(
            output, ["intro", "q001", "q002", "q003", "q004", "q005", "outro"], fp
        )
        (output / "q003.mp4").unlink()
        window.quiz_output_dir.setText(str(output))
        with pytest.raises(RuntimeError, match="pending pilot artifacts"):
            controller._render_quiz_sync()
    finally:
        window.close()


def test_approved_scale_render_composes_thirty_validated_units_without_tts(
    tmp_path: Path,
) -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    output = tmp_path / "scale-30"
    try:
        raw = json.loads(Path("presets/quiz_30_vi_fixture.json").read_text(encoding="utf-8"))
        approved = approve_quiz_project(raw, approved_at="2026-08-10T00:00:00Z")
        controller.quiz_document = approved
        window.set_quiz_document(approved)
        fp = approved["approval"]["content_fingerprint"]
        q_ids = [f"q{i:03d}" for i in range(1, 31)]
        _make_dummy_pilot_artifacts(
            output,
            ["intro", *q_ids, "outro"],
            fp,
            topic=approved.get("topic") or approved.get("title") or "Kiến thức",
        )
        window.quiz_output_dir.setText(str(output))

        result = controller._render_quiz_sync()

        assert Path(result["final_mp4"]).is_file()
        assert result["question_count"] == 30
        assert result["provider_calls"] == 0
        assert result["tts_calls"] == 0
        assert result["pending_items"] == []
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        assert manifest["question_ids"] == [f"q{i:03d}" for i in range(1, 31)]
    finally:
        window.close()


def test_scale_render_callbacks_keep_thirty_question_identity() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    controller = VoxQtApp(window, start_provider_health=False)
    try:
        raw = json.loads(
            Path("presets/quiz_30_vi_fixture.json").read_text(encoding="utf-8")
        )
        approved = approve_quiz_project(raw, approved_at="2026-08-10T00:00:00Z")
        controller.quiz_document = approved
        window.set_quiz_document(approved)

        controller._on_success(
            "render_quiz",
            {"question_count": 30, "final_mp4": "final-30.mp4"},
        )
        assert "30 câu hoàn tất" in window.statusBar().currentMessage()

        controller._on_failure("render_quiz", "fixture failure")
        assert window.render_quiz_button.isEnabled() is True
        assert "30 câu lỗi" in window.quiz_status.text()
    finally:
        window.close()
