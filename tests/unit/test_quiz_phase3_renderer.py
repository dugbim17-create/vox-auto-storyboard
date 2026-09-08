from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from app.services.quiz_renderer import QuizOfflineRenderer, QuizRenderError, QuizRenderState
from app.services.quiz_research import research_quiz_fixture
from app.services.quiz_timeline import QuizTimelineCompiler


def pilot_quiz() -> dict:
    payload = json.loads(
        Path("presets/quiz_5_vi_candidates_verified.json").read_text(encoding="utf-8")
    )
    return research_quiz_fixture(payload["questions"], topic=payload["topic"]).project


def test_five_question_badge_uses_dynamic_total() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = pilot_quiz()

    _frame, layout = renderer.render_frame_with_layout(
        quiz,
        QuizRenderState(kind="QUESTION", question=quiz["questions"][0], progress=0.0),
    )

    assert layout["badge_text"] == "CÂU 1/5"


def test_render_plan_separates_countdown_and_time_up_for_each_question() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = pilot_quiz()
    timeline = QuizTimelineCompiler(fps=30).compile(quiz)

    plan = renderer.build_render_plan(quiz, timeline)

    assert len([segment for segment in plan if segment.state.kind == "QUESTION"]) == 5
    assert len([segment for segment in plan if segment.state.kind == "COUNTDOWN"]) == 5
    assert len([segment for segment in plan if segment.state.kind == "TIME_UP"]) == 5
    assert len([segment for segment in plan if segment.state.kind == "REVEAL"]) == 5
    countdown = next(segment for segment in plan if segment.state.kind == "COUNTDOWN")
    time_up = next(segment for segment in plan if segment.state.kind == "TIME_UP")
    assert countdown.duration_ms == 10_000
    assert countdown.state.progress == 0.5
    assert time_up.duration_ms == 250
    assert time_up.state.progress == 0.0
    assert time_up.start_ms == countdown.start_ms + countdown.duration_ms


def test_time_up_frame_has_distinct_visual_marker() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = pilot_quiz()
    question = quiz["questions"][0]

    countdown, countdown_layout = renderer.render_frame_with_layout(
        quiz, QuizRenderState(kind="COUNTDOWN", question=question, progress=0.5)
    )
    time_up, time_up_layout = renderer.render_frame_with_layout(
        quiz, QuizRenderState(kind="TIME_UP", question=question, progress=0.0)
    )

    assert countdown.tobytes() != time_up.tobytes()
    assert countdown_layout["time_up_text"] is None
    assert time_up_layout["time_up_text"] == "HẾT GIỜ"
    assert time_up_layout["answer_box"] is None


def test_question_state_draws_no_cyan_progress_pixel_at_zero() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = pilot_quiz()

    frame = renderer.render_frame(
        quiz,
        QuizRenderState(kind="QUESTION", question=quiz["questions"][0], progress=0.0),
    )

    assert frame.getpixel((180, 673)) != renderer.theme.timer


def test_legacy_thirty_question_badge_remains_dynamic() -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz = json.loads(Path("presets/quiz_30_vi_fixture.json").read_text(encoding="utf-8"))

    _frame, layout = renderer.render_frame_with_layout(
        quiz,
        QuizRenderState(kind="QUESTION", question=quiz["questions"][29], progress=0.0),
    )

    assert layout["badge_text"] == "CÂU 30/30"


def test_local_visual_fixture_is_decoded_inside_owned_asset_root(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    visual_path = asset_root / "q001" / "visual.png"
    visual_path.parent.mkdir(parents=True)
    Image.new("RGB", (640, 480), (14, 120, 210)).save(visual_path)
    renderer = QuizOfflineRenderer(
        width=1280, height=720, fps=30, asset_root=asset_root
    )
    quiz = pilot_quiz()
    quiz["questions"][0]["visual"] = {"local_path": "q001/visual.png", "crop": "contain"}

    frame, layout = renderer.render_frame_with_layout(
        quiz,
        QuizRenderState(kind="QUESTION", question=quiz["questions"][0]),
    )

    assert frame.size == (1280, 720)
    assert layout["visual_box"] is not None
    assert layout["visual_source_size"] == [640, 480]
    assert layout["visual_box"][2] <= layout["question_box"][0]


def test_visual_fixture_missing_corrupt_or_outside_root_fails_closed(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    renderer = QuizOfflineRenderer(asset_root=asset_root)
    quiz = pilot_quiz()
    question = quiz["questions"][0]

    for local_path, expected in (
        ("missing.png", "missing"),
        ("../escape.png", "project-relative"),
    ):
        question["visual"] = {"local_path": local_path, "crop": "contain"}
        with pytest.raises(QuizRenderError, match=expected):
            renderer.render_frame(quiz, QuizRenderState(kind="QUESTION", question=question))

    corrupt = asset_root / "corrupt.png"
    corrupt.write_text("not an image", encoding="utf-8")
    question["visual"] = {"local_path": "corrupt.png", "crop": "contain"}
    with pytest.raises(QuizRenderError, match="decode"):
        renderer.render_frame(quiz, QuizRenderState(kind="QUESTION", question=question))


def test_frame_probe_bundle_writes_four_states_for_all_five_questions(tmp_path: Path) -> None:
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)

    result = renderer.render_frame_probes(pilot_quiz(), tmp_path)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert len(result.frame_paths) == 20
    assert manifest["question_count"] == 5
    assert manifest["state_count"] == 20
    assert manifest["provider_calls"] == 0
    assert manifest["tts_calls"] == 0
    assert manifest["render_calls"] == 0
    assert {item["state"] for item in manifest["frames"]} == {
        "QUESTION",
        "COUNTDOWN",
        "TIME_UP",
        "REVEAL",
    }
    for item in manifest["frames"]:
        path = tmp_path / item["relative_path"]
        assert path.is_file()
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        with Image.open(path) as frame:
            frame.load()
            assert frame.size == (1280, 720)
        assert item["layout"]["question"]["overflow"] is False
        assert item["layout"]["choices_box"][3] <= 720
    assert not list(tmp_path.rglob("*.partial"))


def test_frame_probe_bundle_hard_blocks_overflow_before_manifest(tmp_path: Path) -> None:
    quiz = pilot_quiz()
    quiz["questions"][0]["question"] = " ".join(["nội dung rất dài"] * 100)
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)

    with pytest.raises(QuizRenderError, match="blocked_overflow"):
        renderer.render_frame_probes(quiz, tmp_path)

    assert not (tmp_path / "frame-probes.json").exists()
