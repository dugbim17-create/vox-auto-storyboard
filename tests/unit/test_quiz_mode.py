from __future__ import annotations

from copy import deepcopy

import pytest

from app.schemas.quiz import QuizValidationError, validate_quiz_project
from app.services.quiz_timeline import QuizTimelineCompiler


def _quiz(count: int = 30) -> dict:
    questions = []
    for index in range(1, count + 1):
        questions.append(
            {
                "question_id": f"q{index:03d}",
                "order": index,
                "type": "multiple_choice_image",
                "question": f"Câu hỏi địa lý số {index}?",
                "highlight_span": "địa lý",
                "choices": [
                    {"id": "A", "text": f"Đáp án A{index}"},
                    {"id": "B", "text": f"Đáp án B{index}"},
                    {"id": "C", "text": f"Đáp án C{index}"},
                ],
                "correct_choice_id": "B",
                "answer_text": f"Đáp án B{index}",
                "question_voice": f"Câu số {index}. Câu hỏi địa lý số {index}?",
                "answer_voice": f"Đáp án đúng là đáp án B{index}.",
                "countdown_seconds": 10,
                "template_id": "image_left_mcq_right",
                "visual_asset_id": f"asset_q{index:03d}",
                "fact_sources": [f"https://example.test/fact/{index}"],
            }
        )
    return {
        "schema_version": "quiz_project_v1",
        "title": "Quiz địa lý Việt Nam",
        "language": "vi",
        "question_count": count,
        "seconds_per_question": 10,
        "theme_id": "cat_quiz_blue",
        "questions": questions,
        "intro": {"title": "Thử thách địa lý", "rules": ["30 câu hỏi", "10 giây mỗi câu"]},
        "outro": {"title": "Bạn đúng bao nhiêu câu?", "cta": "Bình luận điểm của bạn"},
    }


def test_exact_30_question_quiz_validates() -> None:
    quiz = _quiz()

    validated = validate_quiz_project(quiz)

    assert validated["question_count"] == 30
    assert validated["questions"][-1]["order"] == 30


def test_question_count_must_match_exactly_30() -> None:
    with pytest.raises(QuizValidationError, match="exactly 30"):
        validate_quiz_project(_quiz(29))


def test_correct_choice_and_answer_text_must_agree() -> None:
    quiz = _quiz()
    quiz["questions"][4]["answer_text"] = "Một đáp án khác"

    with pytest.raises(QuizValidationError, match="answer_text"):
        validate_quiz_project(quiz)


def test_choices_are_unique_and_have_one_correct_answer() -> None:
    quiz = _quiz()
    quiz["questions"][0]["choices"][2]["id"] = "B"

    with pytest.raises(QuizValidationError, match="choice ids"):
        validate_quiz_project(quiz)


def test_timeline_compiles_seven_ordered_phases_per_question() -> None:
    quiz = validate_quiz_project(_quiz())

    timeline = QuizTimelineCompiler(fps=30).compile(quiz)

    q1 = timeline.questions[0]
    assert [phase.kind for phase in q1.phases] == [
        "QUESTION_IN",
        "QUESTION_HOLD",
        "COUNTDOWN",
        "TIME_UP",
        "ANSWER_REVEAL",
        "ANSWER_EXPLAIN",
        "QUESTION_OUT",
    ]
    assert q1.phases[2].duration_ms == 10_000
    assert q1.start_ms == timeline.intro.end_ms
    assert timeline.questions[1].start_ms == q1.end_ms


def test_timeline_is_deterministic_for_same_quiz() -> None:
    quiz = validate_quiz_project(_quiz())
    compiler = QuizTimelineCompiler(fps=30)

    first = compiler.compile(quiz).to_dict()
    second = compiler.compile(deepcopy(quiz)).to_dict()

    assert first == second
    assert first["question_count"] == 30
    assert first["frame_count"] == round(first["duration_ms"] / 1000 * 30)


def test_timeline_marks_final_question_and_outro() -> None:
    quiz = validate_quiz_project(_quiz())

    timeline = QuizTimelineCompiler(fps=30).compile(quiz)

    assert timeline.questions[-1].is_final is True
    assert timeline.questions[-1].order == 30
    assert timeline.outro.start_ms == timeline.questions[-1].end_ms
    assert timeline.duration_ms == timeline.outro.end_ms
