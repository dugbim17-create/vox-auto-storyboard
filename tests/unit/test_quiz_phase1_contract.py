from __future__ import annotations

from copy import deepcopy

import pytest

from app.schemas.quiz import (
    QuizValidationError,
    approve_quiz_project,
    retry_quiz_question,
    validate_quiz_artifact,
    validate_quiz_project,
)


def quiz_fixture(count: int = 5) -> dict:
    questions = []
    for index in range(1, count + 1):
        questions.append(
            {
                "question_id": f"q{index:03d}",
                "order": index,
                "type": "multiple_choice_image",
                "difficulty": "easy",
                "question": f"Câu hỏi số {index}?",
                "choices": [
                    {"id": "A", "text": f"Sai A{index}"},
                    {"id": "B", "text": f"Đúng B{index}"},
                    {"id": "C", "text": f"Sai C{index}"},
                ],
                "correct_choice_id": "B",
                "answer_text": f"Đúng B{index}",
                "question_voice": f"Câu hỏi số {index}?",
                "answer_voice": f"Đáp án là Đúng B{index}.",
                "countdown_seconds": 10,
                "template_id": "image_left_mcq_right",
                "time_sensitive": False,
                "as_of_date": None,
                "fact_sources": [
                    {
                        "source_id": f"src_{index}",
                        "title": "Nguồn chính thống",
                        "url": f"https://example.test/{index}",
                        "publisher": "Example Authority",
                        "accessed_at": "2026-08-10T00:00:00Z",
                        "claim_supported": f"Đúng B{index}",
                    }
                ],
            }
        )
    return {
        "schema_version": "quiz_project_v1",
        "project_id": "quiz_pilot_001",
        "title": "Pilot 5 câu",
        "topic": "Địa lý Việt Nam",
        "language": "vi",
        "target_question_count": count,
        "question_count": count,
        "seconds_per_question": 10,
        "difficulty": "mixed",
        "audience": "general",
        "theme_id": "vox_quiz_01",
        "voice_profile_id": "voice_vi_01",
        "bgm_id": "quiz_upbeat_01",
        "approval": {"status": "draft", "approved_at": None, "content_fingerprint": None},
        "questions": questions,
    }


def test_five_question_pilot_gets_canonical_defaults() -> None:
    validated = validate_quiz_project(quiz_fixture())

    assert validated["target_question_count"] == 5
    assert len(validated["questions"]) == 5
    first = validated["questions"][0]
    assert first["approval_status"] == "draft"
    assert first["ledger"]["status"] == "planned"
    assert first["ledger"]["attempt_count"] == 0
    assert first["artifacts"] == {
        "question_audio": None,
        "answer_audio": None,
        "visual": None,
        "question_video": None,
    }


def test_declared_count_must_match_actual_questions() -> None:
    document = quiz_fixture()
    document["questions"].pop()

    with pytest.raises(QuizValidationError, match="target_question_count"):
        validate_quiz_project(document)


def test_validation_does_not_mutate_input() -> None:
    document = quiz_fixture()
    before = deepcopy(document)

    validate_quiz_project(document)

    assert document == before


def test_time_sensitive_question_requires_as_of_date() -> None:
    document = quiz_fixture()
    document["questions"][0]["time_sensitive"] = True

    with pytest.raises(QuizValidationError, match="as_of_date"):
        validate_quiz_project(document)


def test_source_record_requires_claim_and_access_date() -> None:
    document = quiz_fixture()
    del document["questions"][0]["fact_sources"][0]["claim_supported"]

    with pytest.raises(QuizValidationError, match="claim_supported"):
        validate_quiz_project(document)


def test_near_duplicate_question_text_is_rejected() -> None:
    document = quiz_fixture()
    document["questions"][1]["question"] = "  CÂU   HỎI số 1?  "

    with pytest.raises(QuizValidationError, match="duplicate question"):
        validate_quiz_project(document)


def test_answer_voice_must_contain_answer_text() -> None:
    document = quiz_fixture()
    document["questions"][0]["answer_voice"] = "Đáp án là một nội dung khác."

    with pytest.raises(QuizValidationError, match="answer_voice"):
        validate_quiz_project(document)


def test_approval_fingerprint_is_deterministic_and_marks_questions() -> None:
    first = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")
    second = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")

    assert first["approval"]["status"] == "approved"
    assert first["approval"]["content_fingerprint"] == second["approval"]["content_fingerprint"]
    assert len(first["approval"]["content_fingerprint"]) == 64
    assert all(question["approval_status"] == "approved" for question in first["questions"])


def test_artifact_record_requires_owned_relative_path_and_sha256() -> None:
    record = validate_quiz_artifact(
        {
            "artifact_id": "q001_question_audio_v001",
            "question_id": "q001",
            "kind": "question_audio",
            "local_path": "audio/q001/question.wav",
            "sha256": "a" * 64,
            "bytes": 1234,
            "provider": "local",
            "provider_request_id": None,
            "created_at": "2026-08-10T00:00:00Z",
            "validation": {"duration": 2.1},
        },
        expected_question_id="q001",
    )

    assert record["kind"] == "question_audio"
    with pytest.raises(QuizValidationError, match="local_path"):
        validate_quiz_artifact({**record, "local_path": "../escape.wav"}, expected_question_id="q001")
    with pytest.raises(QuizValidationError, match="sha256"):
        validate_quiz_artifact({**record, "sha256": "bad"}, expected_question_id="q001")


def test_retry_render_resets_only_target_render_dependencies() -> None:
    document = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")
    for question in document["questions"]:
        question["ledger"].update({"status": "validated", "render_status": "validated", "qc_status": "passed"})
        question["artifacts"]["visual"] = {"artifact_id": f"{question['question_id']}_visual"}
        question["artifacts"]["question_audio"] = {"artifact_id": f"{question['question_id']}_question_audio"}
        question["artifacts"]["answer_audio"] = {"artifact_id": f"{question['question_id']}_answer_audio"}
        question["artifacts"]["question_video"] = {"artifact_id": f"{question['question_id']}_video"}
    unaffected_before = deepcopy([document["questions"][0], document["questions"][1], *document["questions"][3:]])

    retried = retry_quiz_question(document, "q003", failed_stage="render", reason="frame probe failed")

    unaffected_after = [retried["questions"][0], retried["questions"][1], *retried["questions"][3:]]
    assert unaffected_after == unaffected_before
    target = retried["questions"][2]
    assert target["ledger"]["attempt_count"] == 1
    assert target["ledger"]["render_status"] == "pending"
    assert target["ledger"]["qc_status"] == "pending"
    assert target["artifacts"]["question_video"] is None
    assert target["artifacts"]["visual"] is not None
    assert target["artifacts"]["question_audio"] is not None
