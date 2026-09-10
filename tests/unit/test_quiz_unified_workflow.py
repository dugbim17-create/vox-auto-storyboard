from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.quiz_unified_workflow import (
    STAGES,
    mark_workflow_dirty,
    normalize_quiz_workflow_document,
    preserve_regeneration_context,
    replace_one_question,
    update_workflow_stage,
    workflow_readiness,
)


def _document() -> dict:
    return {
        "engine_v2": True,
        "language": "vi-VN",
        "channel_profile": "fr-culture",
        "visual_style": {"id": "clear-knowledge", "version": 1, "motion": "medium"},
        "round_structure": {
            "schema_version": 1,
            "mode": "mixed",
            "rounds": [
                {"id": "warmup", "label": "Khởi động", "format_key": "multiple_choice", "count": 1, "difficulty": "easy"},
                {"id": "visual", "label": "Nhìn kỹ", "format_key": "photo_reveal", "count": 1, "difficulty": "medium"},
            ],
        },
        "questions": [
            {"id": "q1", "order": 1, "round_id": "warmup", "format_key": "multiple_choice", "question": "Một?"},
            {"id": "q2", "order": 2, "round_id": "visual", "format_key": "photo_reveal", "question": "Hai?"},
        ],
        "approval": {"status": "approved"},
    }


def test_normalize_adds_workflow_without_mutating_source() -> None:
    source = _document()
    original = deepcopy(source)
    result = normalize_quiz_workflow_document(source)
    assert source == original
    assert result["workflow"] == {"stage": "channel", "selected_question_id": None, "dirty": False}
    assert result["round_structure"] == source["round_structure"]


def test_stage_navigation_is_bounded_and_document_preserved() -> None:
    source = _document()
    result = update_workflow_stage(source, "appearance")
    assert result["workflow"]["stage"] == "appearance"
    assert result["questions"] == source["questions"]
    assert result["visual_style"] == source["visual_style"]
    with pytest.raises(ValueError, match="stage"):
        update_workflow_stage(source, "unknown")
    assert STAGES == ("channel", "content", "appearance", "voice_export")


def test_readiness_is_truthful_and_offline() -> None:
    ready = workflow_readiness(_document())
    assert ready["content"] is True
    assert ready["appearance"] is True
    assert ready["provider_calls"] == 0
    assert ready["tts_calls"] == 0
    assert ready["video_exports"] == 0
    empty = workflow_readiness({"engine_v2": True, "questions": []})
    assert empty["content"] is False
    assert empty["question_count"] == 0


def test_dirty_and_regeneration_preserve_context_and_only_replace_one() -> None:
    source = _document()
    dirty = mark_workflow_dirty(source)
    assert source.get("workflow") is None
    assert dirty["workflow"]["dirty"] is True
    context = preserve_regeneration_context(source, "q2")
    assert context["question_id"] == "q2"
    assert context["round_id"] == "visual"
    assert context["format_key"] == "photo_reveal"
    replaced = replace_one_question(source, "q2", {"question": "Hai mới?"})
    assert replaced["questions"][0] == source["questions"][0]
    assert replaced["questions"][1]["question"] == "Hai mới?"
    assert replaced["questions"][1]["round_id"] == "visual"
    assert replaced["round_structure"] == source["round_structure"]
    assert replaced["visual_style"] == source["visual_style"]
    assert replaced["approval"] == {"status": "draft"}
    assert replaced["workflow"]["dirty"] is True
