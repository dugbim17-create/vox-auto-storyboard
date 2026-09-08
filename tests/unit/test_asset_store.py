"""Tests for the P1-T03 asset store (path safety, atomic writes, SHA-256, versioning)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.storage.asset_store import (
    PROJECT_SUBDIRS,
    AssetStore,
    AssetStoreError,
    sha256_bytes,
    sha256_file,
)


@pytest.fixture()
def store(tmp_path: Path) -> AssetStore:
    return AssetStore(project_root=tmp_path)


def test_init_project_creates_all_subdirs(store: AssetStore) -> None:
    root = store.init_project("prj_123")
    assert root.is_dir()
    for sub in PROJECT_SUBDIRS:
        assert (root / sub).is_dir()


def test_invalid_project_id_rejected(store: AssetStore) -> None:
    for bad in ("../evil", "a/b", "a\\b", "", ".hidden", "prj/../../etc"):
        with pytest.raises(AssetStoreError):
            store.project_dir(bad)


def test_path_traversal_blocked(store: AssetStore) -> None:
    store.init_project("prj_1")
    with pytest.raises(AssetStoreError):
        store._resolve_inside("prj_1", "../../../../windows/evil")

    # also via write_project_file
    with pytest.raises(AssetStoreError):
        store.write_project_file("prj_1", "../outside.txt", b"x")


def test_unknown_subdir_rejected(store: AssetStore) -> None:
    store.init_project("prj_1")
    with pytest.raises(AssetStoreError):
        store.subdir("prj_1", "hack")


def test_atomic_write_and_sha256(store: AssetStore) -> None:
    store.init_project("prj_a")
    data = b"hello world"
    path, digest = store.write_project_file("prj_a", "input/script.txt", data)
    assert path.is_file()
    assert path.read_bytes() == data
    assert digest == sha256_bytes(data) == sha256_file(path)


def test_versioned_assets_never_overwrite(store: AssetStore) -> None:
    store.init_project("prj_v")
    p1, _ = store.write_versioned("prj_v", "images", "scene_001", ".png", 1, b"A")
    p2, _ = store.write_versioned("prj_v", "images", "scene_001", ".png", 2, b"B")
    assert p1 != p2
    assert p1.name == "scene_001_v001.png"
    assert p2.name == "scene_001_v002.png"
    assert p1.read_bytes() == b"A"
    assert p2.read_bytes() == b"B"  # old content preserved (regenerate rule)


def test_manifest_write_json(store: AssetStore) -> None:
    store.init_project("prj_m")
    path, digest = store.write_manifest("prj_m", "storyboard.json", {"scenes": []})
    assert path.name == "storyboard.json"
    assert path.is_file()
    assert path.parent.name == "manifests"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["scenes"] == []
    assert loaded["sha256"]
    assert digest == sha256_file(path)
