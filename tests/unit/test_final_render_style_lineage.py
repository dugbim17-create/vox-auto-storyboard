from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services.project_manager import ProjectManager
from app.storage import database
from app.storage.asset_store import sha256_file
from app.storage.repositories import ProjectRepo


def test_compose_final_writes_style_and_input_hash_lineage(tmp_path: Path) -> None:
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    project_root = tmp_path / "projects"
    try:
        with factory() as session:
            ProjectRepo.create(
                session,
                project_id="p1",
                status="SCENES_READY",
                fps=30,
                aspect_ratio="16:9",
            )
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            manager.store.write_manifest(
                "p1",
                "storyboard.json",
                {
                    "style_snapshot": {
                        "style_revision": 2,
                        "visual_hash": "visual-A",
                        "motion_hash": "motion-A",
                        "render_theme_hash": "theme-A",
                    },
                    "scenes": [{"scene_id": "scene_001"}],
                },
            )
            scene = manager.store.subdir("p1", "scenes") / "scene_001.mp4"
            scene.write_bytes(b"scene-video")
            audio = manager.store.subdir("p1", "audio") / "narration.wav"
            audio.write_bytes(b"audio")
            subtitle = manager.store.subdir("p1", "final") / "subtitles.srt"
            subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", "utf-8")

            class Composer:
                def compose(self, scenes, active_audio, output, **kwargs):
                    assert scenes == [scene]
                    assert active_audio == audio
                    output.write_bytes(b"final-video")
                    return output, SimpleNamespace()

            output = manager.compose_final(
                "p1",
                composer=Composer(),
                audio_path=audio,
                subtitle_path=subtitle,
                expected_duration_ms=1000,
            )
            manifest = json.loads(
                (
                    manager.store.subdir("p1", "manifests")
                    / "render_manifest.json"
                ).read_text("utf-8")
            )
            assert output.is_file()
            assert manifest["kind"] == "final_render"
            assert manifest["style"]["visual_hash"] == "visual-A"
            assert manifest["style"]["motion_hash"] == "motion-A"
            assert manifest["style"]["render_theme_hash"] == "theme-A"
            assert manifest["scenes"] == [
                {"scene_id": "scene_001", "sha256": sha256_file(scene)}
            ]
            assert manifest["audio_sha256"] == sha256_file(audio)
            assert manifest["subtitle_sha256"] == sha256_file(subtitle)
            assert manifest["output"]["sha256"] == sha256_file(output)
    finally:
        database.reset_engine()


def test_compose_final_fails_if_scene_lineage_style_is_stale(tmp_path: Path) -> None:
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    project_root = tmp_path / "projects"
    try:
        with factory() as session:
            ProjectRepo.create(
                session,
                project_id="p1",
                status="SCENES_READY",
                fps=30,
                aspect_ratio="16:9",
            )
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            manager.store.write_manifest(
                "p1",
                "storyboard.json",
                {
                    "style_snapshot": {
                        "style_revision": 2,
                        "visual_hash": "visual-new",
                        "motion_hash": "motion-new",
                        "render_theme_hash": "theme-new",
                    },
                    "scenes": [{"scene_id": "scene_001"}],
                },
            )
            scene = manager.store.subdir("p1", "scenes") / "scene_001.mp4"
            scene.write_bytes(b"scene-video")
            render_dir = manager.store.subdir("p1", "manifests") / "render"
            render_dir.mkdir(parents=True, exist_ok=True)
            (render_dir / "scene_001.json").write_text(
                json.dumps(
                    {
                        "style": {
                            "visual_hash": "visual-old",
                            "motion_hash": "motion-old",
                            "render_theme_hash": "theme-old",
                        },
                        "output": {"sha256": sha256_file(scene)},
                    }
                ),
                encoding="utf-8",
            )

            class Composer:
                def compose(self, *args, **kwargs):
                    raise AssertionError("composer must not run")

            try:
                manager.compose_final("p1", composer=Composer())
            except ValueError as exc:
                assert "stale scene render lineage" in str(exc)
            else:
                raise AssertionError("stale scene lineage should block final compose")
    finally:
        database.reset_engine()
