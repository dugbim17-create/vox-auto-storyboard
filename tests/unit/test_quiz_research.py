from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_quiz_phase1_contract import quiz_fixture

from app.services.quiz_research import (
    QuizResearchError,
    research_quiz_fixture,
    verify_question_bank,
)


def candidate_bank(count: int = 8) -> list[dict]:
    candidates = quiz_fixture(count)["questions"]
    for question in candidates:
        question["fact_sources"][0]["authority"] = "official"
    return candidates


def test_fixture_research_requires_at_least_eight_candidates() -> None:
    with pytest.raises(QuizResearchError, match="at least 8"):
        research_quiz_fixture(candidate_bank(7), topic="Địa lý Việt Nam")


def test_verifier_selects_exactly_five_eligible_questions() -> None:
    candidates = candidate_bank(8)
    candidates[1]["time_sensitive"] = True
    candidates[1]["as_of_date"] = None
    candidates[2]["fact_sources"] = [
        {
            "source_id": "weak",
            "title": "Một blog",
            "url": "https://blog.test/3",
            "publisher": "Blog cá nhân",
            "accessed_at": "2026-08-10T00:00:00Z",
            "claim_supported": "Đúng B3",
            "authority": "secondary",
        }
    ]

    result = verify_question_bank(candidates, target_count=5)

    assert [question["question_id"] for question in result.selected] == [
        "q001",
        "q004",
        "q005",
        "q006",
        "q007",
    ]
    assert result.rejected["q002"] == "time_sensitive_missing_as_of_date"
    assert result.rejected["q003"] == "insufficient_independent_sources"
    assert result.provider_calls == 0


def test_two_independent_secondary_publishers_are_accepted() -> None:
    candidates = candidate_bank(8)
    candidates[0]["fact_sources"] = [
        {
            "source_id": "s1",
            "title": "Nguồn 1",
            "url": "https://one.test",
            "publisher": "Publisher One",
            "accessed_at": "2026-08-10T00:00:00Z",
            "claim_supported": "Đúng B1",
            "authority": "secondary",
        },
        {
            "source_id": "s2",
            "title": "Nguồn 2",
            "url": "https://two.test",
            "publisher": "Publisher Two",
            "accessed_at": "2026-08-10T00:00:00Z",
            "claim_supported": "Đúng B1",
            "authority": "secondary",
        },
    ]

    result = verify_question_bank(candidates, target_count=5)

    assert result.selected[0]["question_id"] == "q001"


def test_verifier_fails_when_fewer_than_five_meet_policy() -> None:
    candidates = candidate_bank(8)
    for question in candidates[:4]:
        question["time_sensitive"] = True
        question["as_of_date"] = None

    with pytest.raises(QuizResearchError, match="only 4 eligible"):
        verify_question_bank(candidates, target_count=5)


def test_research_result_builds_five_question_project_draft() -> None:
    result = research_quiz_fixture(candidate_bank(8), topic="Địa lý Việt Nam")

    assert result.project["target_question_count"] == 5
    assert result.project["question_count"] == 5
    assert result.project["topic"] == "Địa lý Việt Nam"
    assert result.project["approval"]["status"] == "draft"
    assert len(result.project["questions"]) == 5
    assert result.project["research"]["candidate_count"] == 8
    assert result.project["research"]["selected_count"] == 5
    assert result.provider_calls == 0


def test_repository_candidate_bank_is_fact_verified_and_selectable() -> None:
    payload = json.loads(
        Path("presets/quiz_5_vi_candidates_verified.json").read_text(encoding="utf-8")
    )

    result = research_quiz_fixture(payload["questions"], topic=payload["topic"])

    assert len(payload["questions"]) == 8
    assert len(result.project["questions"]) == 5
    assert all(
        isinstance(question["fact_sources"][0], dict)
        and question["fact_sources"][0]["authority"] == "official"
        for question in result.project["questions"]
    )
