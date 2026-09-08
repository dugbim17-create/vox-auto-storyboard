from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from app.services.quiz_renderer import QuizOfflineRenderer, QuizRenderState
from app.services.quiz_timeline import QuizTimelineCompiler

FIXTURE = Path("presets/quiz_30_vi_fixture.json")


def _quiz() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_question_and_reveal_frames_use_distinct_answer_states(tmp_path: Path) -> None:
    renderer = QuizOfflineRenderer(width=640, height=360, fps=10)
    quiz = _quiz()
    question = quiz["questions"][0]

    question_frame = renderer.render_frame(
        quiz, QuizRenderState(kind="QUESTION", question=question, progress=0.5)
    )
    reveal_frame = renderer.render_frame(
        quiz, QuizRenderState(kind="REVEAL", question=question, progress=1.0)
    )

    assert question_frame.size == (640, 360)
    assert reveal_frame.size == (640, 360)
    assert question_frame.getpixel(renderer.choice_probe_point(0)) != renderer.theme.success
    assert reveal_frame.getpixel(renderer.choice_probe_point(0)) == renderer.theme.success
    assert reveal_frame.getpixel(renderer.choice_probe_point(1)) == renderer.theme.wrong_dim
    assert reveal_frame.getpixel(renderer.choice_probe_point(2)) == renderer.theme.wrong_dim
    question_frame.save(tmp_path / "question.png")
    reveal_frame.save(tmp_path / "reveal.png")


def test_vietnamese_primary_text_fits_without_overflow() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = _quiz()

    frame, layout = renderer.render_frame_with_layout(
        quiz,
        QuizRenderState(kind="QUESTION", question=quiz["questions"][29], progress=0.5),
    )

    assert isinstance(frame, Image.Image)
    assert layout["question"]["overflow"] is False
    assert layout["question"]["line_count"] <= 3
    assert layout["question"]["font_size"] >= 38
    assert all(choice["overflow"] is False for choice in layout["choices"])
    assert all(choice["line_count"] <= 2 for choice in layout["choices"])
    assert all(choice["font_size"] >= 30 for choice in layout["choices"])


def test_long_question_reserves_space_between_badge_choices_and_answer() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = _quiz()

    _frame, layout = renderer.render_frame_with_layout(
        quiz,
        QuizRenderState(kind="REVEAL", question=quiz["questions"][29], progress=1.0),
    )

    assert layout["badge_box"][3] + 8 <= layout["question_box"][1]
    assert layout["question_box"][3] + 8 <= layout["choices_box"][1]
    assert layout["choices_box"][3] + 12 <= layout["answer_box"][1]


def test_render_plan_contains_intro_all_30_questions_reveals_and_outro() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = _quiz()
    timeline = QuizTimelineCompiler(fps=30).compile(quiz)

    plan = renderer.build_render_plan(quiz, timeline)

    assert plan[0].state.kind == "INTRO"
    assert plan[-1].state.kind == "OUTRO"
    assert len([item for item in plan if item.state.kind == "QUESTION"]) == 30
    assert len([item for item in plan if item.state.kind == "COUNTDOWN"]) == 30
    assert len([item for item in plan if item.state.kind == "REVEAL"]) == 30
    assert [item.state.question["order"] for item in plan if item.state.kind == "REVEAL"] == list(range(1, 31))


def test_offline_render_writes_mp4_probe_and_hash_manifest(tmp_path: Path) -> None:
    renderer = QuizOfflineRenderer(width=320, height=180, fps=10)
    compiler = QuizTimelineCompiler(
        fps=10,
        intro_ms=100,
        question_in_ms=50,
        question_hold_ms=50,
        time_up_ms=50,
        answer_reveal_ms=50,
        answer_explain_ms=50,
        question_out_ms=50,
        outro_ms=100,
    )
    quiz = _quiz()
    for question in quiz["questions"]:
        question["countdown_seconds"] = 1
    quiz["seconds_per_question"] = 1

    result = renderer.render(quiz, tmp_path, compiler=compiler, audio_policy="synthetic_sine")

    assert result.output_path.is_file()
    assert result.output_path.stat().st_size > 10_000
    assert result.manifest_path.is_file()
    assert result.probe_path.is_file()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    probe = json.loads(result.probe_path.read_text(encoding="utf-8"))
    assert manifest["question_count"] == 30
    assert manifest["sha256"] == result.sha256
    assert manifest["provider_calls"] == 0
    assert manifest["audio_policy"] == "synthetic_sine"
    assert probe["video"]["width"] == 320
    assert probe["video"]["height"] == 180
    assert abs(probe["video"]["fps"] - 10) < 0.01
    assert probe["audio"]["present"] is True
    assert probe["format"]["duration_ms"] == manifest["duration_ms"]


def test_fixture_is_exactly_30_questions_and_has_long_vietnamese_case() -> None:
    quiz = _quiz()

    assert quiz["question_count"] == 30
    assert len(quiz["questions"]) == 30
    assert "Việt Nam" in quiz["questions"][29]["question"]
    assert max(len(question["question"]) for question in quiz["questions"]) >= 70


def test_cli_registers_additive_render_quiz_command() -> None:
    from app.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["render-quiz", "--quiz", "quiz.json", "--output-dir", "out"])

    assert args.command == "render-quiz"
    assert args.quiz == "quiz.json"
    assert args.output_dir == "out"
    assert args.audio_policy == "synthetic_sine"


def test_generic_storyboard_limit_remains_20() -> None:
    schema = json.loads(Path("app/schemas/storyboard.schema.json").read_text(encoding="utf-8"))

    assert schema["properties"]["scenes"]["maxItems"] == 20
    assert schema["properties"]["scenes"]["minItems"] == 4


def test_four_choices_render_without_index_error() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = {
        "schema_version": "quiz_project_v1",
        "title": "Thử thách 4 đáp án",
        "language": "vi",
        "question_count": 1,
        "target_question_count": 1,
        "seconds_per_question": 2,
        "theme_id": "vox_quiz_01",
        "questions": [
            {
                "question_id": "q001",
                "order": 1,
                "type": "multiple_choice_text",
                "template_id": "text_mcq",
                "question": "90 : 9 + 5 = ?",
                "choices": [
                    {"id": "A", "text": "10"},
                    {"id": "B", "text": "15"},
                    {"id": "C", "text": "20"},
                    {"id": "D", "text": "25"},
                ],
                "correct_choice_id": "B",
                "answer_text": "15",
                "question_voice": "90 chia 9 cộng 5 bằng bao nhiêu?",
                "answer_voice": "Đáp án đúng là 15.",
                "fact_sources": ["math_truth"],
                "countdown_seconds": 2,
            }
        ],
    }
    q_state = QuizRenderState(kind="QUESTION", question=quiz["questions"][0], progress=0.5)
    frame_q, layout_q = renderer.render_frame_with_layout(quiz, q_state)
    assert len(layout_q["choices"]) == 4
    assert layout_q["choices_box"][1] > layout_q["question_box"][3]

    rev_state = QuizRenderState(kind="REVEAL", question=quiz["questions"][0], progress=1.0)
    frame_r, layout_r = renderer.render_frame_with_layout(quiz, rev_state)
    assert len(layout_r["choices"]) == 4
    assert layout_r["answer_box"] is not None
