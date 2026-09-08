from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.services.project_manager import ProjectManager
from app.storage import database
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo


def test_project_render_uses_coordinator_and_writes_style_lineage(tmp_path: Path) -> None:
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    project_root = tmp_path / "projects"
    try:
        with factory() as session:
            ProjectRepo.create(session, project_id="p1", status="STORYBOARD_VALIDATED")
            session.flush()
            SceneRepo.add(session, "p1", scene_id="scene_001", order=1)
            session.flush()
            asset = AssetRepo.add(
                session,
                "p1",
                "scene_001",
                asset_id="scene_001_composite_v001",
                role="composite",
                path="selected.jpg",
                sha256="image-hash",
                version=1,
                selected=True,
                visual_style_hash="visual-A",
                cache_identity="identity-A",
            )
            SceneRepo.set_selected_image(session, "p1", "scene_001", asset.asset_id)
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            manager.store.write_manifest(
                "p1",
                "storyboard.json",
                {
                    "style_snapshot": {
                        "style_revision": 1,
                        "visual_hash": "visual-A",
                        "motion_hash": "motion-A",
                        "render_theme_hash": "theme-A",
                    },
                    "scenes": [{"scene_id": "scene_001"}],
                },
            )
            motion_dir = manager.store.subdir("p1", "manifests") / "motion"
            motion_dir.mkdir(parents=True, exist_ok=True)
            (motion_dir / "scene_001.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "motion_plan",
                        "scene_id": "scene_001",
                        "style": {
                            "style_revision": 1,
                            "visual_hash": "visual-A",
                            "motion_hash": "motion-A",
                            "render_theme_hash": "theme-A",
                        },
                        "payload_sha256": "motion-payload-hash",
                        "payload": {
                            "scene_id": "scene_001",
                            "duration_ms": 1000,
                            "fps": 30,
                            "canvas": {"width": 320, "height": 180},
                            "layers": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            class Renderer:
                renderer_name = "ffmpeg"
                renderer_version = "test"

                def render_scene(self, project_id, scene_id, plan, project_root=None):
                    output = Path(project_root) / project_id / "scenes" / f"{scene_id}.mp4"
                    output.write_bytes(b"scene")
                    return output, SimpleNamespace(width=320, height=180)

            result = asyncio.run(manager.render_project("p1", renderer=Renderer()))
            assert result["rendered"] == [
                str(project_root / "p1" / "scenes" / "scene_001.mp4")
            ]
            lineage = json.loads(
                (
                    project_root
                    / "p1"
                    / "manifests"
                    / "render"
                    / "scene_001.json"
                ).read_text("utf-8")
            )
            assert lineage["style"]["visual_hash"] == "visual-A"
            assert lineage["inputs"]["selected_asset_id"] == asset.asset_id
    finally:
        database.reset_engine()


def test_project_render_blocks_stale_selected_asset(tmp_path: Path) -> None:
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    project_root = tmp_path / "projects"
    try:
        with factory() as session:
            ProjectRepo.create(session, project_id="p1", status="STORYBOARD_VALIDATED")
            session.flush()
            SceneRepo.add(session, "p1", scene_id="scene_001", order=1)
            session.flush()
            asset = AssetRepo.add(
                session,
                "p1",
                "scene_001",
                asset_id="scene_001_composite_v001",
                role="composite",
                path="selected.jpg",
                sha256="image-hash",
                version=1,
                selected=True,
                visual_style_hash="visual-old",
                cache_identity="identity-old",
            )
            SceneRepo.set_selected_image(session, "p1", "scene_001", asset.asset_id)
            session.commit()
            manager = ProjectManager(session, project_root=project_root)
            manager.store.write_manifest(
                "p1",
                "storyboard.json",
                {
                    "style_snapshot": {
                        "style_revision": 2,
                        "visual_hash": "visual-new",
                        "motion_hash": "motion-A",
                        "render_theme_hash": "theme-A",
                    },
                    "scenes": [{"scene_id": "scene_001"}],
                },
            )
            motion_dir = manager.store.subdir("p1", "manifests") / "motion"
            motion_dir.mkdir(parents=True, exist_ok=True)
            (motion_dir / "scene_001.json").write_text(
                json.dumps(
                    {
                        "kind": "motion_plan",
                        "style": {"motion_hash": "motion-A"},
                        "payload_sha256": "motion",
                        "payload": {
                            "scene_id": "scene_001",
                            "duration_ms": 1000,
                            "fps": 30,
                            "canvas": {"width": 320, "height": 180},
                            "layers": [],
                        },
                    }
                ),
                encoding="utf-8",
            )

            class Renderer:
                def render_scene(self, *args, **kwargs):
                    raise AssertionError("renderer must not run")

            try:
                asyncio.run(manager.render_project("p1", renderer=Renderer()))
            except ValueError as exc:
                assert "stale selected image" in str(exc)
            else:
                raise AssertionError("stale image should block render")
    finally:
        database.reset_engine()
