"""Offline readback evidence for the unified Quiz workflow.

This intentionally captures widget state instead of invoking provider/TTS/video
work. Native screenshots are produced by the sibling capture helper once the
window is shown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.gui_qt import VoxQtApp
from app.services.quiz_style_packs import resolve_style_snapshot
from app.services.quiz_unified_workflow import (
    mark_workflow_dirty,
    normalize_quiz_workflow_document,
    preserve_regeneration_context,
    replace_one_question,
    update_workflow_stage,
    workflow_readiness,
)
from app.ui_qt.main_window import VoxStudioWindow


def _question(qid: str, order: int, round_id: str) -> dict:
    return {
        "id": qid,
        "order": order,
        "round_id": round_id,
        "format_key": "multiple_choice" if round_id == "warmup" else "photo_reveal",
        "question": f"Câu hỏi {order}?",
        "choices": [
            {"id": "A", "text": "Phương án A"},
            {"id": "B", "text": "Phương án B"},
            {"id": "C", "text": "Phương án C"},
            {"id": "D", "text": "Phương án D"},
        ],
        "correct_id": "A",
        "answer_text": "Phương án A",
        "explanation_text": "Giải thích fixture.",
        "fact_sources": ["https://example.test/source"],
    }


def document() -> dict:
    return {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Unified workflow evidence",
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
        "questions": [_question("q1", 1, "warmup"), _question("q2", 2, "visual")],
        "approval": {"status": "draft"},
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture_widget_state(window: VoxStudioWindow, stage: int) -> dict:
    window.quiz_stage_stack.setCurrentIndex(stage)
    return {
        "stage": stage + 1,
        "current_index": window.quiz_stage_stack.currentIndex(),
        "stage_names": [window.quiz_stage_stack.widget(i).objectName() for i in range(window.quiz_stage_stack.count())],
        "round_count": window.quiz_round_group.count(),
        "question_count": window.quiz_question_table.rowCount(),
        "style_count": window.quiz_style_thumbnail_list.count(),
        "style_ids": [
            str(window.quiz_style_thumbnail_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(window.quiz_style_thumbnail_list.count())
        ],
        "empty_state": bool(window.quiz_empty_state.property("empty_state")),
        "dirty": bool(window.quiz_stage_dirty.property("dirty")),
        "preview_status": str(window.quiz_appearance_preview.property("preview_status")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="output/quiz-unified-workflow")
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    out = (PROJECT_ROOT / args.output_root / args.run).resolve()
    out.mkdir(parents=True, exist_ok=False)

    source = document()
    normalized = normalize_quiz_workflow_document(source)
    dirty = mark_workflow_dirty(source)
    staged = update_workflow_stage(source, "appearance")
    context = preserve_regeneration_context(source, "q2")
    replaced = replace_one_question(source, "q2", {"question": "Câu hỏi mới?"})

    app = QApplication.instance() or QApplication([])
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_quiz_document(source)
        stages = [capture_widget_state(window, stage) for stage in range(4)]
        window.quiz_question_table.item(0, 2).setText("Câu hỏi dirty")
        window.mark_quiz_stage_dirty()
        dirty_stage = capture_widget_state(window, 1)
    finally:
        window.close()

    payload = {
        "run_id": args.run,
        "fixture_origin": "local in-memory fixture; no provider/TTS/video",
        "stages": stages,
        "dirty_stage": dirty_stage,
        "round_structure_preserved": normalized["round_structure"] == source["round_structure"],
        "source_untouched": source.get("workflow") is None,
        "workflow_stage": staged["workflow"]["stage"],
        "regeneration_context": context,
        "replaced_question_id": replaced["questions"][1]["id"],
        "other_question_preserved": replaced["questions"][0] == source["questions"][0],
        "round_structure_after_replace": replaced["round_structure"],
        "style_after_replace": replaced["visual_style"],
        "readiness": workflow_readiness(source),
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "mp4_count": 0,
    }
    evidence = out / "workflow-readback.json"
    evidence.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readback = json.loads(evidence.read_text(encoding="utf-8"))
    assert readback == payload
    manifest = {
        "status": "SELF_VERIFIED",
        "workflow_readback": str(evidence),
        "workflow_readback_sha256": sha256(evidence),
        "stages": 4,
        "round_structure_preserved": payload["round_structure_preserved"],
        "source_untouched": payload["source_untouched"],
        "other_question_preserved": payload["other_question_preserved"],
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "mp4_count": 0,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
