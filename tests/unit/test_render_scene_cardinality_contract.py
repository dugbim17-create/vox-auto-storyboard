from __future__ import annotations

from pathlib import Path

import pytest

from app.services.project_manager import ProjectManager, ProjectManagerError
from app.storage import database
from app.storage.repositories import ProjectRepo, SceneRepo


def _manager(tmp_path: Path):
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_schema(engine)
    session = database.get_session_factory(engine)()
    manager = ProjectManager(session, project_root=tmp_path / "projects")
    project, _ = manager.create_project("two scene script", project_id="p1")
    SceneRepo.add(session, project["project_id"], scene_id="scene_001", order=1)
    SceneRepo.add(session, project["project_id"], scene_id="scene_002", order=2)
    session.commit()
    store = manager.store
    store.write_manifest(
        "p1",
        "storyboard.json",
        {"scenes": [{"scene_id": "scene_001"}, {"scene_id": "scene_002"}]},
    )
    return session, manager


def test_compose_rejects_partial_scene_set_before_composer(tmp_path: Path) -> None:
    session, manager = _manager(tmp_path)
    manager.store.subdir("p1", "scenes").joinpath("scene_001.mp4").write_bytes(b"one")

    class Composer:
        called = False

        def compose(self, *_args, **_kwargs):
            self.called = True
            raise AssertionError("composer must not run")

    composer = Composer()
    with pytest.raises(ProjectManagerError, match="missing scene MP4"):
        manager.compose_final("p1", composer=composer)
    assert composer.called is False
    assert ProjectRepo.get(session, "p1").status != "COMPLETED"
    assert not (manager.store.subdir("p1", "final") / "final.mp4").exists()
    session.close()
    database.reset_engine()


def test_render_rejects_missing_motion_plan_instead_of_skipping(tmp_path: Path) -> None:
    import asyncio

    session, manager = _manager(tmp_path)
    motion_dir = manager.store.subdir("p1", "manifests") / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / "scene_001.json").write_text(
        '{"scene_id":"scene_001","duration_ms":1000,"fps":30,"canvas":{"width":320,"height":180},"layers":[]}',
        encoding="utf-8",
    )

    class Renderer:
        def render_scene(self, project_id, scene_id, plan, project_root=None):
            out = Path(project_root) / project_id / "scenes" / f"{scene_id}.mp4"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"scene")
            return out, object()

    with pytest.raises(ProjectManagerError, match="missing motion plan"):
        asyncio.run(manager.render_project("p1", renderer=Renderer()))
    session.close()
    database.reset_engine()
