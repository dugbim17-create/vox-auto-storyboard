"""Tests for P4-T05 image generation service.

Covers the acceptance criteria:

- generate toàn project (every scene gets 5 role images + asset rows);
- fail một scene không mất scene khác (one failing provider does not stop others);
- retry scene (transient failure -> JobRunner retries -> success);
- select candidate (composite selected, scene.selected_image_asset_id set);
- cache (unchanged prompt reuses files without calling the provider again).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.providers.base import ImageGenerationRequest, ImageGenerationResult
from app.services.image_generation import (
    ImageGenerationService,
    role_cache_key,
)
from app.storage import database
from app.storage.asset_store import AssetStore
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo

ROLES = ("composite", "background", "subject", "foreground", "texture")


def write_png(path: Path) -> None:
    """A minimal valid PNG so the fake provider produces a real file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # 1x1 PNG
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
        )
    )


class FakeImage:
    def __init__(self, *, fail_roles: set[str] | None = None, fail_prompt_marker: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_roles = fail_roles or set()
        self.fail_prompt_marker = fail_prompt_marker
        self.last_request: ImageGenerationRequest | None = None

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.calls.append(f"{request.role}:{request.prompt[:20]}")
        self.last_request = request
        if request.role in self.fail_roles:
            raise RuntimeError(f"provider failed for {request.role}")
        if self.fail_prompt_marker and self.fail_prompt_marker in request.prompt:
            raise RuntimeError(f"provider failed for marker {self.fail_prompt_marker}")
        write_png(Path(request.output_path))
        return ImageGenerationResult(
            path=request.output_path,
            provider="fake",
            width=10,
            height=8,
            prompt_hash="x" * 16,
            sha256="y" * 64,
        )


def _storyboard() -> dict:
    return {
        "project_id": "prj_img",
        "summary": "Test storyboard.",
        "style_anchor": {
            "visual_language": "editorial",
            "palette": ["red", "blue"],
            "texture": ["grain"],
            "typography": "serif",
        },
        "characters": [{"character_id": "char_001", "name": "An", "description": "a cyclist"}],
        "locations": [{"location_id": "loc_001", "name": "old town"}],
        "scenes": [
            {
                "scene_id": "scene_001",
                "order": 1,
                "script_span": {"start_char": 0, "end_char": 5},
                "narration_text": "Nội dung 1.",
                "visual_summary": "s1",
                "image_prompt": "a cyclist in a lane",
                "negative_constraints": ["blur"],
            },
            {
                "scene_id": "scene_002",
                "order": 2,
                "script_span": {"start_char": 6, "end_char": 12},
                "narration_text": "Nội dung 2.",
                "visual_summary": "s2",
                "image_prompt": "rooftops at dawn",
                "negative_constraints": [],
            },
        ],
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


def seed_project(session, project_root: Path, project_id: str = "prj_img") -> None:
    store = AssetStore(project_root)
    store.init_project(project_id)
    ProjectRepo.create(session, project_id=project_id, title="Image")
    for order in (1, 2):
        SceneRepo.add(
            session,
            project_id,
            scene_id=f"scene_{order:03d}",
            order=order,
            narration_text=f"Nội dung {order}.",
            status="PLANNED",
        )
    session.commit()
    # Storyboard manifest needed for prompt building.
    store.write_manifest(project_id, "storyboard.json", _storyboard())


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# AC: generate toàn project
# --------------------------------------------------------------------------- #
def test_generates_all_roles_for_all_scenes(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    fake = FakeImage()
    svc = ImageGenerationService(fake, project_root=project_root)
    result = run(svc.generate_project("prj_img", session))

    assert result.total_scenes == 2
    assert result.scenes_ok == 2
    assert result.errors == []

    # Asset rows: 2 scenes x 5 roles = 10.
    assets = AssetRepo.list(session, "prj_img")
    assert len(assets) == 10
    roles = {a.role for a in assets}
    assert roles == set(ROLES)

    # Files exist on disk under images/.
    store = AssetStore(project_root)
    files = list(store.subdir("prj_img", "images").iterdir())
    assert len(files) == 10


def test_legacy_cliproxy_alias_uses_primary_provider(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    primary = FakeImage()
    fallback = FakeImage()
    svc = ImageGenerationService(
        primary,
        fallback_provider=fallback,
        project_root=project_root,
    )

    result = run(
        svc.generate_project(
            "prj_img",
            session,
            provider_name="cliproxy",
        )
    )

    assert result.scenes_ok == 2
    assert primary.calls
    assert not fallback.calls


def test_scene_selected_image_asset_id_set(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    fake = FakeImage()
    run(ImageGenerationService(fake, project_root=project_root).generate_project("prj_img", session))

    scenes = SceneRepo.list(session, "prj_img")
    for scene in scenes:
        assert scene.selected_image_asset_id is not None

    # Exactly one composite is selected per scene and the Scene foreign
    # reference uses that persisted Asset.asset_id (not a synthetic token).
    for scene in scenes:
        assets = AssetRepo.list(session, "prj_img", scene.scene_id)
        composites = [a for a in assets if a.role == "composite"]
        selected = [a for a in assets if a.selected]
        assert len(selected) == 1
        assert selected[0].role == "composite"
        assert selected[0] in composites
        assert scene.selected_image_asset_id == selected[0].asset_id


# --------------------------------------------------------------------------- #
# AC: fail một scene không mất scene khác
# --------------------------------------------------------------------------- #
def test_one_failing_scene_does_not_stop_others(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    # scene_001's prompts reference "a cyclist in a lane"; fail any request whose
    # prompt contains that marker so only scene_001 fails, scene_002 succeeds.
    fake = FakeImage(fail_prompt_marker="a cyclist in a lane")

    svc = ImageGenerationService(fake, project_root=project_root)
    result = run(svc.generate_project("prj_img", session))

    # The failing scene does not stop the other scene.
    assert result.total_scenes == 2
    assert result.scenes_ok == 1
    assert len(result.errors) == 1

    # scene_002 (rooftops) produced all 5 assets; scene_001 failed.
    scene1 = AssetRepo.list(session, "prj_img", "scene_001")
    scene2 = AssetRepo.list(session, "prj_img", "scene_002")
    assert len(scene2) == 5
    assert len(scene1) == 0


# --------------------------------------------------------------------------- #
# AC: retry
# --------------------------------------------------------------------------- #
def test_retry_transient_failure_succeeds(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    calls = {"n": 0}

    class FlakyImage(FakeImage):
        async def generate(self, request):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise RuntimeError("transient network")
            return await super().generate(request)

    fake = FlakyImage()
    svc = ImageGenerationService(fake, project_root=project_root)
    run(svc.generate_project("prj_img", session))
    # First two attempts failed, later succeeded -> some retries happened.
    assert calls["n"] > len(ROLES) * 2  # at least one role was retried


# --------------------------------------------------------------------------- #
# AC: select candidate / versioning
# --------------------------------------------------------------------------- #
def test_regenerate_bumps_version(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    fake = FakeImage()
    svc = ImageGenerationService(fake, project_root=project_root)
    run(svc.generate_project("prj_img", session))

    # Second run: cache should be hit (same prompts) -> no new files.
    fake.calls.clear()
    result2 = run(svc.generate_project("prj_img", session))
    assert result2.errors == []
    assert fake.calls == []  # cache reused, no provider calls

    # Version still 1 (cache reused, not regenerated).
    assets = AssetRepo.list(session, "prj_img")
    assert all(a.version == 1 for a in assets)


def test_cache_key_deterministic() -> None:
    assert role_cache_key("a", None, "16:9", "fake") == role_cache_key("a", None, "16:9", "fake")
    assert role_cache_key("a", 1, "16:9", "fake") != role_cache_key("a", 2, "16:9", "fake")


def test_cache_key_includes_model_negative_reference_and_provider_params() -> None:
    base = {
        "prompt": "a", "seed": 1, "aspect": "16:9", "provider": "fake",
        "model": "model-a", "negative_prompt": "blur",
        "reference_hashes": ("ref-a",), "provider_params": {"size": "1024x1024"},
    }

    assert role_cache_key(**base) != role_cache_key(**{**base, "model": "model-b"})
    assert role_cache_key(**base) != role_cache_key(**{**base, "negative_prompt": "text"})
    assert role_cache_key(**base) != role_cache_key(**{**base, "reference_hashes": ("ref-b",)})
    assert role_cache_key(**base) != role_cache_key(
        **{**base, "provider_params": {"size": "512x512"}}
    )



def test_style_change_creates_new_assets_and_return_to_style_reuses_cache(
    tmp_path, session, project_root
) -> None:
    seed_project(session, project_root)
    store = AssetStore(project_root)
    storyboard = _storyboard()
    storyboard["style_snapshot"] = {
        "schema_version": 1,
        "style_revision": 1,
        "preset": "editorial_collage",
        "visual_language": "style A",
        "palette": ["red"],
        "texture": ["paper"],
        "typography": "serif",
        "negative_prompt": [],
        "continuity_rules": [],
        "motion_profile": "default",
        "renderer_theme": {},
        "visual_hash": "style-A",
        "motion_hash": "motion-A",
        "render_theme_hash": "render-A",
    }
    store.write_manifest("prj_img", "storyboard.json", storyboard)
    fake = FakeImage()
    svc = ImageGenerationService(fake, project_root=project_root)

    first = run(svc.generate_project("prj_img", session))
    assert first.generated == 10
    assert len(AssetRepo.list(session, "prj_img")) == 10

    storyboard["style_snapshot"].update(
        style_revision=2,
        visual_language="style B",
        palette=["blue"],
        visual_hash="style-B",
    )
    store.write_manifest("prj_img", "storyboard.json", storyboard)
    fake.calls.clear()
    second = run(svc.generate_project("prj_img", session))
    assert second.generated == 10
    assert len(fake.calls) == 10
    assert len(AssetRepo.list(session, "prj_img")) == 20
    selected_b = [AssetRepo.get_selected_for_scene(session, "prj_img", f"scene_{i:03d}") for i in (1, 2)]
    assert all(asset is not None and asset.visual_style_hash == "style-B" for asset in selected_b)

    storyboard["style_snapshot"].update(
        style_revision=3,
        visual_language="style A",
        palette=["red"],
        visual_hash="style-A",
    )
    store.write_manifest("prj_img", "storyboard.json", storyboard)
    fake.calls.clear()
    third = run(svc.generate_project("prj_img", session))
    assert third.generated == 0
    assert third.cached == 10
    assert fake.calls == []
    assert len(AssetRepo.list(session, "prj_img")) == 20
    selected_a = [AssetRepo.get_selected_for_scene(session, "prj_img", f"scene_{i:03d}") for i in (1, 2)]
    assert all(asset is not None and asset.visual_style_hash == "style-A" for asset in selected_a)

def test_corrupt_cached_image_is_regenerated_and_counted(tmp_path, session, project_root) -> None:
    seed_project(session, project_root)
    fake = FakeImage()
    svc = ImageGenerationService(fake, project_root=project_root)
    first = run(svc.generate_project("prj_img", session))
    assert first.generated == 10
    assert first.cached == 0

    composite = next(
        asset for asset in AssetRepo.list(session, "prj_img") if asset.role == "composite"
    )
    Path(composite.path).write_bytes(b"corrupt")
    fake.calls.clear()

    second = run(svc.generate_project("prj_img", session))

    assert second.generated == 1
    assert second.cached == 9
    assert len(fake.calls) == 1
