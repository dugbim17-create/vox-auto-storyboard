"""Deterministic Phase 2 quiz research and fact-policy verification."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.schemas.quiz import validate_quiz_project

MIN_CANDIDATES = 8
OFFICIAL_AUTHORITIES = {"official", "primary", "government"}


class QuizResearchError(ValueError):
    """Raised when a candidate bank cannot satisfy the approved pilot."""


@dataclass(frozen=True)
class VerifiedQuestionBank:
    selected: list[dict[str, Any]]
    rejected: dict[str, str]
    provider_calls: int = 0


@dataclass(frozen=True)
class QuizResearchResult:
    project: dict[str, Any]
    rejected: dict[str, str]
    provider_calls: int = 0


def _source_policy(question: dict[str, Any]) -> str | None:
    if question.get("time_sensitive") is True and not str(question.get("as_of_date") or "").strip():
        return "time_sensitive_missing_as_of_date"
    sources = question.get("fact_sources") or []
    records = [source for source in sources if isinstance(source, dict)]
    if any(str(source.get("authority") or "").casefold() in OFFICIAL_AUTHORITIES for source in records):
        return None
    publishers = {
        str(source.get("publisher") or "").strip().casefold()
        for source in records
        if str(source.get("publisher") or "").strip()
    }
    if len(publishers) >= 2:
        return None
    return "insufficient_independent_sources"


def verify_question_bank(candidates: list[dict[str, Any]], *, target_count: int = 5) -> VerifiedQuestionBank:
    if len(candidates) < MIN_CANDIDATES:
        raise QuizResearchError(f"question research requires at least {MIN_CANDIDATES} candidates")
    selected: list[dict[str, Any]] = []
    rejected: dict[str, str] = {}
    seen_text: set[str] = set()
    for raw in candidates:
        question = deepcopy(raw)
        question_id = str(question.get("question_id") or "").strip()
        normalized = " ".join(str(question.get("question") or "").casefold().split())
        if normalized in seen_text:
            rejected[question_id] = "duplicate_question"
            continue
        seen_text.add(normalized)
        reason = _source_policy(question)
        if reason:
            rejected[question_id] = reason
            continue
        selected.append(question)
        if len(selected) == target_count:
            break
    if len(selected) < target_count:
        raise QuizResearchError(f"only {len(selected)} eligible questions; need {target_count}")
    return VerifiedQuestionBank(selected=selected, rejected=rejected)


def research_quiz_fixture(
    candidates: list[dict[str, Any]], *, topic: str, project_id: str = "quiz_pilot_001"
) -> QuizResearchResult:
    verified = verify_question_bank(candidates, target_count=5)
    project = {
        "schema_version": "quiz_project_v1",
        "project_id": project_id,
        "title": f"Quiz {topic}",
        "topic": topic,
        "language": "vi",
        "target_question_count": 5,
        "question_count": 5,
        "seconds_per_question": 10,
        "difficulty": "mixed",
        "audience": "general",
        "theme_id": "vox_quiz_01",
        "voice_profile_id": "voice_vi_01",
        "bgm_id": "quiz_upbeat_01",
        "approval": {"status": "draft", "approved_at": None, "content_fingerprint": None},
        "questions": verified.selected,
        "research": {
            "candidate_count": len(candidates),
            "selected_count": len(verified.selected),
            "rejected": verified.rejected,
            "provider_calls": 0,
        },
        "intro": {},
        "outro": {},
    }
    return QuizResearchResult(
        project=validate_quiz_project(project),
        rejected=verified.rejected,
    )
