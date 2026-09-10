from __future__ import annotations

import copy

import pytest

from app.services.quiz_episode_structure import (
    SUPPORTED_ROUND_FORMATS,
    allocate_round_questions,
    assign_legacy_round,
    validate_episode_structure,
)


def _structure() -> dict:
    return {
        "schema_version": 1,
        "mode": "mixed",
        "rounds": [
            {"id": "warmup", "label": "Khởi động", "format_key": "multiple_choice", "count": 2, "difficulty": "easy"},
            {"id": "visual", "label": "Nhìn kỹ", "format_key": "photo_reveal", "count": 1, "difficulty": "medium"},
        ],
    }


def test_supported_rounds_validate_and_allocate_deterministically() -> None:
    structure = _structure()
    validate_episode_structure(structure, episode_count=3)
    allocated = allocate_round_questions(structure, episode_count=3)
    assert [item["round_id"] for item in allocated] == ["warmup", "warmup", "visual"]
    assert [item["order"] for item in allocated] == [1, 2, 3]
    assert all(item["format_key"] in SUPPORTED_ROUND_FORMATS for item in allocated)


def test_legacy_document_gets_one_implicit_round_without_mutating_source() -> None:
    document = {"questions": [{"id": "q1"}, {"id": "q2"}]}
    original = copy.deepcopy(document)
    result = assign_legacy_round(document)
    assert document == original
    assert result["round_structure"]["rounds"][0]["id"] == "legacy"
    assert result["round_structure"]["rounds"][0]["count"] == 2
    assert all(question["round_id"] == "legacy" for question in result["questions"])


def test_round_count_mismatch_fails_closed() -> None:
    structure = _structure()
    with pytest.raises(ValueError, match="count"):
        validate_episode_structure(structure, episode_count=2)


@pytest.mark.parametrize(
    "mutation, pattern",
    [
        ("duplicate_id", "round id"),
        ("unsupported_format", "format"),
        ("zero_count", "count"),
        ("empty_rounds", "round"),
    ],
)
def test_invalid_round_structure_is_rejected(mutation: str, pattern: str) -> None:
    structure = _structure()
    if mutation == "duplicate_id":
        structure["rounds"][1]["id"] = structure["rounds"][0]["id"]
    elif mutation == "unsupported_format":
        structure["rounds"][0]["format_key"] = "fake_format"
    elif mutation == "zero_count":
        structure["rounds"][0]["count"] = 0
    else:
        structure["rounds"] = []
    with pytest.raises(ValueError, match=pattern):
        validate_episode_structure(structure, episode_count=3)


def test_no_asset_generation_is_encoded_for_text_only_round() -> None:
    structure = {
        "schema_version": 1,
        "mode": "mixed",
        "rounds": [
            {"id": "text", "label": "Kiến thức", "format_key": "multiple_choice", "count": 1, "difficulty": "medium"},
        ],
    }
    allocated = allocate_round_questions(structure, episode_count=1)
    assert allocated[0]["requires_asset"] is False
    assert allocated[0]["format_key"] == "multiple_choice"


def test_asset_dependent_round_is_marked_pending_until_evidence() -> None:
    structure = {
        "schema_version": 1,
        "mode": "mixed",
        "rounds": [
            {"id": "photo", "label": "Ảnh", "format_key": "photo_reveal", "count": 1, "difficulty": "medium"},
        ],
    }
    allocated = allocate_round_questions(structure, episode_count=1)
    assert allocated[0]["requires_asset"] is True
    assert allocated[0]["asset_status"] == "pending"
