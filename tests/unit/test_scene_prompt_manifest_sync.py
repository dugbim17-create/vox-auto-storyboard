from __future__ import annotations

import json
from pathlib import Path

from app.services.visual_project_service import VisualProjectService
from app.storage.asset_store import AssetStore


def test_save_prompt_updates_canonical_storyboard_manifest(tmp_path: Path) -> None:
    project_id = "p1"
    store = AssetStore(tmp_path)
    store.init_project(project_id)
    path = store.subdir(project_id, "manifests") / "storyboard.json"
    path.write_text(
        json.dumps({"scenes": [{"scene_id": "s1", "image_prompt": "old"}]}),
        encoding="utf-8",
    )

    service = VisualProjectService(project_root=tmp_path)
    service.update_storyboard_prompt(project_id, "s1", "new cinematic prompt")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["scenes"][0]["image_prompt"] == "new cinematic prompt"


def test_save_prompt_rejects_missing_scene(tmp_path: Path) -> None:
    project_id = "p1"
    store = AssetStore(tmp_path)
    store.init_project(project_id)
    path = store.subdir(project_id, "manifests") / "storyboard.json"
    path.write_text(json.dumps({"scenes": []}), encoding="utf-8")

    service = VisualProjectService(project_root=tmp_path)
    try:
        service.update_storyboard_prompt(project_id, "missing", "prompt")
    except ValueError as exc:
        assert "scene not found" in str(exc)
    else:
        raise AssertionError("expected missing scene to fail")
