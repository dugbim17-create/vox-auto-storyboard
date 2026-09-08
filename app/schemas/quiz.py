from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from typing import Any

QUIZ_SCHEMA_VERSION = "quiz_project_v1"
QUIZ_QUESTION_COUNT = 30
SUPPORTED_QUESTION_TYPES = {
    "multiple_choice_image",
    "multiple_choice_text",
    "word_puzzle",
    "image_identification",
    "emoji_rebus",
    "concept_rebus",
    "open_visual",
    "dont_say_same",
    "eat_or_pass",
    "fast_math",
    "vocab_flashcard",
    "mystery_box",
    "missing_letters",
    "silhouette_shadow",
    "this_or_that",
    "anime_character",
}
SUPPORTED_TEMPLATES = {
    "image_left_mcq_right",
    "text_mcq",
    "text_word_puzzle",
    "image_identification",
    "emoji_rebus_grid",
    "concept_rebus_horizontal",
    "open_visual_card",
    "dont_say_same_mystery",
    "eat_or_pass_split",
    "fast_math_blackboard",
    "vocab_flashcard_split",
    "mystery_box_triplet",
    "missing_letters_tiles",
    "silhouette_shadow_card",
    "this_or_that_versus",
    "anime_character_clues",
}


class QuizValidationError(ValueError):
    """Raised when a quiz project cannot be rendered unambiguously."""


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise QuizValidationError(f"{field} must not be empty")
    return text


def _normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _validate_fact_sources(question: dict[str, Any], index: int) -> None:
    sources = question.get("fact_sources")
    if not isinstance(sources, list) or not sources:
        raise QuizValidationError(f"question {index} fact_sources must not be empty")
    for source_index, source in enumerate(sources, 1):
        if isinstance(source, str):
            _required_text(source, f"question {index} source {source_index} url")
            continue
        if not isinstance(source, dict):
            raise QuizValidationError(f"question {index} source {source_index} must be an object")
        for field in ("source_id", "title", "url", "publisher", "accessed_at", "claim_supported"):
            _required_text(source.get(field), f"question {index} source {source_index} {field}")


