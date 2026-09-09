from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PIL import Image

from app.services.quiz_style_identity import build_quiz_visual_identity
from app.services.quiz_style_packs import resolve_style_snapshot
from app.services.quiz_v2_runtime import content_fingerprint


def _document(tmp_path: Path, style: dict | None) -> dict:
    image = tmp_path / "scene.png"
    Image.new("RGB", (24, 24), "#dd5544").save(image)
    question = {
        "id": "q1",
        "question": "Which explanation fits?",
        "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}],
        "correct_id": "A",
        "answer_text": "One",
        "reveal_image_path": str(image),
        "countdown_seconds": 3.5,
    }
    return {
        "engine_v2": True,
        "language": "en-US",
        "questions": [question],
        "assets": {"q1": {"sha256": "asset-fixture"}},
        "narration": {"q1": "One"},
        **({"visual_style": deepcopy(style)} if style is not None else {}),
    }


def test_content_fingerprint_style_change_invalidates_review_identity_but_not_speech(tmp_path: Path) -> None:
    low = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="low")
    high = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="high")
    first = _document(tmp_path, low)
    second = _document(tmp_path, high)
    assert content_fingerprint(first) != content_fingerprint(second)
    assert first["narration"] == second["narration"]
    assert first["questions"] == second["questions"]


def test_style_identity_cache_keys_change_only_visual_video_channels(tmp_path: Path) -> None:
    low = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="low")
    high = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="high")
    base = _document(tmp_path, low)
    changed = _document(tmp_path, high)
    first = build_quiz_visual_identity(base, visual_style=low)
    second = build_quiz_visual_identity(changed, visual_style=high)
    assert first["semantic_hash"] == second["semantic_hash"]
    assert first["asset_hash"] == second["asset_hash"]
    assert first["narration_hash"] == second["narration_hash"]
    assert first["visual_hash"] != second["visual_hash"]
    assert first["video_hash"] != second["video_hash"]


def test_legacy_content_fingerprint_remains_stable_without_style(tmp_path: Path) -> None:
    first = _document(tmp_path, None)
    second = deepcopy(first)
    assert content_fingerprint(first) == content_fingerprint(second)
    identity = build_quiz_visual_identity(first)
    assert identity["visual_hash"] == identity["baseline_visual_hash"]
    assert identity["video_hash"] == identity["baseline_video_hash"]
