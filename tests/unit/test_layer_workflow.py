"""Tests for P5-T02 direct layer workflow.

Covers the acceptance criteria:

- preview composite renders correctly (layers flattened onto one canvas);
- layer alignment correct (background full-bleed, subject bottom-center,
  texture/foreground centered);
- asset manifest complete (per-role records under manifests/).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.services.layer_validator import ALPHA_ROLES
from app.services.layer_workflow import LayerWorkflow
from app.storage import database
from app.storage.asset_store import AssetStore
from app.storage.repositories import ProjectRepo


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


def make_image(path: Path, size=(1920, 1080), mode="RGBA", color=(200, 30, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new(mode, size, color)
    img.save(path, format="PNG")
    return path


def seed_project(session, project_root: Path, project_id: str = "prj_layers") -> None:
    store = AssetStore(project_root)
    store.init_project(project_id)
    ProjectRepo.create(session, project_id=project_id, title="Layers")
    session.commit()


def valid_package(image_dir: Path) -> dict:
    bg = make_image(image_dir / "background.png", mode="RGB")
    subj = make_image(image_dir / "subject.png", mode="RGBA", color=(10, 200, 90))
    fg = make_image(image_dir / "foreground.png", mode="RGBA", color=(90, 90, 250))
    tex = make_image(image_dir / "texture.png", mode="RGBA", color=(250, 250, 90))
    comp = make_image(image_dir / "composite.png", mode="RGBA", color=(200, 90, 200))
    return {
        "background": str(bg),
        "subject": str(subj),
        "foreground": str(fg),
        "texture": str(tex),
        "composite": str(comp),
    }


def test_preview_composite_renders_correct_size(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    workflow = LayerWorkflow(project_root=project_root)

    result = workflow.prepare_scene("prj_layers", "scene_001", package, store=store)

    assert result.ok, result.error
    assert len(result.layers) == 5

    # Preview is a canvas-sized image.
    preview = Image.open(result.preview_path)
    assert preview.size == (1920, 1080)
    assert preview.mode == "RGBA"


def test_layer_alignment_correct(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    workflow = LayerWorkflow(project_root=project_root)

    result = workflow.prepare_scene("prj_layers", "scene_001", package, store=store)
    assert result.ok

    layers = {layer.role: layer for layer in result.layers}

    # Background full-bleed at (0,0) and canvas-sized.
    bg = layers["background"]
    assert bg.ox == 0 and bg.oy == 0
    assert bg.width == 1920 and bg.height == 1080

    # Subject bottom-center: oy + height == canvas_height; ox centered.
    subj = layers["subject"]
    assert subj.oy + subj.height == 1080
    assert subj.ox == (1920 - subj.width) // 2

    # Foreground/texture centered (ox/oy non-negative).
    for role in ("foreground", "texture"):
        layer = layers[role]
        assert layer.ox >= 0 and layer.oy >= 0


def test_alpha_expected_on_alpha_roles(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    for layer in result.layers:
        if layer.role in ALPHA_ROLES:
            assert layer.alpha is True
        else:
            assert layer.alpha is False


def test_asset_manifest_complete(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    assert result.ok

    # Manifest file exists under manifests/.
    manifest = json.loads(
        (project_root / "prj_layers" / "manifests" / "asset_manifest_scene_001.json").read_text("utf-8")
    )
    assert manifest["scene_id"] == "scene_001"
    assert manifest["canvas"]["width"] == 1920
    assert manifest["canvas"]["height"] == 1080
    assert len(manifest["layers"]) == 5
    roles = {layer["role"] for layer in manifest["layers"]}
    assert roles == {"background", "subject", "foreground", "texture", "composite"}


def test_normalized_layers_written_to_disk(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    assert result.ok

    for layer in result.layers:
        assert Path(layer.path).is_file()
        # All normalized layers are RGBA PNGs at canvas size.
        with Image.open(layer.path) as img:
            assert img.size == (1920, 1080)
            assert img.mode == "RGBA"


def test_invalid_package_rejected(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    package["subject"] = "missing.png"
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    assert not result.ok
    assert "subject" in result.error


def test_preview_has_background_pixels(project_root, session) -> None:
    # Sanity: preview top-left should be opaque (background full-bleed).
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    assert result.ok
    with Image.open(result.preview_path) as preview:
        px = preview.getpixel((5, 5))
        assert px[3] > 0  # opaque at top-left (background covers)


def test_metadata_preserved_in_normalized_png(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    assert result.ok
    # The normalized subject PNG carries a Role metadata chunk.
    with Image.open(project_root / "prj_layers" / "layers" / "scene_001_subject.png") as img:
        assert "Role" in img.info
        assert img.info["Role"] == "subject"


# --------------------------------------------------------------------------- #
# Strategy B — prepare_composite (P5-T03 segmentation fallback)
# --------------------------------------------------------------------------- #
class _RectBackend:
    """Deterministic fake segmentation: subject = a rectangle on the frame."""

    def __init__(self, box=(80, 50, 200, 150), size=(320, 240)) -> None:
        self.box = box
        self.size = size

    def produce_mask(self, image) -> Image.Image:
        m = Image.new("L", self.size, 0)
        for y in range(self.box[1], self.box[3]):
            for x in range(self.box[0], self.box[2]):
                m.putpixel((x, y), 255)
        return m


class _EmptyBackend:
    """Fake backend that finds no subject (forces composite fallback)."""

    def __init__(self, size=(320, 240)) -> None:
        self.size = size

    def produce_mask(self, _image) -> Image.Image:
        return Image.new("L", self.size, 0)  # zero mask == "no subject"


def make_composite(path: Path, size=(320, 240), bg=(30, 60, 120)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", size, bg + (255,))
    img.save(path, format="PNG")
    return path


def test_prepare_composite_segments_subject(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    comp = make_composite(project_root / "src" / "composite.png")
    workflow = LayerWorkflow(
        canvas_width=320, canvas_height=240, project_root=project_root,
        segmentation_backend=_RectBackend(size=(320, 240)),
    )

    result = workflow.prepare_composite("prj_layers", "scene_001", str(comp), store=store)
    assert result.ok, result.error
    roles = {layer.role for layer in result.layers}
    assert roles == {"composite", "subject", "background"}

    by_role = {layer.role: layer for layer in result.layers}
    assert by_role["subject"].alpha is True
    assert by_role["background"].alpha is False
    # Manifest + preview written to disk.
    assert Path(result.manifest_path).is_file()
    assert Path(result.preview_path).is_file()


def test_prepare_composite_fallback_when_no_subject(project_root, session) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    comp = make_composite(project_root / "src" / "composite.png")
    workflow = LayerWorkflow(
        canvas_width=320, canvas_height=240, project_root=project_root,
        segmentation_backend=_EmptyBackend(),
    )

    result = workflow.prepare_composite("prj_scene", "scene_002", str(comp), store=store)
    assert result.ok, result.error
    # No subject found -> only composite + background (composite is the fallback).
    roles = {layer.role for layer in result.layers}
    assert roles == {"composite", "background"}
    # The composite layer carries the whole frame (fallback subject proxy).
    composite_layer = next(layer for layer in result.layers if layer.role == "composite")
    with Image.open(composite_layer.path) as img:
        assert img.mode == "RGBA"


def test_prepare_scene_manifest_is_a_real_file(project_root, session) -> None:
    """Regression: prepare_scene writes a JSON manifest (not a tuple string)."""
    seed_project(session, project_root)
    store = AssetStore(project_root)
    package = valid_package(project_root / "src")
    result = LayerWorkflow(project_root=project_root).prepare_scene(
        "prj_layers", "scene_001", package, store=store
    )
    assert result.ok
    assert Path(result.manifest_path).is_file()
    data = json.loads(Path(result.manifest_path).read_text("utf-8"))
    assert data["scene_id"] == "scene_001"