def validate_quiz_project(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise QuizValidationError("quiz project must be an object")
    quiz = deepcopy(document)
    if quiz.get("schema_version") != QUIZ_SCHEMA_VERSION:
        raise QuizValidationError(f"schema_version must be {QUIZ_SCHEMA_VERSION}")
    _required_text(quiz.get("title"), "title")
    _required_text(quiz.get("language"), "language")
    _required_text(quiz.get("theme_id"), "theme_id")
    questions = quiz.get("questions")
    legacy_count_contract = "target_question_count" not in quiz
    target_count = quiz.get("target_question_count", QUIZ_QUESTION_COUNT)
    if isinstance(target_count, bool) or not isinstance(target_count, int) or target_count < 1:
        raise QuizValidationError("target_question_count must be a positive integer")
    if not isinstance(questions, list) or len(questions) != target_count:
        if legacy_count_contract:
            raise QuizValidationError("quiz must contain exactly 30 questions")
        raise QuizValidationError("questions must match target_question_count")
    if quiz.get("question_count") != target_count:
        if legacy_count_contract:
            raise QuizValidationError("question_count must be exactly 30")
        raise QuizValidationError("question_count must match target_question_count")
    quiz["target_question_count"] = target_count
    default_seconds = quiz.get("seconds_per_question")
    if isinstance(default_seconds, bool) or not isinstance(default_seconds, int) or default_seconds < 1:
        raise QuizValidationError("seconds_per_question must be a positive integer")

    seen_ids: set[str] = set()
    seen_question_texts: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(questions, 1):
        if not isinstance(raw, dict):
            raise QuizValidationError(f"question {index} must be an object")
        question = deepcopy(raw)
        question_id = _required_text(question.get("question_id"), f"question {index} question_id")
        if question_id in seen_ids:
            raise QuizValidationError("question ids must be unique")
        seen_ids.add(question_id)
        if question.get("order") != index:
            raise QuizValidationError("question order must be contiguous 1..30")
        question_type = _required_text(question.get("type"), f"question {index} type")
        if question_type not in SUPPORTED_QUESTION_TYPES:
            raise QuizValidationError(f"unsupported question type: {question_type}")
        template_id = _required_text(question.get("template_id"), f"question {index} template_id")
        if template_id not in SUPPORTED_TEMPLATES:
            raise QuizValidationError(f"unsupported template: {template_id}")
        question_text = _required_text(question.get("question"), f"question {index} question")
        normalized_text = _normalized_text(question_text)
        if normalized_text in seen_question_texts:
            raise QuizValidationError("duplicate question text")
        seen_question_texts.add(normalized_text)
        _required_text(question.get("question_voice"), f"question {index} question_voice")
        _required_text(question.get("answer_voice"), f"question {index} answer_voice")
        countdown = question.get("countdown_seconds", default_seconds)
        if isinstance(countdown, bool) or not isinstance(countdown, int) or countdown < 1:
            raise QuizValidationError(f"question {index} countdown_seconds must be positive")
        question["countdown_seconds"] = countdown
        _validate_fact_sources(question, index)
        if question.get("time_sensitive") is True:
            _required_text(question.get("as_of_date"), f"question {index} as_of_date")

        if question_type.startswith("multiple_choice") or "choices" in question or question_type in {"fast_math", "vocab_flashcard"}:
            choices = question.get("choices")
            if not isinstance(choices, list) or len(choices) < 2:
                raise QuizValidationError(f"question {index} choices must contain at least two items")
            choice_ids = [_required_text(choice.get("id"), "choice id") for choice in choices if isinstance(choice, dict)]
            if len(choice_ids) != len(choices) or len(choice_ids) != len(set(choice_ids)):
                raise QuizValidationError("choice ids must be unique")
            choice_by_id = {
                choice_id: _required_text(choice.get("text"), f"choice {choice_id} text")
                for choice_id, choice in zip(choice_ids, choices, strict=True)
            }
            correct_id = _required_text(question.get("correct_choice_id"), "correct_choice_id")
            if correct_id not in choice_by_id:
                raise QuizValidationError("correct_choice_id must match one choice")
            answer_text = _required_text(question.get("answer_text"), "answer_text")
            if answer_text.casefold() != choice_by_id[correct_id].casefold():
                raise QuizValidationError("answer_text must match the correct choice text")
        else:
            answer_text = _required_text(question.get("answer_text"), "answer_text")
        answer_voice = _required_text(question.get("answer_voice"), f"question {index} answer_voice")
        if _normalized_text(answer_text) not in _normalized_text(answer_voice):
            raise QuizValidationError("answer_voice must contain answer_text")
        question.setdefault("approval_status", "draft")
        question.setdefault("content_fingerprint", None)
        question.setdefault(
            "artifacts",
            {
                "question_audio": None,
                "answer_audio": None,
                "visual": None,
                "question_video": None,
            },
        )
        question.setdefault("timing", {})
        question.setdefault(
            "ledger",
            {
                "status": "planned",
                "attempt_count": 0,
                "research_status": "pending",
                "fact_status": "pending",
                "approval_status": "pending",
                "asset_status": "pending",
                "question_tts_status": "pending",
                "answer_tts_status": "pending",
                "render_status": "pending",
                "qc_status": "pending",
                "provider_request_ids": [],
                "last_error": None,
                "updated_at": None,
            },
        )
        question.setdefault("validation", {})
        normalized.append(question)

    quiz["questions"] = normalized
    quiz.setdefault("intro", {})
    quiz.setdefault("outro", {})
    return quiz


SUPPORTED_ARTIFACT_KINDS = {"visual", "question_audio", "answer_audio", "question_video"}


def validate_quiz_artifact(record: dict[str, Any], *, expected_question_id: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise QuizValidationError("artifact must be an object")
    artifact = deepcopy(record)
    _required_text(artifact.get("artifact_id"), "artifact_id")
    question_id = _required_text(artifact.get("question_id"), "question_id")
    if question_id != expected_question_id:
        raise QuizValidationError("artifact question_id ownership mismatch")
    kind = _required_text(artifact.get("kind"), "kind")
    if kind not in SUPPORTED_ARTIFACT_KINDS:
        raise QuizValidationError("unsupported artifact kind")
    local_path = _required_text(artifact.get("local_path"), "local_path").replace("\\", "/")
    path_parts = [part for part in local_path.split("/") if part]
    if local_path.startswith("/") or re.match(r"^[A-Za-z]:", local_path) or ".." in path_parts:
        raise QuizValidationError("local_path must be project-relative")
    artifact["local_path"] = local_path
    sha256 = _required_text(artifact.get("sha256"), "sha256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise QuizValidationError("sha256 must contain 64 hex characters")
    artifact["sha256"] = sha256
    size = artifact.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise QuizValidationError("artifact bytes must be positive")
    _required_text(artifact.get("provider"), "provider")
    _required_text(artifact.get("created_at"), "created_at")
    if not isinstance(artifact.get("validation"), dict):
        raise QuizValidationError("artifact validation must be an object")
    return artifact


def retry_quiz_question(
    document: dict[str, Any], question_id: str, *, failed_stage: str, reason: str
) -> dict[str, Any]:
    if failed_stage != "render":
        raise QuizValidationError("unsupported retry stage")
    quiz = validate_quiz_project(document)
    targets = [question for question in quiz["questions"] if question["question_id"] == question_id]
    if len(targets) != 1:
        raise QuizValidationError("retry question_id not found")
    target = targets[0]
    target["ledger"]["attempt_count"] = int(target["ledger"].get("attempt_count") or 0) + 1
    target["ledger"]["status"] = "approved"
    target["ledger"]["render_status"] = "pending"
    target["ledger"]["qc_status"] = "pending"
    target["ledger"]["last_error"] = _required_text(reason, "retry reason")
    target["artifacts"]["question_video"] = None
    target["validation"] = {}
    return quiz


def approve_quiz_project(document: dict[str, Any], *, approved_at: str) -> dict[str, Any]:
    quiz = validate_quiz_project(document)
    fingerprint_source = deepcopy(quiz)
    fingerprint_source.pop("approval", None)
    for question in fingerprint_source["questions"]:
        question.pop("approval_status", None)
        question.pop("content_fingerprint", None)
        question.pop("ledger", None)
        question.pop("artifacts", None)
        question.pop("timing", None)
        question.pop("validation", None)
    payload = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    quiz["approval"] = {
        "status": "approved",
        "approved_at": _required_text(approved_at, "approved_at"),
        "content_fingerprint": fingerprint,
    }
    for question in quiz["questions"]:
        question["approval_status"] = "approved"
        question["content_fingerprint"] = fingerprint
        question["ledger"]["approval_status"] = "approved"
    return quiz
