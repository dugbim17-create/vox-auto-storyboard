from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.services.quiz_question_unit import (
    QuizQuestionUnitError,
    QuizQuestionUnitRenderer,
)
from app.services.quiz_research import research_quiz_fixture

WAV = Path("tests/fixtures/omnivoice_probe.wav")


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_: Any) -> Any:
        self.calls.append(list(cmd))
        output = Path(cmd[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-audio")

        class Proc:
            returncode = 0
            stderr = ""

        return Proc()


def test_timing_plan_uses_ffprobe_voice_durations() -> None:
    renderer = QuizQuestionUnitRenderer(fps=30)

    plan = renderer.compile_timing(
        question_wav=WAV,
        answer_wav=WAV,
        countdown_seconds=10,
    )

    assert plan.question_voice_duration_ms == 3520
    assert plan.answer_voice_duration_ms == 3520
    assert plan.question_in_ms == 400
    assert plan.question_voice_start_ms == 400
    assert plan.countdown_start_ms == 3920
    assert plan.time_up_start_ms == 13_920
    assert plan.answer_reveal_start_ms == 14_170
    assert plan.answer_voice_start_ms - plan.answer_reveal_start_ms == 80
    assert plan.answer_hold_ms == 4020
    assert plan.question_out_ms == 350
    assert plan.duration_ms % plan.frame_duration_ms == 0


def test_timing_plan_fails_closed_for_missing_or_invalid_audio(tmp_path: Path) -> None:
    renderer = QuizQuestionUnitRenderer(fps=30)

    with pytest.raises(QuizQuestionUnitError, match="question WAV"):
        renderer.compile_timing(
            question_wav=tmp_path / "missing.wav",
            answer_wav=WAV,
            countdown_seconds=10,
        )

    invalid = tmp_path / "invalid.wav"
    invalid.write_bytes(b"not a wav")
    with pytest.raises(QuizQuestionUnitError, match="answer WAV"):
        renderer.compile_timing(
            question_wav=WAV,
            answer_wav=invalid,
            countdown_seconds=10,
        )


def test_countdown_requires_positive_integer() -> None:
    renderer = QuizQuestionUnitRenderer(fps=30)

    with pytest.raises(QuizQuestionUnitError, match="countdown"):
        renderer.compile_timing(question_wav=WAV, answer_wav=WAV, countdown_seconds=0)


def test_audio_graph_delays_voices_sting_and_ducks_bgm(tmp_path: Path) -> None:
    runner = FakeRunner()
    renderer = QuizQuestionUnitRenderer(fps=30, runner=runner)
    sting = tmp_path / "sting.wav"
    bgm = tmp_path / "bgm.wav"
    sting.write_bytes(WAV.read_bytes())
    bgm.write_bytes(WAV.read_bytes())
    timing = renderer.compile_timing(
        question_wav=WAV, answer_wav=WAV, countdown_seconds=10
    )

    output = renderer.build_audio_track(
        question_wav=WAV,
        answer_wav=WAV,
        timing=timing,
        output_path=tmp_path / "unit-audio.m4a",
        answer_sting_path=sting,
        bgm_path=bgm,
    )

    assert output.is_file()
    command = " ".join(runner.calls[0])
    assert "adelay=400|400" in command
    assert f"adelay={timing.answer_voice_start_ms}|{timing.answer_voice_start_ms}" in command
    assert f"adelay={timing.answer_reveal_start_ms}|{timing.answer_reveal_start_ms}" in command
    assert "sidechaincompress" in command
    assert "aloop=loop=-1" in command
    assert f"atrim=0:{timing.duration_ms / 1000:.3f}" in command
    assert "asplit=2[voice_mix][voice_sc]" in command
    assert "[bgm][voice_sc]sidechaincompress" in command
    assert "[voice_mix][sting][ducked]amix=inputs=3" in command
    assert "amix=inputs=3" in command
    assert "-t" in runner.calls[0]


def test_audio_graph_without_bgm_still_mixes_question_answer_and_sting(tmp_path: Path) -> None:
    runner = FakeRunner()
    renderer = QuizQuestionUnitRenderer(runner=runner)
    timing = renderer.compile_timing(
        question_wav=WAV, answer_wav=WAV, countdown_seconds=10
    )

    renderer.build_audio_track(
        question_wav=WAV,
        answer_wav=WAV,
        timing=timing,
        output_path=tmp_path / "unit-audio.m4a",
    )

    command = " ".join(runner.calls[0])
    assert "sidechaincompress" not in command
    assert "amix=inputs=2" in command
    assert "sine=frequency=880" in command


def test_real_question_unit_render_writes_h264_aac_manifest(tmp_path: Path) -> None:
    import json

    payload = json.loads(
        Path("presets/quiz_5_vi_candidates_verified.json").read_text(encoding="utf-8")
    )
    quiz = research_quiz_fixture(payload["questions"], topic=payload["topic"]).project
    renderer = QuizQuestionUnitRenderer(fps=30)

    result = renderer.render(
        quiz_document=quiz,
        question_id="q001",
        question_wav=WAV,
        answer_wav=WAV,
        output_dir=tmp_path,
        countdown_seconds=1,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.output_path.is_file()
    assert result.output_path.stat().st_size > 50_000
    assert manifest["question_id"] == "q001"
    assert manifest["video"]["codec"] == "h264"
    assert manifest["video"]["width"] == 1280
    assert manifest["video"]["height"] == 720
    assert manifest["video"]["fps"] == pytest.approx(30, abs=0.01)
    assert manifest["video"]["pix_fmt"] == "yuv420p"
    assert manifest["audio"]["codec"] == "aac"
    assert manifest["audio"]["sample_rate"] == 48_000
    assert manifest["audio"]["channels"] == 2
    assert abs(manifest["duration_ms"] - manifest["timing"]["duration_ms"]) <= 34
    assert 0 <= (
        manifest["timing"]["answer_voice_start_ms"]
        - manifest["timing"]["answer_reveal_start_ms"]
    ) <= 120
    assert manifest["provider_calls"] == 0
    assert manifest["tts_calls"] == 0
    assert len(manifest["sha256"]) == 64


def test_render_manifest_records_injected_live_tts_provenance(tmp_path: Path) -> None:
    import json

    payload = json.loads(
        Path("presets/quiz_5_vi_candidates_verified.json").read_text(encoding="utf-8")
    )
    quiz = research_quiz_fixture(payload["questions"], topic=payload["topic"]).project

    result = QuizQuestionUnitRenderer(fps=30).render(
        quiz_document=quiz,
        question_id="q001",
        question_wav=WAV,
        answer_wav=WAV,
        output_dir=tmp_path,
        countdown_seconds=1,
        provider_calls=2,
        tts_calls=2,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["provider_calls"] == 2
    assert manifest["tts_calls"] == 2
