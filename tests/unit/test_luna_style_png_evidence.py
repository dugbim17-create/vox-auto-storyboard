from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.services.quiz_style_packs import resolve_style_snapshot


def _document(style_id: str, motion: str) -> dict:
    return {
        "engine_v2": True,
        "language": "en-US",
        "questions": [
            {
                "id": "q1",
                "question": "Which explanation fits?",
                "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}],
                "correct_id": "A",
                "answer_text": "One",
                "countdown_seconds": 3.5,
            }
        ],
        "visual_style": resolve_style_snapshot(style_id, locale="en-US", motion=motion),
    }


def test_preview_writer_uses_unique_run_style_motion_aspect_state_paths_and_manifest(tmp_path: Path) -> None:
    from app.services.quiz_style_evidence import write_preview_evidence

    manifest = write_preview_evidence(
        tmp_path,
        run_id="run-001",
        document=_document("clear-knowledge", "low"),
        frames={
            "question": Image.new("RGB", (1920, 1080), "#d7c3a4"),
            "reveal": Image.new("RGB", (1920, 1080), "#b5362b"),
        },
        aspect="16:9",
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-001"
    assert len(payload["artifacts"]) == 2
    paths = [Path(item["path"]) for item in payload["artifacts"]]
    assert len(set(paths)) == 2
    assert all(path.is_file() for path in paths)
    assert all("run-001" in path.name and "clear-knowledge" in path.name and "low" in path.name and "16_9" in path.name for path in paths)
    assert all(item["sha256"] for item in payload["artifacts"])
    assert payload["provider_calls"] == 0
    assert payload["tts_calls"] == 0
    assert payload["video_exports"] == 0
    assert payload["mp4_count"] == 0


def test_preview_writer_never_overwrites_existing_run_file(tmp_path: Path) -> None:
    from app.services.quiz_style_evidence import write_preview_evidence

    first = write_preview_evidence(
        tmp_path,
        run_id="run-001",
        document=_document("sport-scoreboard", "high"),
        frames={"question": Image.new("RGB", (1080, 1920), "#123456")},
        aspect="9:16",
    )
    before = first.read_bytes()
    with pytest.raises(FileExistsError):
        write_preview_evidence(
            tmp_path,
            run_id="run-001",
            document=_document("sport-scoreboard", "high"),
            frames={"question": Image.new("RGB", (1080, 1920), "#654321")},
            aspect="9:16",
        )
    assert first.read_bytes() == before


def test_preview_writer_rejects_missing_style_for_style_evidence(tmp_path: Path) -> None:
    from app.services.quiz_style_evidence import write_preview_evidence

    document = _document("clear-knowledge", "medium")
    document.pop("visual_style")
    with pytest.raises(ValueError, match="visual_style"):
        write_preview_evidence(
            tmp_path,
            run_id="run-legacy",
            document=document,
            frames={"question": Image.new("RGB", (1920, 1080), "black")},
            aspect="16:9",
        )
