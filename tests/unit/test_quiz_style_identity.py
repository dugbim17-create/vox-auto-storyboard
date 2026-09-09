from __future__ import annotations

from app.services.quiz_style_identity import build_quiz_visual_identity
from app.services.quiz_style_packs import resolve_style_snapshot


def test_visual_style_snapshot_changes_visual_identity_only() -> None:
    snapshot_a = resolve_style_snapshot("clear-knowledge", locale="vi-VN")
    snapshot_b = resolve_style_snapshot("editorial-culture", locale="vi-VN")
    base = {
        "questions": [{"id": "q1", "question": "Một cộng một?", "correct_id": "A"}],
        "assets": {"q1": "asset-sha"},
        "narration": {"q1": "voice-sha"},
    }

    identity_a = build_quiz_visual_identity(base, visual_style=snapshot_a)
    identity_b = build_quiz_visual_identity(base, visual_style=snapshot_b)

    assert identity_a["semantic_hash"] == identity_b["semantic_hash"]
    assert identity_a["asset_hash"] == identity_b["asset_hash"]
    assert identity_a["narration_hash"] == identity_b["narration_hash"]
    assert identity_a["visual_hash"] != identity_b["visual_hash"]
    assert identity_a["video_hash"] != identity_b["video_hash"]


def test_no_style_document_keeps_baseline_identity() -> None:
    base = {
        "questions": [{"id": "q1", "question": "Một cộng một?", "correct_id": "A"}],
        "assets": {"q1": "asset-sha"},
        "narration": {"q1": "voice-sha"},
    }
    identity = build_quiz_visual_identity(base)
    assert identity["schema_version"] == "quiz_visual_identity_v1"
    assert identity["visual_style"] is None
    assert identity["visual_hash"] == identity["baseline_visual_hash"]
    assert identity["video_hash"] == identity["baseline_video_hash"]


def test_visual_identity_is_deterministic_for_equivalent_mapping_order() -> None:
    snapshot = resolve_style_snapshot("sport-scoreboard")
    first = build_quiz_visual_identity({"b": 2, "a": 1}, visual_style=snapshot)
    second = build_quiz_visual_identity({"a": 1, "b": 2}, visual_style=snapshot)
    assert first == second


def test_visual_identity_rejects_invalid_style_snapshot() -> None:
    try:
        build_quiz_visual_identity({}, visual_style={"id": "unknown", "version": 1})
    except ValueError as exc:
        assert "visual style" in str(exc).lower()
    else:
        raise AssertionError("invalid visual style must fail closed")


def test_engine_normalizes_and_keeps_persisted_style_snapshot() -> None:
    from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2

    snapshot = resolve_style_snapshot("editorial-culture", locale="fr-FR", motion="low")
    engine = QuizVideoEngineV2(QuizRenderOptions(visual_style=snapshot, language="fr-FR"))
    assert engine.opt.visual_style == snapshot
    assert engine.opt.visual_style is not snapshot
