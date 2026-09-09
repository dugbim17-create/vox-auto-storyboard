from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2, get_font
from app.services.quiz_style_identity import build_quiz_visual_identity
from app.services.quiz_style_packs import StylePackError, resolve_style_snapshot
from app.services.quiz_v2_runtime import content_fingerprint, load_document, save_document
from app.services.quiz_v2_style_bridge import load_visual_style_snapshot, save_visual_style_snapshot


def _question() -> dict:
    return {
        "id": "q1",
        "question": "Which explanation fits?",
        "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}],
        "correct_id": "A",
        "answer_text": "One",
        "countdown_seconds": 3.5,
    }


def _document(snapshot: dict) -> dict:
    return {
        "engine_v2": True,
        "language": "en-US",
        "questions": [_question()],
        "visual_style": copy.deepcopy(snapshot),
    }


def test_version_is_an_independent_identity_dimension() -> None:
    first = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="medium")
    second = copy.deepcopy(first)
    second["version"] = 999
    assert first["version"] != second["version"]
    with pytest.raises(StylePackError, match="version"):
        resolve_style_snapshot(
            "clear-knowledge",
            locale="en-US",
            motion="medium",
            snapshot_override=second["snapshot"],
            version=second["version"],
        )


def test_unsupported_persisted_version_is_rejected_without_registry_fallback() -> None:
    snapshot = resolve_style_snapshot("clear-knowledge", locale="en-US")
    snapshot["version"] = 999
    with pytest.raises(ValueError, match="version"):
        save_visual_style_snapshot(
            {"engine_v2": True, "questions": [], "visual_style": snapshot},
            Path("unsupported-version-should-not-be-created.json"),
        )


def test_registry_upgrade_does_not_silently_change_saved_old_snapshot(tmp_path: Path) -> None:
    import app.services.quiz_style_packs as registry

    saved = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="low")
    path = save_visual_style_snapshot(_document(saved), tmp_path / "episode.json")
    before = load_visual_style_snapshot(path)
    original_pack = copy.deepcopy(registry._STYLE_PACKS["clear-knowledge"])
    try:
        registry._STYLE_PACKS["clear-knowledge"]["version"] = 2
        registry._STYLE_PACKS["clear-knowledge"]["snapshot"]["palette"]["accent"] = "registry-v2-accent"
        with pytest.raises(ValueError, match="version"):
            load_visual_style_snapshot(path)
    finally:
        registry._STYLE_PACKS["clear-knowledge"] = original_pack
    assert before["version"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["visual_style"]["version"] == 1


def test_save_reload_preserves_exact_snapshot_version(tmp_path: Path) -> None:
    snapshot = resolve_style_snapshot("editorial-culture", locale="en-US", motion="high")
    path = save_document(_document(snapshot), tmp_path)
    loaded = load_document(path)
    assert loaded["visual_style"]["version"] == snapshot["version"]
    assert loaded["visual_style"] == snapshot


def test_render_normalization_preserves_persisted_version_and_rejects_unknown() -> None:
    snapshot = resolve_style_snapshot("sport-scoreboard", locale="en-US", motion="low")
    engine = QuizVideoEngineV2(QuizRenderOptions(visual_style=snapshot, language="en-US"))
    assert engine.opt.visual_style["version"] == snapshot["version"]
    unsupported = copy.deepcopy(snapshot)
    unsupported["version"] = 999
    with pytest.raises(ValueError, match="version"):
        QuizVideoEngineV2(QuizRenderOptions(visual_style=unsupported, language="en-US"))


def test_fingerprint_and_visual_identity_include_snapshot_version(tmp_path: Path) -> None:
    first = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="medium")
    second = copy.deepcopy(first)
    second["version"] = 2
    first_doc = _document(first)
    second_doc = _document(second)
    with pytest.raises(ValueError, match="version"):
        content_fingerprint(second_doc)
    identity_a = build_quiz_visual_identity(first_doc, visual_style=first)
    with pytest.raises(ValueError, match="version"):
        build_quiz_visual_identity(second_doc, visual_style=second)
    assert identity_a["visual_style"]["version"] == first["version"]


def test_rendered_pixels_keep_the_saved_version_token_in_engine_snapshot() -> None:
    snapshot = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="medium")
    engine = QuizVideoEngineV2(QuizRenderOptions(visual_style=snapshot, language="en-US"))
    canvas = Image.new("RGB", (1920, 1080), "black")
    event = {
        "idx": 1,
        "total_q": 1,
        "q_start": 0,
        "cd_start": 2,
        "cd_dur": 6,
        "rev_start": 8,
        "rev_dur": 4,
        "data": _question(),
    }
    frame = engine._render_question_card(canvas, ImageDraw.Draw(canvas), 3, event)
    assert frame.size == (1920, 1080)
    assert engine.opt.visual_style["version"] == snapshot["version"]
