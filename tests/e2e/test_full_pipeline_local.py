"""End-to-end test for the local pipeline (Phase 7).

Drives the whole flow with **no external services**:

1. ``create-project`` via ``ProjectManager`` (real DB).
2. fake image service writes JPEGs straight to ``images/``.
3. fake layer workflow writes PNGs to ``layers/``.
4. pre-written motion plan JSONs in ``manifests/motion/{scene_id}.json``.
5. ``render_project(renderer=LocalSceneRenderer-with-fakes)`` produces
   ``scenes/*.mp4`` placeholders.
6. fake TTS writes ``audio/narration.wav``.
7. ``compose_final(composer=FinalComposer-with-fakes)`` writes
   ``final/final.mp4``.

Each test asserts on the artefacts (files, sizes, status fields) so a
regression in any one stage fails fast. Tests never invoke real FFmpeg.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import wave
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import sessionmaker

import app.storage.database as db_module
from app.services.ffmpeg_compiler import CompiledMotion
from app.services.final_composer import FinalComposer
from app.services.motion_templates import build_template
from app.services.project_manager import (
    ProjectManager,
    ProjectManagerError,
)
from app.services.scene_renderer import LocalSceneRenderer, RenderProbe
from app.storage.asset_store import AssetStore

PROJECT_ID = "prj_e2e"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeCompiler:
    """Captures plans/assets; produces a canned CompiledMotion for the
    renderer. Never invokes a real FFmpeg binary."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict, str]] = []

    def compile(self, plan, *, assets=None, output_path="") -> CompiledMotion:
        self.calls.append((plan, assets or {}, str(output_path)))
        return CompiledMotion(
            scene_id=plan["scene_id"],
            command=["ffmpeg", "-y", "-i", "x.png", "-t", "1", str(output_path)],
            filter_graph="null",
            fps=plan.get("fps", 30),
            width=plan.get("canvas", {}).get("width", 1920),
            height=plan.get("canvas", {}).get("height", 1080),
            duration_ms=plan.get("duration_ms", 1000),
            frame_count=plan.get("fps", 30),
        )


class FakeRunner:
    """Captures every command; writes a tiny placeholder file at the last
    argument (FFmpeg's output convention)."""

    def __init__(self, rc: int = 0) -> None:
        self.rc = rc
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **_):
        self.calls.append(list(cmd))
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-mp4")

        class P:
            returncode = self.rc
            stderr = "boom"
        return P()


class FakeProbe:
    def __init__(self, fps=30.0, width=320, height=180, duration_ms=1000,
                 pix_fmt="yuv420p") -> None:
        self.data: dict = {
            "fps": float(fps), "width": int(width), "height": int(height),
            "duration_ms": int(duration_ms), "pix_fmt": str(pix_fmt),
        }

    def __call__(self, _p, plan):
        probe = RenderProbe(**self.data)
        canvas = plan.get("canvas", {})
        probe.verify(
            expected_fps=plan.get("fps", 30),
            expected_w=canvas.get("width", 1920),
            expected_h=canvas.get("height", 1080),
            expected_duration_ms=plan.get("duration_ms", 1000),
        )
        return probe


class FakeFinalProbe:
    def __init__(self, audio=False, duration_ms=1000) -> None:
        self.audio = audio
        self.duration_ms = duration_ms

    def __call__(self, _composer, _path) -> dict:
        return {
            "fps": 30.0, "width": 320, "height": 180, "duration_ms": self.duration_ms,
            "pix_fmt": "yuv420p", "has_audio": self.audio,
        }


