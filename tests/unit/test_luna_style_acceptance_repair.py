from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageChops, ImageDraw

from app.services.quiz_channel_renderer import render as render_channel
from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2, get_font
from app.services.quiz_style_packs import resolve_style_snapshot
from app.services.quiz_v2_runtime import content_fingerprint, require_review


def _question() -> dict:
    return {
        "id": "q1",
        "question": "Which explanation fits the runway numbering rule?",
        "choices": [
            {"id": "A", "text": "Magnetic heading"},
            {"id": "B", "text": "Opening year"},
        ],
        "correct_id": "A",
        "answer_text": "Magnetic heading",
        "explanation_text": "Runway numbers follow magnetic heading.",
        "difficulty": "medium",
        "countdown_seconds": 3.5,
    }


def _document(style: dict | None = None) -> dict:
    payload = {
        "schema_version": "quiz_v2_dynamic",
        "engine_v2": True,
        "title": "Repair fixture",
        "language": "en-US",
        "questions": [_question()],
    }
    if style is not None:
        payload["visual_style"] = deepcopy(style)
    return payload


def _event() -> dict:
    return {
        "idx": 1,
        "total_q": 1,
        "q_start": 0,
        "cd_start": 2,
        "cd_dur": 6,
        "rev_start": 8,
        "rev_dur": 4,
        "data": _question(),
    }


def _channel_engine(style: dict | None, profile: str = "de-wissen") -> SimpleNamespace:
    return SimpleNamespace(
        opt=SimpleNamespace(
            channel_profile=profile,
            language="en-US",
            visual_style=deepcopy(style),
        ),
        _normalize_choices=lambda question: [
            (str(choice["id"]), str(choice["text"]))
            for choice in question.get("choices", [])
        ],
    )


def _render_via_channel(style: dict | None, *, profile: str = "de-wissen", state: str = "question", aspect: str = "16:9") -> Image.Image:
    size = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    canvas = Image.new("RGB", size, "black")
    engine = _channel_engine(style, profile)
    return render_channel(
        engine,
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event(),
        time=9 if state == "reveal" else 3,
    )


def _render_via_production_dispatch(style: dict | None, *, profile: str = "de-wissen", state: str = "question", aspect: str = "16:9") -> Image.Image:
    size = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    options = QuizRenderOptions(
        aspect_ratio=aspect,
        channel_profile=profile,
        language="en-US",
        visual_style=deepcopy(style),
    )
    engine = QuizVideoEngineV2(options)
    canvas = Image.new("RGB", size, "black")
    return engine._render_question_card(
        canvas,
        ImageDraw.Draw(canvas),
        9 if state == "reveal" else 3,
        _event(),
    )


def test_preview_and_production_dispatch_match_pixels_for_style_question_and_reveal() -> None:
    style = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="medium")
    for state in ("question", "reveal"):
        preview = _render_via_channel(style, profile="de-wissen", state=state)
        production = _render_via_production_dispatch(style, profile="de-wissen", state=state)
        assert preview.tobytes() == production.tobytes()


def test_preview_and_production_dispatch_match_pixels_for_legacy_no_style() -> None:
    for state in ("question", "reveal"):
        preview = _render_via_channel(None, profile="de-wissen", state=state)
        production = _render_via_production_dispatch(None, profile="de-wissen", state=state)
        assert preview.tobytes() == production.tobytes()


def test_production_dispatch_without_profile_does_not_require_unknown_channel() -> None:
    options = QuizRenderOptions()
    engine = QuizVideoEngineV2(options)
    canvas = Image.new("RGB", (1920, 1080), "black")
    frame = engine._render_question_card(canvas, ImageDraw.Draw(canvas), 3, _event())
    assert frame.size == (1920, 1080)


