"""Tests for P2-T06 ProjectManager + Storyboard CLI helpers.

Covers the acceptance criteria:

- tạo storyboard.json;
- DB có scenes;
- status đúng;
- chạy lần hai không duplicate nếu input không đổi.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.project_manager import (
    ProjectManager,
    ProjectManagerError,
    generate_project_id,
    sha256_text,
)
from app.services.prompts import get_prompt_pack
from app.services.script_analysis import ScriptAnalyzer
from app.storage import database
from app.storage.asset_store import AssetStore
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo, StateEventRepo


class FakePlanner:
    """Deterministic fake LLM that returns a fixed valid storyboard."""

    def __init__(self, storyboard: dict) -> None:
        self.storyboard = storyboard
        self.prompt_pack = get_prompt_pack()
        self.calls = 0

    async def generate_json(self, **_: Any) -> dict:
        self.calls += 1
        return self.storyboard


def make_scene(order: int) -> dict:
    return {
        "scene_id": f"scene_{order:03d}",
        "order": order,
        "script_span": {
            "start_char": (order - 1) * 10,
            "end_char": order * 10,
        },
        "narration_text": f"Scene {order}.",
        "purpose": "body",
        "estimated_duration_seconds": 5.0,
        "visual_summary": f"Visual {order}.",
        "image_prompt": f"Image prompt {order}.",
        "negative_constraints": ["no text"],
        "motion_prompt": "subtle zoom",
        "motion_template": "01_subject_slide_headline_pop",
        "transition_out": "hard_cut",
    }


def make_storyboard(scene_count: int = 5) -> dict:
    return {
        "summary": "Demo project.",
        "style_anchor": {
            "visual_language": "editorial paper collage",
            "palette": ["off-white", "black"],
            "texture": ["paper grain"],
            "typography": "bold sans",
            "continuity_rules": [],
        },
        "characters": [{"name": "Host"}],
        "locations": [{"name": "Studio"}],
        "scenes": [make_scene(i) for i in range(1, scene_count + 1)],
    }


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


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# create-project
# --------------------------------------------------------------------------- #
def test_create_project_creates_row_and_input_file(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, created = manager.create_project("Xin chào.\nĐây là script.")
    assert created is True
    assert project["status"] == "INGESTED"

    # input file written
    store = AssetStore(project_root)
    input_bytes = store.read_project_file(project["project_id"], "input/script.txt")
    assert input_bytes.decode("utf-8").strip() == "Xin chào.\nĐây là script."

    # DB row exists
    proj = ProjectRepo.get(session, project["project_id"])
    assert proj is not None
    assert proj.script_hash == sha256_text("Xin chào.\nĐây là script.")


def test_create_project_idempotent_same_script(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    p1, created1 = manager.create_project("Cùng một script.")
    p2, created2 = manager.create_project("Cùng một script.")
    assert created1 is True
    assert created2 is False
    assert p1["project_id"] == p2["project_id"]  # reused, not duplicated


def test_create_project_empty_script_raises(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    with pytest.raises(ProjectManagerError):
        manager.create_project("   ")


def test_generate_project_id_unique() -> None:
    ids = {generate_project_id() for _ in range(50)}
    assert len(ids) == 50


def test_sha256_text_deterministic() -> None:
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abd")


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #
def test_plan_creates_storyboard_and_scenes(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Kịch bản demo cho plan.")
    planner = FakePlanner(make_storyboard(5))
    analyzer = ScriptAnalyzer(planner)

    result = run(manager.plan(project["project_id"], analyzer))

    assert result["scene_count"] == 5
    assert result["word_count"] == 5  # "Kịch bản demo cho plan." -> 5 tokens
    # storyboard.json written
    store = AssetStore(project_root)
    sb = store.read_project_file(project["project_id"], "manifests/storyboard.json")
    assert b"summary" in sb

    # DB scenes present
    scenes = SceneRepo.list(session, project["project_id"])
    assert len(scenes) == 5
    assert scenes[0].status == "PLANNED"


def test_plan_sets_status_validated(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Script cho status.")
    planner = FakePlanner(make_storyboard(4))
    analyzer = ScriptAnalyzer(planner)

    run(manager.plan(project["project_id"], analyzer))

    proj = ProjectRepo.get(session, project["project_id"])
    assert proj is not None and proj.status == "STORYBOARD_VALIDATED"
    events = StateEventRepo.list(session, project["project_id"])
    to_states = [e.to_state for e in events]
    assert "SCRIPT_ANALYZED" in to_states
    assert "STORYBOARD_DRAFTED" in to_states
    assert "STORYBOARD_VALIDATED" in to_states


def test_plan_second_time_no_duplicate_scenes(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Script lặp lại.")
    planner = FakePlanner(make_storyboard(5))
    analyzer = ScriptAnalyzer(planner)

    run(manager.plan(project["project_id"], analyzer))
    run(manager.plan(project["project_id"], analyzer))

    scenes = SceneRepo.list(session, project["project_id"])
    ids = [sc.scene_id for sc in scenes]
    assert len(scenes) == 5
    assert len(set(ids)) == 5  # no duplicates after re-plan


def test_plan_missing_project_raises(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    planner = FakePlanner(make_storyboard(5))
    analyzer = ScriptAnalyzer(planner)
    with pytest.raises(ProjectManagerError):
        run(manager.plan("does_not_exist", analyzer))


def test_render_project_measures_voice_before_motion_and_render(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Voice is the canonical clock.")
    project_id = project["project_id"]
    SceneRepo.add(
        session,
        project_id,
        scene_id="scene_001",
        order=1,
        narration_text="The reveal lands now.",
    )
    session.commit()
    asset = AssetRepo.add(
        session,
        project_id,
        "scene_001",
        asset_id="scene_001_composite_v001",
        role="composite",
        path="selected.jpg",
        sha256="image-hash",
        version=1,
        selected=True,
        visual_style_hash=None,
        cache_identity="test-identity",
    )
    SceneRepo.set_selected_image(session, project_id, "scene_001", asset.asset_id)
    session.commit()
    manager.store.write_manifest(
        project_id,
        "storyboard.json",
        {"scenes": [{"scene_id": "scene_001"}]},
    )
    motion_dir = manager.store.subdir(project_id, "manifests") / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / "scene_001.json").write_text(
        '{"scene_id":"scene_001","duration_ms":1574,"fps":30,'
        '"canvas":{"width":1920,"height":1080},"layers":[]}',
        encoding="utf-8",
    )
    calls: list[str] = []

    class TTS:
        async def run(self, pid, active_session, project_root=None):
            from app.providers.base import TTSWordTiming
            from app.services.tts_pipeline import SceneTTSResult

            calls.append("tts")
            scene = SceneRepo.get(active_session, pid, "scene_001")
            scene.actual_voice_duration_ms = 1234
            active_session.commit()
            return SimpleNamespace(
                audio_paths=[Path(project_root) / pid / "audio" / "scene_001.wav"],
                scene_results=[
                    SceneTTSResult(
                        scene_id="scene_001",
                        wav_path="scene_001.wav",
                        duration_ms=1234,
                        cached=False,
                        word_timings=(
                            TTSWordTiming(text="The", start_ms=50, end_ms=200),
                            TTSWordTiming(text="reveal", start_ms=250, end_ms=500),
                            TTSWordTiming(text="lands", start_ms=550, end_ms=800),
                            TTSWordTiming(text="now", start_ms=850, end_ms=1100),
                        ),
                    )
                ],
            )

    class MotionPlanner:
        async def plan_project(self, _pid, contexts):
            from app.schemas.motion_plan import build_motion_plan
            from app.services.motion_templates import build_template

            calls.append("motion")
            assert [ctx.voice_duration_ms for ctx in contexts] == [1234]
            assert contexts[0].timeline is not None
            assert [word.text for word in contexts[0].voice_timeline.words] == [
                "The",
                "reveal",
                "lands",
                "now",
            ]
            return SimpleNamespace(
                scenes=[
                    SimpleNamespace(
                        scene_id="scene_001",
                        plan=build_motion_plan(
                            build_template(
                                "01_subject_slide_headline_pop",
                                "scene_001",
                                1234,
                                canvas_size=(1920, 1080),
                            )
                        ),
                    )
                ]
            )

    class Renderer:
        def render_scene(self, pid, scene_id, _plan, project_root=None):
            calls.append("render")
            output = Path(project_root) / pid / "scenes" / f"{scene_id}.mp4"
            output.write_bytes(b"scene")
            return output, object()

    run(
        manager.render_project(
            project_id,
            renderer=Renderer(),
            motion_planner=MotionPlanner(),
            tts_pipeline=TTS(),
        )
    )

    assert calls == ["tts", "motion", "render"]


def test_render_project_rejects_motion_without_measured_word_timings(session, project_root) -> None:
    from app.services.tts_pipeline import SceneTTSResult

    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Measured words are required.")
    project_id = project["project_id"]
    SceneRepo.add(
        session,
        project_id,
        scene_id="scene_001",
        order=1,
        narration_text="Measured words are required.",
    )
    session.commit()
    manager.store.write_manifest(
        project_id,
        "storyboard.json",
        {"scenes": [{"scene_id": "scene_001"}]},
    )
    motion_dir = manager.store.subdir(project_id, "manifests") / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / "scene_001.json").write_text(
        '{"scene_id":"scene_001","duration_ms":1200,"fps":30,'
        '"canvas":{"width":1920,"height":1080},"layers":[]}',
        encoding="utf-8",
    )

    class TTS:
        async def run(self, pid, active_session, project_root=None):
            scene = SceneRepo.get(active_session, pid, "scene_001")
            scene.actual_voice_duration_ms = 1200
            active_session.commit()
            return SimpleNamespace(
                audio_paths=[Path(project_root) / pid / "audio" / "scene_001.wav"],
                scene_results=[
                    SceneTTSResult(
                        scene_id="scene_001",
                        wav_path="scene_001.wav",
                        duration_ms=1200,
                        cached=False,
                    )
                ],
            )

    class MotionPlanner:
        async def plan_project(self, _pid, _contexts):
            raise AssertionError("motion planner must not run without measured words")

    class Renderer:
        def render_scene(self, *_args, **_kwargs):
            raise AssertionError("renderer must not run without measured words")

    with pytest.raises(ProjectManagerError, match="measured word timings"):
        run(
            manager.render_project(
                project_id,
                renderer=Renderer(),
                motion_planner=MotionPlanner(),
                tts_pipeline=TTS(),
            )
        )


def test_render_project_persists_current_planner_result_before_render(session, project_root) -> None:
    from app.providers.base import TTSWordTiming
    from app.schemas.motion_plan import build_motion_plan
    from app.services.motion_templates import build_template
    from app.services.tts_pipeline import SceneTTSResult

    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Render the current plan.")
    project_id = project["project_id"]
    SceneRepo.add(
        session,
        project_id,
        scene_id="scene_001",
        order=1,
        narration_text="Render the current plan.",
    )
    session.commit()
    asset = AssetRepo.add(
        session,
        project_id,
        "scene_001",
        asset_id="scene_001_composite_v001",
        role="composite",
        path="selected.jpg",
        sha256="image-hash",
        version=1,
        selected=True,
        visual_style_hash=None,
        cache_identity="test-identity",
    )
    SceneRepo.set_selected_image(session, project_id, "scene_001", asset.asset_id)
    session.commit()
    manager.store.write_manifest(
        project_id,
        "storyboard.json",
        {"scenes": [{"scene_id": "scene_001"}]},
    )
    plan = build_motion_plan(
        build_template(
            "01_subject_slide_headline_pop",
            "scene_001",
            1200,
            canvas_size=(1920, 1080),
        )
    )

    class TTS:
        async def run(self, pid, active_session, project_root=None):
            scene = SceneRepo.get(active_session, pid, "scene_001")
            scene.actual_voice_duration_ms = 1200
            active_session.commit()
            return SimpleNamespace(
                audio_paths=[Path(project_root) / pid / "audio" / "scene_001.wav"],
                scene_results=[
                    SceneTTSResult(
                        scene_id="scene_001",
                        wav_path="scene_001.wav",
                        duration_ms=1200,
                        cached=False,
                        word_timings=(
                            TTSWordTiming(text="Render", start_ms=50, end_ms=250),
                            TTSWordTiming(text="the", start_ms=300, end_ms=450),
                            TTSWordTiming(text="current", start_ms=500, end_ms=750),
                            TTSWordTiming(text="plan", start_ms=800, end_ms=1050),
                        ),
                    )
                ],
            )

    class MotionPlanner:
        async def plan_project(self, _pid, _contexts):
            return SimpleNamespace(
                scenes=[SimpleNamespace(scene_id="scene_001", plan=plan)]
            )

    captured: dict[str, Any] = {}

    class Renderer:
        def render_scene(self, pid, scene_id, raw_plan, project_root=None):
            captured["plan"] = raw_plan
            output = Path(project_root) / pid / "scenes" / f"{scene_id}.mp4"
            output.write_bytes(b"scene")
            return output, object()

    run(
        manager.render_project(
            project_id,
            renderer=Renderer(),
            motion_planner=MotionPlanner(),
            tts_pipeline=TTS(),
        )
    )

    persisted = manager._load_scene_plan(project_id, "scene_001")
    assert persisted == plan.to_dict()
    assert captured["plan"] == plan.to_dict()


def test_render_project_prepares_selected_composite_through_layer_owner(session, project_root) -> None:
    from app.storage.repositories import AssetRepo

    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Prepare the selected composite.")
    project_id = project["project_id"]
    SceneRepo.add(
        session,
        project_id,
        scene_id="scene_001",
        order=1,
        narration_text="Prepare the selected composite.",
    )
    asset = AssetRepo.add(
        session,
        project_id,
        "scene_001",
        asset_id="asset_001",
        role="composite",
        path="selected.png",
        selected=True,
    )
    session.flush()
    SceneRepo.set_selected_image(session, project_id, "scene_001", asset.asset_id)
    session.commit()
    manager.store.write_manifest(
        project_id,
        "storyboard.json",
        {"scenes": [{"scene_id": "scene_001"}]},
    )
    motion_dir = manager.store.subdir(project_id, "manifests") / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / "scene_001.json").write_text(
        '{"scene_id":"scene_001","duration_ms":1200,"fps":30,'
        '"canvas":{"width":1920,"height":1080},"layers":[]}',
        encoding="utf-8",
    )
    calls: list[tuple[str, str, str]] = []

    class Layers:
        def prepare_composite(self, pid, scene_id, composite_path, store=None):
            calls.append((pid, scene_id, composite_path))
            return SimpleNamespace(ok=True, error="")

    class Renderer:
        def render_scene(self, pid, scene_id, _raw_plan, project_root=None):
            output = Path(project_root) / pid / "scenes" / f"{scene_id}.mp4"
            output.write_bytes(b"scene")
            return output, object()

    run(
        manager.render_project(
            project_id,
            renderer=Renderer(),
            layer_workflow=Layers(),
        )
    )

    assert calls == [(project_id, "scene_001", "selected.png")]


def test_render_project_materializes_narration_through_same_owner(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Materialize one narration authority.")
    project_id = project["project_id"]
    SceneRepo.add(
        session,
        project_id,
        scene_id="scene_001",
        order=1,
        narration_text="Materialize one narration authority.",
    )
    session.commit()
    asset = AssetRepo.add(
        session,
        project_id,
        "scene_001",
        asset_id="scene_001_composite_v001",
        role="composite",
        path="selected.jpg",
        sha256="image-hash",
        version=1,
        selected=True,
        visual_style_hash=None,
        cache_identity="test-identity",
    )
    SceneRepo.set_selected_image(session, project_id, "scene_001", asset.asset_id)
    session.commit()
    manager.store.write_manifest(
        project_id,
        "storyboard.json",
        {"scenes": [{"scene_id": "scene_001"}]},
    )
    motion_dir = manager.store.subdir(project_id, "manifests") / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / "scene_001.json").write_text(
        '{"scene_id":"scene_001","duration_ms":1200,"fps":30,'
        '"canvas":{"width":1920,"height":1080},"layers":[]}',
        encoding="utf-8",
    )

    class TTS:
        async def run(self, pid, active_session, project_root=None):
            return SimpleNamespace(audio_paths=["scene_001.wav"], marker="same-result")

        def materialize_audio(self, result, output_path):
            assert result.marker == "same-result"
            output_path.write_bytes(b"narration")
            return output_path

    class Renderer:
        def render_scene(self, pid, scene_id, _raw_plan, project_root=None):
            output = Path(project_root) / pid / "scenes" / f"{scene_id}.mp4"
            output.write_bytes(b"scene")
            return output, object()

    result = run(
        manager.render_project(
            project_id,
            renderer=Renderer(),
            tts_pipeline=TTS(),
        )
    )

    narration = Path(result["narration_path"])
    assert narration.name == "narration.wav"
    assert narration.read_bytes() == b"narration"


def test_compose_final_reaches_completed_state_after_render(session, project_root) -> None:
    manager = ProjectManager(session, project_root=project_root)
    project, _ = manager.create_project("Script for final state.")
    pid = project["project_id"]
    store = AssetStore(project_root)
    scenes_dir = store.subdir(pid, "scenes")
    store.subdir(pid, "final")
    store.write_manifest(pid, "storyboard.json", {"scenes": [{"scene_id": "scene_001"}]})
    scene_path = scenes_dir / "scene_001.mp4"
    scene_path.write_bytes(b"scene")

    class Composer:
        def compose(self, scenes, audio, output, **kwargs):
            output.write_bytes(b"final")
            return output, object()

    manager.compose_final(pid, composer=Composer())
    assert ProjectRepo.get(session, pid).status == "COMPLETED"


# --------------------------------------------------------------------------- #
# CLI wiring (argparse commands resolve correctly)
# --------------------------------------------------------------------------- #
def test_cli_has_create_project_and_plan_subcommands() -> None:
    from app.cli import _build_parser

    parser = _build_parser()
    # Access argparse internals; pyright can't see through private API.
    sub = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]
    assert "create-project" in sub  # type: ignore[operator]
    assert "plan" in sub  # type: ignore[operator]
    assert "doctor" in sub  # type: ignore[operator]
    assert "render" in sub  # type: ignore[operator]
    assert "compose" in sub  # type: ignore[operator]