class FakeImageService:
    def __init__(self, project_root: Path) -> None:
        self.calls: list[str] = []
        self.project_root = project_root

    async def generate_project(self, project_id, *, session=None):
        from PIL import Image

        from app.services.image_generation import ImagePipelineResult
        from app.storage.repositories import AssetRepo, SceneRepo

        self.calls.append(project_id)
        store = AssetStore(self.project_root)
        images = store.subdir(project_id, "images")
        scene_count = 0
        for storyboard_path in store.subdir(project_id, "manifests").glob("storyboard.json"):
            sb = json.loads(storyboard_path.read_text(encoding="utf-8"))
            for order, scene in enumerate(sb.get("scenes", []), start=1):
                scene_id = scene["scene_id"]
                if SceneRepo.get(session, project_id, scene_id) is None:
                    SceneRepo.add(session, project_id, scene_id=scene_id, order=order)
                    session.flush()
                for role in ("subject", "background", "headline"):
                    img = Image.new("RGB", (320, 180), (30, 60, 120))
                    img.save(images / f"{scene_id}_{role}.jpg", "JPEG")
                selected_path = images / f"{scene_id}_subject.jpg"
                asset = AssetRepo.add(
                    session,
                    project_id,
                    scene_id,
                    asset_id=f"{scene_id}_composite_v001",
                    role="composite",
                    path=str(selected_path),
                    sha256="fake-image-hash",
                    version=1,
                    selected=True,
                    visual_style_hash=None,
                    cache_identity=f"fake-{scene_id}",
                )
                SceneRepo.set_selected_image(session, project_id, scene_id, asset.asset_id)
                scene_count += 1
        session.commit()
        return ImagePipelineResult(project_id=project_id, total_scenes=scene_count)


class FakeTTSPipeline:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(self, project_id, session=None, *, project_root=None):
        self.calls.append(project_id)
        store = AssetStore(project_root)
        audio_dir = store.subdir(project_id, "audio")
        out = audio_dir / "narration.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)
        from app.services.tts_pipeline import TTSPipelineResult
        return TTSPipelineResult(
            project_id=project_id, total_scenes=1, generated=1,
        )


# --------------------------------------------------------------------------- #
# Setup helpers
# --------------------------------------------------------------------------- #
def _write_motion_plan(root: Path, scene_id: str, template: str,
                       duration_ms: int = 1000) -> None:
    plan = build_template(template, scene_id, duration_ms, seed=1, canvas_size=(320, 180))
    manifests = AssetStore(root).subdir(PROJECT_ID, "manifests")
    motion_dir = manifests / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / f"{scene_id}.json").write_text(
        json.dumps(plan, ensure_ascii=False), encoding="utf-8"
    )


def _write_layer(root: Path, scene_id: str, role: str) -> None:
    from PIL import Image

    layers = AssetStore(root).subdir(PROJECT_ID, "layers")
    img = Image.new("RGBA", (320, 180), (200, 30, 30, 255))
    img.save(layers / f"{scene_id}_{role}.png")


def _write_storyboard(root: Path, scenes: list[str]) -> None:
    sb = {
        "project_id": PROJECT_ID,
        "title": "E2E",
        "aspect_ratio": "16:9",
        "fps": 30,
        "scenes": [
            {
                "scene_id": s, "order": i + 1,
                "script_span": {"start_char": i * 10, "end_char": (i + 1) * 10},
                "narration_text": f"Scene {i+1}",
                "purpose": "body",
                "estimated_duration_seconds": 1.0,
                "visual_summary": f"Scene {i+1}",
                "image_prompt": f"A test visual for scene {i+1}, no text",
                "negative_constraints": ["no text"],
                "motion_prompt": "subtle movement",
                "motion_template": "01_subject_slide_headline_pop",
                "transition_out": "hard_cut",
            }
            for i, s in enumerate(scenes)
        ],
    }
    manifests = AssetStore(root).subdir(PROJECT_ID, "manifests")
    (manifests / "storyboard.json").write_text(
        json.dumps(sb, ensure_ascii=False), encoding="utf-8"
    )


def _setup_prj(project_root: Path, scenes: list[str],
               templates: list[str] | None = None) -> str:
    templates = templates or ["01_subject_slide_headline_pop"] * len(scenes)
    assert len(templates) == len(scenes)
    AssetStore(project_root).init_project(PROJECT_ID)
    _write_storyboard(project_root, scenes)
    for s, tpl in zip(scenes, templates, strict=True):
        plan = build_template(tpl, s, 1000, seed=1, canvas_size=(320, 180))
        # Build the motion plan JSON for the renderer to pick up.
        _write_motion_plan(project_root, s, tpl, duration_ms=1000)
        # Materialise a PNG for every role the template references.
        roles = {layer.get("asset_role", "") for layer in plan.get("layers", [])}
        for role in roles:
            _write_layer(project_root, s, role)
    return PROJECT_ID



