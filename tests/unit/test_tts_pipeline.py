"""Tests for P3-T05 TTS scene pipeline.

Covers the acceptance criteria:

- tất cả scene có WAV;
- actual duration cập nhật;
- rerun dùng cache (narration unchanged -> no synthesize call);
- thay narration chỉ regenerate scene đó (changed scene only).
"""

from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from app.providers.base import TTSRequest, TTSResult, TTSWordTiming
from app.services.tts_pipeline import (
    TTSScenePipeline,
    sha256_text,
    sha256_tts_request,
)
from app.storage import database
from app.storage.asset_store import AssetStore
from app.storage.repositories import ProjectRepo, SceneRepo


def write_wav(path: Path, *, samples: int) -> None:
    sample_rate = 24000
    bits = 16
    channels = 1
    block_align = channels * bits // 8
    byte_rate = sample_rate * block_align
    data_size = samples * block_align
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE" + b"fmt "
    header += struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
    header += b"data" + struct.pack("<I", data_size)
    path.write_bytes(header + b"\x00\x00" * samples)


class FakeTTS:
    def __init__(self, duration_ms: int = 3000) -> None:
        self.calls: list[str] = []
        self.requests: list[TTSRequest] = []
        self.duration_ms = duration_ms

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        self.calls.append(request.segment_id)
        self.requests.append(request)
        path = Path(request.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_wav(path, samples=self.duration_ms * 24)  # 24 samples per ms
        return TTSResult(
            wav_path=str(path),
            duration_ms=self.duration_ms,
            sample_rate=24000,
            channels=1,
            provider="omnivoice",
        )


@pytest.fixture()
def session(tmp_path: Path):
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/test.db")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    with factory() as s:
        yield s
    database.reset_engine()


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    return tmp_path / "projects"


def seed_project(session, project_id: str = "prj_tts") -> None:
    ProjectRepo.create(session, project_id=project_id, title="TTS")
    for order in (1, 2, 3):
        SceneRepo.add(
            session,
            project_id,
            scene_id=f"scene_{order:03d}",
            order=order,
            narration_text=f"Nội dung scene {order}.",
            status="PLANNED",
        )
    session.commit()


def run(coro):
    return asyncio.run(coro)


def test_all_scenes_have_wav(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    pipeline = TTSScenePipeline(fake)
    result = run(pipeline.run("prj_tts", session, project_root=project_root))

    assert result.total_scenes == 3
    assert result.generated == 3
    assert result.cached == 0
    assert result.errors == []
    assert fake.calls == ["scene_001", "scene_002", "scene_003"]

    # Every scene has a WAV file on disk.
    store = AssetStore(project_root)
    wavs = list(store.subdir("prj_tts", "audio").glob("*.wav"))
    assert len(wavs) == 3


def test_actual_duration_updated(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    run(TTSScenePipeline(fake).run("prj_tts", session, project_root=project_root))

    for scene in SceneRepo.list(session, "prj_tts"):
        assert scene.actual_voice_duration_ms == 3000.0


def test_rerun_uses_cache(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    pipeline = TTSScenePipeline(fake)
    first = run(pipeline.run("prj_tts", session, project_root=project_root))
    assert first.generated == 3

    # Second run: narration unchanged -> all cached, no synthesize calls.
    fake.calls.clear()
    second = run(pipeline.run("prj_tts", session, project_root=project_root))
    assert second.generated == 0
    assert second.cached == 3
    assert fake.calls == []


def test_changed_narration_regenerates_only_that_scene(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    pipeline = TTSScenePipeline(fake)
    run(pipeline.run("prj_tts", session, project_root=project_root))

    # Change narration of scene_002 only.
    scene2 = SceneRepo.get(session, "prj_tts", "scene_002")
    scene2.narration_text = "Nội dung scene 2 đã thay đổi."
    session.commit()

    fake.calls.clear()
    run(pipeline.run("prj_tts", session, project_root=project_root))
    assert fake.calls == ["scene_002"]  # only changed scene regenerated


def test_cache_key_derived_from_narration() -> None:
    assert sha256_text("Xin chào") != sha256_text("Xin chào 2")


def test_tts_cache_key_includes_voice_identity_and_parameters() -> None:
    base = {
        "text_normalized": "Xin chào", "voice_profile_id": "voice_a", "language": "vi",
        "reference_audio_hash": "ref-a", "seed": 42, "speed": 1.0,
        "provider_params": {"temperature": 0.2},
    }

    assert sha256_tts_request(**base) != sha256_tts_request(
        **{**base, "voice_profile_id": "voice_b"}
    )
    assert sha256_tts_request(**base) != sha256_tts_request(
        **{**base, "reference_audio_hash": "ref-b"}
    )
    assert sha256_tts_request(**base) != sha256_tts_request(
        **{**base, "provider_params": {"temperature": 0.8}}
    )


def test_corrupt_cache_is_not_reused(tmp_path, session, project_root) -> None:
    seed_project(session)
    store = AssetStore(project_root)
    audio_dir = store.subdir("prj_tts", "audio")
    key = sha256_tts_request(
        text_normalized="Nội dung scene 1.",
        voice_profile_id="voice_vi_01",
        language="vi",
        reference_audio_hash="",
        seed=42,
        speed=1.0,
        provider_params={},
    )[:12]
    (audio_dir / f"scene_001_{key}.wav").write_bytes(b"corrupt")

    fake = FakeTTS()
    result = run(TTSScenePipeline(fake).run("prj_tts", session, project_root=project_root))

    assert result.generated == 3
    assert fake.calls == ["scene_001", "scene_002", "scene_003"]


def test_profile_identity_is_passed_to_tts_request(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    pipeline = TTSScenePipeline(
        fake,
        voice_profile_id="voice_custom",
        reference_audio_path="voices/reference.wav",
        seed=99,
        speed=0.9,
        provider_params={"style": "calm"},
    )

    run(pipeline.run("prj_tts", session, project_root=project_root))

    assert fake.requests[0].voice_profile_id == "voice_custom"
    assert fake.requests[0].reference_audio_path == "voices/reference.wav"
    assert fake.requests[0].seed == 99
    assert fake.requests[0].speed == 0.9
    assert fake.requests[0].provider_params == {"style": "calm"}


def test_result_exposes_scene_audio_in_order(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    result = run(TTSScenePipeline(fake).run("prj_tts", session, project_root=project_root))

    assert [Path(path).name for path in result.audio_paths] == [
        "scene_001_" + Path(result.audio_paths[0]).name.split("_", 2)[2],
        "scene_002_" + Path(result.audio_paths[1]).name.split("_", 2)[2],
        "scene_003_" + Path(result.audio_paths[2]).name.split("_", 2)[2],
    ]
    assert [item.scene_id for item in result.scene_results] == [
        "scene_001",
        "scene_002",
        "scene_003",
    ]


def test_result_exposes_canonical_measured_voice_timeline(tmp_path, session, project_root) -> None:
    seed_project(session)

    class TimedTTS(FakeTTS):
        async def synthesize(self, request: TTSRequest) -> TTSResult:
            result = await super().synthesize(request)
            result.word_timings = (
                TTSWordTiming(text="Nội", start_ms=100, end_ms=400),
                TTSWordTiming(text="dung", start_ms=450, end_ms=850),
                TTSWordTiming(text="scene", start_ms=900, end_ms=1300),
                TTSWordTiming(text=request.segment_id[-1], start_ms=1350, end_ms=1700),
            )
            return result

    result = run(
        TTSScenePipeline(TimedTTS()).run("prj_tts", session, project_root=project_root)
    )
    timeline = result.scene_results[0].voice_timeline(fps=30)

    assert timeline.scene_id == "scene_001"
    assert timeline.duration_ms == 3000
    assert [(word.text, word.start_ms, word.end_ms) for word in timeline.words] == [
        ("Nội", 100, 400),
        ("dung", 450, 850),
        ("scene", 900, 1300),
        ("1", 1350, 1700),
    ]


def test_cached_audio_retains_measured_word_timings(tmp_path, session, project_root) -> None:
    seed_project(session)

    class TimedTTS(FakeTTS):
        async def synthesize(self, request: TTSRequest) -> TTSResult:
            result = await super().synthesize(request)
            result.word_timings = (
                TTSWordTiming(text="Nội", start_ms=100, end_ms=400),
                TTSWordTiming(text="dung", start_ms=450, end_ms=850),
                TTSWordTiming(text="scene", start_ms=900, end_ms=1300),
                TTSWordTiming(text=request.segment_id[-1], start_ms=1350, end_ms=1700),
            )
            return result

    fake = TimedTTS()
    pipeline = TTSScenePipeline(fake)
    first = run(pipeline.run("prj_tts", session, project_root=project_root))
    fake.calls.clear()
    second = run(pipeline.run("prj_tts", session, project_root=project_root))

    assert fake.calls == []
    assert second.scene_results[0].voice_timeline(fps=30) == first.scene_results[0].voice_timeline(
        fps=30
    )


def test_pipeline_uses_acoustic_aligner_when_provider_has_no_word_timings(
    tmp_path, session, project_root
) -> None:
    seed_project(session)
    calls: list[tuple[str, str, int]] = []

    class Aligner:
        def align(self, wav_path: Path, text: str, duration_ms: int):
            calls.append((wav_path.name, text, duration_ms))
            return (
                TTSWordTiming(text="Nội", start_ms=100, end_ms=400),
                TTSWordTiming(text="dung", start_ms=450, end_ms=850),
                TTSWordTiming(text="scene", start_ms=900, end_ms=1300),
                TTSWordTiming(text=text.split()[-1].rstrip("."), start_ms=1350, end_ms=1700),
            )

    result = run(
        TTSScenePipeline(FakeTTS(), word_aligner=Aligner()).run(
            "prj_tts", session, project_root=project_root
        )
    )

    assert len(calls) == 3
    assert [word.text for word in result.scene_results[0].voice_timeline(fps=30).words] == [
        "Nội",
        "dung",
        "scene",
        "1",
    ]


def test_materialize_audio_requires_complete_scene_cardinality(tmp_path, session, project_root) -> None:
    seed_project(session)
    fake = FakeTTS()
    pipeline = TTSScenePipeline(fake)
    result = run(pipeline.run("prj_tts", session, project_root=project_root))
    result.scene_results.pop()

    with pytest.raises(Exception, match="cardinality mismatch"):
        pipeline.materialize_audio(result, project_root / "combined.wav")


def test_empty_narration_raises(tmp_path, session, project_root) -> None:
    ProjectRepo.create(session, project_id="prj_empty", title="Empty")
    SceneRepo.add(session, "prj_empty", scene_id="scene_001", order=1, narration_text="", status="PLANNED")
    session.commit()
    fake = FakeTTS()
    pipeline = TTSScenePipeline(fake)
    result = run(pipeline.run("prj_empty", session, project_root=project_root))
    assert len(result.errors) == 1
    assert "empty narration" in result.errors[0]
