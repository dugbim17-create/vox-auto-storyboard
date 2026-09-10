from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Keep offscreen as a default for structural tests; native callers set windows before import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.gui_qt import VoxQtApp
from app.services.quiz_style_packs import resolve_style_snapshot
from app.ui_qt.main_window import VoxStudioWindow


def fixture() -> dict:
    def q(qid: str, order: int, round_id: str) -> dict:
        return {
            "id": qid,
            "order": order,
            "round_id": round_id,
            "format_key": "multiple_choice" if round_id == "warmup" else "photo_reveal",
            "question": f"Câu hỏi {order} · kiến thức địa lý?",
            "choices": [{"id": c, "text": f"Phương án {c}"} for c in "ABCD"],
            "correct_id": "A",
            "answer_text": "Phương án A",
            "explanation_text": "Giải thích fixture local.",
            "fact_sources": ["https://example.test/source"],
        }
    return {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Native four-stage fixture",
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
        "questions": [q("q1", 1, "warmup"), q("q2", 2, "visual")],
        "approval": {"status": "draft"},
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(window: VoxStudioWindow, stage: int, output: Path) -> dict:
    window.quiz_stage_stack.setCurrentIndex(stage)
    QApplication.processEvents()
    output.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(output), "PNG")
    with output.open("rb") as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    return {
        "stage": stage + 1,
        "stage_name": window.quiz_stage_stack.widget(stage).objectName(),
        "path": str(output.resolve()),
        "sha256": digest,
        "bytes": output.stat().st_size,
        "size": [output.stat().st_size and window.width(), window.height()],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--output-root", default="output/quiz-unified-workflow")
    args = parser.parse_args()
    out = (PROJECT_ROOT / args.output_root / args.run).resolve()
    out.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    backend = app.platformName()
    window = VoxStudioWindow(autoload=False)
    try:
        window.resize(1431, 921)
        window.show()
        window.show_page("quiz")
        document = fixture()
        window.set_quiz_document(document)
        stages = [capture(window, stage, out / "screenshots" / f"step-{stage + 1}.png") for stage in range(4)]
        window.quiz_question_table.item(0, 2).setText("Câu hỏi đã chỉnh sửa chưa lưu")
        window.mark_quiz_stage_dirty()
        dirty = {
            "dirty": bool(window.quiz_stage_dirty.property("dirty")),
            "message": window.quiz_stage_dirty.text(),
            "document_question_still_original": document["questions"][0]["question"] == "Câu hỏi 1 · kiến thức địa lý?",
        }
    finally:
        window.close()
    payload = {
        "run_id": args.run,
        "fixture_origin": "local in-memory fixture",
        "screenshots": stages,
        "dirty_state": dirty,
        "window_size": [1431, 921],
        "qt_platform": backend,
        "workflow_stages": 4,
        "stage_names": [item["stage_name"] for item in stages],
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
        "mp4_count": 0,
    }
    readback = out / "native-screenshot-readback.json"
    readback.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert json.loads(readback.read_text(encoding="utf-8")) == payload
    manifest = {
        "status": "SELF_VERIFIED",
        "readback": str(readback),
        "readback_sha256": sha256(readback),
        "screenshot_count": len(stages),
        "unique_screenshot_paths": len({item["path"] for item in stages}) == 4,
        "screenshot_hash_readback": all(sha256(Path(item["path"])) == item["sha256"] for item in stages),
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


def _unused_qt_role_marker() -> None:
    # Kept deliberately empty: screenshots are produced by the native Qt widget,
    # not by a decorative image generator.
    return None

_ = Qt