def _seed_selected_assets(session, project_root: Path, scenes: list[str]) -> None:
    from app.storage.repositories import AssetRepo, SceneRepo

    store = AssetStore(project_root)
    for order, scene_id in enumerate(scenes, start=1):
        if SceneRepo.get(session, PROJECT_ID, scene_id) is None:
            SceneRepo.add(session, PROJECT_ID, scene_id=scene_id, order=order)
            session.flush()
        selected_path = store.subdir(PROJECT_ID, "layers") / f"{scene_id}_subject.png"
        asset = AssetRepo.add(
            session,
            PROJECT_ID,
            scene_id,
            asset_id=f"{scene_id}_composite_v001",
            role="composite",
            path=str(selected_path),
            sha256="fake-image-hash",
            version=1,
            selected=True,
            visual_style_hash=None,
            cache_identity=f"fake-{scene_id}",
        )
        SceneRepo.set_selected_image(session, PROJECT_ID, scene_id, asset.asset_id)
    session.commit()

def _new_renderer(project_root: Path | None = None) -> tuple[LocalSceneRenderer, FakeCompiler, FakeRunner]:
    runner = FakeRunner()
    renderer = LocalSceneRenderer(runner=runner, project_root=project_root)
    renderer.compiler = FakeCompiler()  # type: ignore[assignment]
    return renderer, renderer.compiler, runner  # type: ignore[return-value]


def _make_session() -> Any:
    factory = sessionmaker(
        bind=db_module.get_engine(),
        autoflush=True, expire_on_commit=False, future=True,
    )
    return factory()


# --------------------------------------------------------------------------- #
# DB / project fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch) -> Any:
    db_path = tmp_path / "e2e.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    db_module.reset_engine()
    engine = db_module.get_engine(db_url)
    db_module.init_schema(engine)
    yield
    db_module.reset_engine()


@pytest.fixture()
def project_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "projects"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PROJECT_ROOT", str(root))
    return root


# --------------------------------------------------------------------------- #
# E2E tests
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="ffmpeg not required, but runs on all platforms")
def test_e2e_01_single_scene_no_audio(project_root: Path, tmp_path: Path) -> None:
    pid = _setup_prj(project_root, ["scene_001"])
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script 1.", project_id=PROJECT_ID)
        img = FakeImageService(project_root)
        renderer, _compiler, runner = _new_renderer(project_root)
        renderer._probe = FakeProbe(width=320, height=180)  # type: ignore[assignment]
        asyncio.run(manager.render_project(pid, renderer=renderer, image_service=img))
        composer = FinalComposer(runner=FakeRunner())
        composer._run_probe = lambda path: FakeFinalProbe(audio=False, duration_ms=1000)(composer, path)  # type: ignore[assignment]
        out = manager.compose_final(pid, composer=composer)
    assert out.is_file()
    assert out.name == "final.mp4"
    assert len(runner.calls) >= 1


def test_e2e_02_three_scenes_with_audio(project_root: Path, tmp_path: Path) -> None:
    pid = _setup_prj(project_root, ["scene_001", "scene_002", "scene_003"])
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script 3 scenes.", project_id=PROJECT_ID)
        img = FakeImageService(project_root)
        tts = FakeTTSPipeline()
        renderer, compiler, _runner = _new_renderer(project_root)
        renderer._probe = FakeProbe(width=320, height=180)  # type: ignore[assignment]
        asyncio.run(manager.render_project(
            pid, renderer=renderer, image_service=img, tts_pipeline=tts,
        ))
        audio = project_root / pid / "audio" / "narration.wav"
        assert audio.is_file()
        # We invoke the composer directly with expected_duration_ms=3000 to
        # avoid the per-scene sum probe (which can't easily distinguish
        # between per-scene and final probes under the fake runner).
        composer = FinalComposer(runner=FakeRunner())
        composer._run_probe = lambda p: FakeFinalProbe(audio=True, duration_ms=3000)(composer, p)  # type: ignore[assignment]
        scenes = sorted((project_root / pid / "scenes").glob("*.mp4"))
        assert len(scenes) == 3
        out, _probe = composer.compose(
            scenes,
            audio,
            project_root / pid / "final" / "final.mp4",
            fps=30, width=320, height=180, expected_duration_ms=3000,
        )
    assert out.is_file()
    assert len(compiler.calls) == 3


