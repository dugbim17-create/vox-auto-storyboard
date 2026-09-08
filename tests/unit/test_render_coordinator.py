from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services.render_coordinator import RenderCoordinator
from app.storage.asset_store import AssetStore


def _write_project(store: AssetStore, project_id: str) -> None:
    store.init_project(project_id)
    store.write_manifest(
        project_id,
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
    motion_dir = store.subdir(project_id, "manifests") / "motion"
    motion_dir.mkdir(parents=True, exist_ok=True)
    (motion_dir / "scene_001.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "motion_plan",
                "scene_id": "scene_001",
                "style": {
                    "style_revision": 2,
                    "visual_hash": "visual-A",
                    "motion_hash": "motion-A",
                    "render_theme_hash": "theme-A",
                },
                "payload_sha256": "motion-file-hash",
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


def test_coordinator_renders_and_persists_scene_lineage(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    _write_project(store, "p1")
    output = store.subdir("p1", "scenes") / "scene_001.mp4"

    class Renderer:
        renderer_name = "ffmpeg"
        renderer_version = "test"

        def render_scene(self, project_id, scene_id, plan, project_root=None):
            assert project_id == "p1"
            assert scene_id == "scene_001"
            assert plan["duration_ms"] == 1000
            output.write_bytes(b"verified-scene")
            return output, SimpleNamespace(width=320, height=180)

    result = RenderCoordinator(renderer=Renderer(), project_root=store.base).render_scene(
        project_id="p1",
        scene_id="scene_001",
        selected_asset=SimpleNamespace(
            asset_id="asset-1",
            sha256="image-hash",
            visual_style_hash="visual-A",
        ),
    )

    assert result.output_path == output
    assert result.renderer == "ffmpeg"
    manifest = json.loads(
        (store.subdir("p1", "manifests") / "render" / "scene_001.json").read_text("utf-8")
    )
    assert manifest["style"]["visual_hash"] == "visual-A"
    assert manifest["inputs"]["selected_asset_id"] == "asset-1"
    assert manifest["output"]["sha256"] == result.sha256


def test_coordinator_blocks_stale_selected_asset_before_renderer(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    _write_project(store, "p1")
    calls = []

    class Renderer:
        renderer_name = "ffmpeg"
        renderer_version = "test"

        def render_scene(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("renderer must not run")

    try:
        RenderCoordinator(renderer=Renderer(), project_root=store.base).render_scene(
            project_id="p1",
            scene_id="scene_001",
            selected_asset=SimpleNamespace(
                asset_id="asset-old",
                sha256="old-image",
                visual_style_hash="visual-old",
            ),
        )
    except ValueError as exc:
        assert "stale selected image" in str(exc)
    else:
        raise AssertionError("stale asset should block render")
    assert calls == []


def test_coordinator_rejects_motion_lineage_from_old_style(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "projects")
    _write_project(store, "p1")
    motion = store.subdir("p1", "manifests") / "motion" / "scene_001.json"
    payload = json.loads(motion.read_text("utf-8"))
    payload["style"]["motion_hash"] = "motion-old"
    motion.write_text(json.dumps(payload), encoding="utf-8")

    class Renderer:
        renderer_name = "ffmpeg"
        renderer_version = "test"

        def render_scene(self, *args, **kwargs):
            raise AssertionError("renderer must not run")

    try:
        RenderCoordinator(renderer=Renderer(), project_root=store.base).render_scene(
            project_id="p1",
            scene_id="scene_001",
            selected_asset=SimpleNamespace(
                asset_id="asset-1",
                sha256="image-hash",
                visual_style_hash="visual-A",
            ),
        )
    except ValueError as exc:
        assert "stale motion plan" in str(exc)
    else:
        raise AssertionError("stale motion plan should block render")
