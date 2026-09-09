from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.quiz_style_packs import resolve_style_snapshot
from app.services.quiz_v2_style_bridge import (
    load_visual_style_snapshot,
    save_visual_style_snapshot,
)


def test_saved_style_snapshot_survives_registry_change(tmp_path: Path) -> None:
    snapshot = resolve_style_snapshot("clear-knowledge", locale="de-DE", motion="low")
    document = {"engine_v2": True, "language": "de-DE", "questions": [], "visual_style": snapshot}
    path = save_visual_style_snapshot(document, tmp_path / "episode.json")

    # The registry is deliberately re-resolved with a different current default.
    current_default = resolve_style_snapshot("sport-scoreboard", locale="de-DE", motion="high")
    reopened = load_visual_style_snapshot(path)

    assert current_default["id"] != reopened["id"]
    assert reopened == snapshot
    assert reopened["motion"] == "low"


def test_snapshot_save_is_atomic_and_readback_rejects_invalid_document(tmp_path: Path) -> None:
    snapshot = resolve_style_snapshot("editorial-culture")
    path = save_visual_style_snapshot(
        {"engine_v2": True, "questions": [], "visual_style": snapshot},
        tmp_path / "episode.json",
    )
    assert json.loads(path.read_text(encoding="utf-8"))["visual_style"] == snapshot
    assert not list(tmp_path.glob("*.partial"))

    path.write_text(json.dumps({"engine_v2": True, "questions": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="visual_style"):
        load_visual_style_snapshot(path)


def test_save_document_with_visual_style_roundtrips_through_existing_runtime(tmp_path: Path) -> None:
    from app.services import quiz_v2_runtime as runtime

    snapshot = resolve_style_snapshot("clear-knowledge", locale="vi-VN", motion="low")
    document = {
        "engine_v2": True,
        "language": "vi-VN",
        "questions": [{
            "id": "q1",
            "question": "Một cộng một?",
            "choices": [{"id": "A", "text": "Hai"}, {"id": "B", "text": "Ba"}],
            "correct_id": "A",
        }],
        "visual_style": snapshot,
    }
    path = runtime.save_document(document, tmp_path)
    loaded = runtime.load_document(path)
    assert loaded["visual_style"] == snapshot