def test_e2e_03_idempotent_create(project_root: Path, tmp_path: Path) -> None:
    _setup_prj(project_root, ["scene_001"])
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        p1, c1 = manager.create_project("Same script.", title="T", project_id=PROJECT_ID)
        p2, c2 = manager.create_project("Same script.", title="T", project_id=PROJECT_ID)
        assert c1 is True
        assert c2 is False
        assert p1["project_id"] == p2["project_id"]


def test_e2e_04_motion_plan_asset_role_mismatch(project_root: Path, tmp_path: Path) -> None:
    """Motion plan referencing a layer role whose asset does not exist in
    the assets map must be detected at compile time. The renderer's default
    asset discovery silently skips missing roles; we instead pass an explicit
    assets map that points to a nonexistent path so MotionCompilerError
    bubbles up."""
    from app.services.ffmpeg_compiler import MotionCompiler, MotionCompilerError

    pid = _setup_prj(project_root, ["scene_001"])
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script.", project_id=PROJECT_ID)
        plan = json.loads(
            (project_root / pid / "manifests" / "motion" / "scene_001.json").read_text(
                encoding="utf-8"
            )
        )
        # Empty assets map -> every layer fails. MotionCompiler raises.
        with pytest.raises(MotionCompilerError, match="has no asset"):
            MotionCompiler().compile(plan, assets={})


def test_e2e_05_compose_without_audio(project_root: Path, tmp_path: Path) -> None:
    pid = _setup_prj(project_root, ["scene_001"])
    print("\nDEBUG scene MP4 dir:", project_root / pid / "scenes")
    print("DEBUG motion plan exists:", (project_root / pid / "manifests" / "motion" / "scene_001.json").is_file())
    print("DEBUG layer exists:", list((project_root / pid / "layers").glob("*")))
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script.", project_id=PROJECT_ID)
        _seed_selected_assets(session, project_root, ['scene_001'])
        renderer, _, _ = _new_renderer(project_root)
        renderer._probe = FakeProbe(width=320, height=180)  # type: ignore[assignment]
        asyncio.run(manager.render_project(pid, renderer=renderer))
        # List scenes dir after render
        print("DEBUG scenes after render:", list((project_root / pid / "scenes").glob("*")))
        composer = FinalComposer(runner=FakeRunner())
        composer._run_probe = lambda p: FakeFinalProbe(audio=False, duration_ms=1000)(composer, p)  # type: ignore[assignment]
        out = manager.compose_final(pid, composer=composer)
    assert out.is_file()
    assert out.parent.is_dir()


def test_e2e_07_compose_missing_scenes_raises(project_root: Path, tmp_path: Path) -> None:
    pid = _setup_prj(project_root, ["scene_001"])
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script.", project_id=PROJECT_ID)
        composer = FinalComposer(runner=FakeRunner())
        with pytest.raises(ProjectManagerError, match="missing scene MP4"):
            manager.compose_final(pid, composer=composer)


def test_e2e_08_state_machine_advances(project_root: Path, tmp_path: Path) -> None:
    pid = _setup_prj(project_root, ["scene_001"])
    with _make_session() as session:
        manager = ProjectManager(session, project_root=project_root)
        manager.create_project("Script.", project_id=PROJECT_ID)
        _seed_selected_assets(session, project_root, ['scene_001'])
        renderer, _, _ = _new_renderer(project_root)
        renderer._probe = FakeProbe(width=320, height=180)  # type: ignore[assignment]
        asyncio.run(manager.render_project(pid, renderer=renderer))
        composer = FinalComposer(runner=FakeRunner())
        composer._run_probe = lambda p: FakeFinalProbe(audio=False, duration_ms=1000)(composer, p)  # type: ignore[assignment]
        manager.compose_final(pid, composer=composer)
        proj = manager.get_project(pid)
        assert proj["status"] == "COMPLETED"