def test_style_snapshot_tokens_change_actual_pixels_and_saved_snapshot_wins() -> None:
    style = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="medium")
    modified = deepcopy(style)
    modified["snapshot"]["palette"]["background"] = "#d7c3a4"
    modified["snapshot"]["palette"]["text"] = "#1f2b2a"
    modified["snapshot"]["palette"]["accent"] = "#b5362b"
    modified["snapshot"]["typography"]["display"] = "editorial-display"
    modified["snapshot"]["shapes"]["panels"] = "square-editorial"
    modified["snapshot"]["spacing"]["gutter"] = 64

    original = _render_via_channel(style, profile="de-wissen")
    changed = _render_via_channel(modified, profile="de-wissen")
    assert ImageChops.difference(original, changed).getbbox() is not None

    import app.services.quiz_style_packs as registry

    registry_before = deepcopy(registry._STYLE_PACKS["clear-knowledge"])
    try:
        registry._STYLE_PACKS["clear-knowledge"]["snapshot"]["palette"]["background"] = "#040404"
        saved_again = _render_via_channel(modified, profile="de-wissen")
    finally:
        registry._STYLE_PACKS["clear-knowledge"] = registry_before
    assert saved_again.tobytes() == changed.tobytes()


def test_fingerprint_includes_style_but_preserves_semantic_asset_and_narration_identity(tmp_path: Path) -> None:
    image = tmp_path / "asset.png"
    Image.new("RGB", (32, 32), "#dd5544").save(image)
    base = _document()
    base["questions"][0]["scene_image"] = str(image)
    base["questions"][0]["options"] = ["A", "B"]
    base["questions"][0]["correct_option"] = "A"
    base["narration"] = {"q1": "Magnetic heading"}
    base["assets"] = {"q1": {"sha256": "fixture-asset"}}
    base["visual_style"] = None
    first = content_fingerprint(base)
    styled = deepcopy(base)
    styled["visual_style"] = resolve_style_snapshot("editorial-culture", locale="en-US", motion="high")
    second = content_fingerprint(styled)
    assert first != second
    assert styled["questions"] == base["questions"]
    assert styled["assets"] == base["assets"]
    assert styled["narration"] == base["narration"]


def test_style_only_change_invalidates_review_fingerprint_without_changing_tts_inputs(tmp_path: Path) -> None:
    image = tmp_path / "asset.png"
    Image.new("RGB", (32, 32), "#dd5544").save(image)
    style_a = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="low")
    style_b = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="high")
    first = _document(style_a)
    first["questions"][0]["scene_image"] = str(image)
    first["questions"][0]["options"] = ["A", "B"]
    first["questions"][0]["correct_option"] = "A"
    first["narration"] = {"q1": "Magnetic heading"}
    approved = deepcopy(first)
    approved["approval"] = {"status": "approved", "reviewer": "human", "content_fingerprint": content_fingerprint(first)}
    require_review(approved)
    changed = deepcopy(approved)
    changed["visual_style"] = style_b
    assert changed["narration"] == approved["narration"]
    with pytest.raises(ValueError, match="review required"):
        require_review(changed)


def test_snapshot_with_unsupported_path_or_code_remains_rejected() -> None:
    style = resolve_style_snapshot("clear-knowledge", locale="en-US")
    unsafe = deepcopy(style)
    unsafe["snapshot"]["background"]["source"] = "../secret.png"
    with pytest.raises(ValueError):
        resolve_style_snapshot(
            "clear-knowledge",
            locale="en-US",
            motion="medium",
            snapshot_override=unsafe["snapshot"],
        )


def test_supported_snapshot_shape_and_typography_tokens_change_real_layout() -> None:
    from app.services.quiz_layout_spec import resolve_layout

    base = resolve_style_snapshot("clear-knowledge", locale="en-US")
    modified = deepcopy(base)
    modified["snapshot"]["spacing"]["safe_margin"] = 80
    modified["snapshot"]["shapes"]["panels"] = "square-editorial"
    modified["snapshot"]["typography"]["display"] = "editorial-display"
    normal = resolve_layout(_question(), "16:9", base)
    changed = resolve_layout(_question(), "16:9", modified)
    assert normal.safe_margin != changed.safe_margin
    assert normal.question.as_tuple() != changed.question.as_tuple()
