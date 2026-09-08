from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.quiz import validate_quiz_project

PHASE_KINDS = (
    "QUESTION_IN",
    "QUESTION_HOLD",
    "COUNTDOWN",
    "TIME_UP",
    "ANSWER_REVEAL",
    "ANSWER_EXPLAIN",
    "QUESTION_OUT",
)


@dataclass(frozen=True)
class QuizPhase:
    kind: str
    start_ms: int
    duration_ms: int

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "end_ms": self.end_ms,
        }


@dataclass(frozen=True)
class QuizQuestionTimeline:
    question_id: str
    order: int
    start_ms: int
    phases: tuple[QuizPhase, ...]
    is_final: bool = False

    @property
    def end_ms(self) -> int:
        return self.phases[-1].end_ms

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "order": self.order,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "is_final": self.is_final,
            "phases": [phase.to_dict() for phase in self.phases],
        }


@dataclass(frozen=True)
class QuizSectionTimeline:
    kind: str
    start_ms: int
    duration_ms: int

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "end_ms": self.end_ms,
        }


@dataclass(frozen=True)
class QuizTimeline:
    fps: int
    intro: QuizSectionTimeline
    questions: tuple[QuizQuestionTimeline, ...]
    outro: QuizSectionTimeline

    @property
    def duration_ms(self) -> int:
        return self.outro.end_ms

    @property
    def frame_count(self) -> int:
        return round(self.duration_ms / 1000 * self.fps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fps": self.fps,
            "question_count": len(self.questions),
            "duration_ms": self.duration_ms,
            "frame_count": self.frame_count,
            "intro": self.intro.to_dict(),
            "questions": [question.to_dict() for question in self.questions],
            "outro": self.outro.to_dict(),
        }


class QuizTimelineCompiler:
    """Compile approved quiz data into deterministic render phases."""

    def __init__(
        self,
        *,
        fps: int = 30,
        intro_ms: int = 7_000,
        question_in_ms: int = 500,
        question_hold_ms: int = 1_000,
        time_up_ms: int = 250,
        answer_reveal_ms: int = 500,
        answer_explain_ms: int = 2_500,
        question_out_ms: int = 250,
        outro_ms: int = 5_000,
    ) -> None:
        if fps < 1:
            raise ValueError("fps must be positive")
        self.fps = fps
        self.intro_ms = intro_ms
        self.phase_durations = {
            "QUESTION_IN": question_in_ms,
            "QUESTION_HOLD": question_hold_ms,
            "TIME_UP": time_up_ms,
            "ANSWER_REVEAL": answer_reveal_ms,
            "ANSWER_EXPLAIN": answer_explain_ms,
            "QUESTION_OUT": question_out_ms,
        }
        self.outro_ms = outro_ms

    def compile(self, quiz_document: dict[str, Any]) -> QuizTimeline:
        quiz = validate_quiz_project(quiz_document)
        intro = QuizSectionTimeline("INTRO", 0, self.intro_ms)
        cursor = intro.end_ms
        questions: list[QuizQuestionTimeline] = []
        for raw in quiz["questions"]:
            phase_cursor = cursor
            phases: list[QuizPhase] = []
            for kind in PHASE_KINDS:
                duration = (
                    int(raw["countdown_seconds"]) * 1000
                    if kind == "COUNTDOWN"
                    else self.phase_durations[kind]
                )
                phase = QuizPhase(kind, phase_cursor, duration)
                phases.append(phase)
                phase_cursor = phase.end_ms
            question = QuizQuestionTimeline(
                question_id=str(raw["question_id"]),
                order=int(raw["order"]),
                start_ms=cursor,
                phases=tuple(phases),
                is_final=int(raw["order"]) == len(quiz["questions"]),
            )
            questions.append(question)
            cursor = question.end_ms
        outro = QuizSectionTimeline("OUTRO", cursor, self.outro_ms)
        return QuizTimeline(
            fps=self.fps,
            intro=intro,
            questions=tuple(questions),
            outro=outro,
        )
