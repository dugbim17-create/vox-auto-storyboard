"""Image generation service (P4-T05).

Generates per-scene, per-role image candidates for a project through an image
provider, with cache identity and per-run accounting tied to the complete
request contract.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.job_runner import Job, JobRunner
from app.core.state_machine import StateMachine
from app.providers.base import ImageGenerationRequest, ImageGenerationResult
from app.services.scene_image_prompt import SceneImagePromptBuilder
from app.storage.asset_store import AssetStore, sha256_file
from app.storage.repositories import AssetRepo, SceneRepo

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_PROVIDER = "antigravity_image"
FALLBACK_IMAGE_PROVIDER = "antigravity_image"
IMAGE_EXT = ".jpg"
ROLE_ORDER = ("composite", "background", "subject", "foreground", "texture")
MAX_ATTEMPTS_PER_ROLE = 3


class ImageGenerationError(Exception):
    """Raised when a role generation is unrecoverable."""


@dataclass
class RoleImageResult:
    project_id: str
    scene_id: str
    role: str
    path: str
    provider: str
    prompt_hash: str
    sha256: str
    width: int
    height: int
    version: int
    cached: bool
    fallback_used: bool = False
    visual_style_hash: str | None = None
    model: str = ""
    cache_identity: str = ""


@dataclass
class SceneImageOutcome:
    scene_id: str
    ok: bool
    selected_asset_id: str | None = None
    roles_ok: int = 0
    generated: int = 0
    cached: int = 0
    error: str = ""


@dataclass
class ImagePipelineResult:
    project_id: str
    total_scenes: int
    generated: int = 0
    cached: int = 0
    scenes_ok: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_ms: int = 0


def role_cache_key(
    prompt: str,
    seed: int | None,
    aspect: str,
    provider: str,
    *,
    model: str = "",
    negative_prompt: str = "",
    reference_hashes: tuple[str, ...] | list[str] = (),
    provider_params: dict[str, Any] | None = None,
    visual_style_hash: str = "",
    project_id: str = "",
    scene_id: str = "",
    role: str = "",
) -> str:
    """Hash the complete namespaced request identity for one role artifact."""
    payload = {
        "project_id": project_id,
        "scene_id": scene_id,
        "role": role,
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "reference_hashes": list(reference_hashes),
        "aspect_ratio": aspect,
        "seed": seed,
        "provider_params": provider_params or {},
        "visual_style_hash": visual_style_hash,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ImageGenerationService:
    """Orchestrates per-scene image generation for a project."""

    def __init__(
        self,
        image_provider: Any,
        *,
        prompt_builder: SceneImagePromptBuilder | None = None,
        runner: JobRunner | None = None,
        fallback_provider: Any | None = None,
        aspect_ratio: str = "16:9",
        seed: int | None = None,
        project_root: str | Path | None = None,
        provider_params: dict[str, Any] | None = None,
        model: str = "",
        provider_name: str | None = None,
        flowkit_provider: Any | None = None,
        cliproxy_provider: Any | None = None,
    ) -> None:
        self.provider = image_provider
        self.provider_name = provider_name
        self.fallback_provider = fallback_provider
        self.flowkit_provider = flowkit_provider
        self.cliproxy_provider = cliproxy_provider
        self.builder = prompt_builder or SceneImagePromptBuilder(aspect_ratio=aspect_ratio)
        self.aspect_ratio = aspect_ratio
        self.seed = seed
        self.project_root = project_root
        self.provider_params = dict(provider_params or {})
        self.model = model or str(getattr(image_provider, "model", ""))
        self._runner = runner or JobRunner()

    async def generate_project(
        self,
        project_id: str,
        session: Any,
        *,
        project_root: str | Path | None = None,
        provider_name: str | None = None,
    ) -> ImagePipelineResult:
        """Generate image candidates for every scene."""
        start = time.monotonic()
        store = AssetStore(project_root or self.project_root)
        scenes = SceneRepo.list(session, project_id)
        result = ImagePipelineResult(project_id=project_id, total_scenes=len(scenes))
        provider_name = provider_name or self.provider_name or getattr(self.provider, "provider_name", DEFAULT_IMAGE_PROVIDER)

        state = StateMachine(session)
        try:
            state.transition_project(project_id, "IMAGES_GENERATING", reason="images started")
        except Exception as exc:  # noqa: BLE001
            logger.warning("project transition to IMAGES_GENERATING skipped: %s", exc)

        storyboard = self._load_storyboard(project_id, store)
        if not storyboard:
            result.errors.append(f"project {project_id} has no storyboard manifest")
            return result

        plans_by_scene = self.builder.build(storyboard)
        for scene in scenes:
            outcome = await self._process_scene(
                project_id, scene, plans_by_scene, store, session, provider_name
            )
            if outcome.ok:
                result.scenes_ok += 1
            else:
                result.errors.append(f"{outcome.scene_id}: {outcome.error}")
            result.generated += outcome.generated
            result.cached += outcome.cached

        if result.scenes_ok > 0:
            try:
                state.transition_project(project_id, "IMAGES_READY", reason="images ready")
            except Exception as exc:  # noqa: BLE001
                logger.warning("project transition to IMAGES_READY skipped: %s", exc)
        session.commit()
        result.elapsed_ms = int((time.monotonic() - start) * 1000)
        return result

    async def generate_scene(
        self,
        project_id: str,
        scene_id: str,
        session: Any,
        *,
        project_root: str | Path | None = None,
        provider_name: str | None = None,
    ) -> SceneImageOutcome:
        """Generate and select real image assets for one user-selected scene."""
        store = AssetStore(project_root or self.project_root)
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None:
            raise ImageGenerationError(f"scene not found: {project_id}/{scene_id}")
        storyboard = self._load_storyboard(project_id, store)
        if not storyboard:
            raise ImageGenerationError(f"project {project_id} has no storyboard manifest")
        plans_by_scene = self.builder.build(storyboard)
        selected_provider = (
            provider_name
            or self.provider_name
            or getattr(self.provider, "provider_name", DEFAULT_IMAGE_PROVIDER)
        )
        return await self._process_scene(
            project_id,
            scene,
            plans_by_scene,
            store,
            session,
            selected_provider,
        )

    async def _process_scene(
        self,
        project_id: str,
        scene: Any,
        plans_by_scene: dict[str, list[Any]],
        store: AssetStore,
        session: Any,
        provider_name: str,
    ) -> SceneImageOutcome:
        scene_id = scene.scene_id
        plans = plans_by_scene.get(scene_id, [])
        outcome = SceneImageOutcome(scene_id=scene_id, ok=True)
        for plan in plans:
            try:
                meta = await self._generate_role(project_id, scene, plan, store, provider_name)
            except Exception as exc:  # noqa: BLE001
                outcome.ok = False
                outcome.error = str(exc)
                break
            self._persist_asset(session, meta)
            outcome.roles_ok += 1
            if meta.cached:
                outcome.cached += 1
            else:
                outcome.generated += 1
        session.commit()

        if not outcome.ok:
            return outcome
        selected = self._select_candidate(
            session,
            project_id,
            scene_id,
            visual_style_hash=self._visual_style_hash(store, project_id),
        )
        outcome.selected_asset_id = selected
        try:
            StateMachine(session).transition_scene(
                project_id, scene_id, "IMAGE_READY", reason="images generated"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("scene %s transition skipped: %s", scene_id, exc)
        session.commit()
        return outcome

    async def _generate_role(
        self,
        project_id: str,
        scene: Any,
        plan: Any,
        store: AssetStore,
        provider_name: str,
    ) -> RoleImageResult:
        stem = f"{scene.scene_id}_{plan.role}"
        job = Job(
            job_id=f"{stem}_{int(time.time() * 1000)}",
            provider=provider_name,
            fn=self._generate_job,
            kwargs={
                "project_id": project_id,
                "scene": scene,
                "plan": plan,
                "store": store,
                "provider_name": provider_name,
            },
            max_attempts=MAX_ATTEMPTS_PER_ROLE,
            timeout_seconds=300.0,
        )
        await self._runner.submit(job, concurrency_limit=1)
        await self._runner.wait(job.job_id)
        if job.status != "succeeded":
            raise ImageGenerationError(f"{scene.scene_id}/{plan.role}: {job.error}")
        return job.result

    async def _generate_job(
        self, *, project_id, scene, plan, store, provider_name
    ) -> RoleImageResult:
        canonical, primary, primary_model = self._resolve_provider(provider_name)
        cached = self._find_cached(
            project_id,
            scene,
            plan,
            store,
            canonical,
            model=primary_model,
        )
        if cached is not None:
            return cached
        try:
            return await self._run_generate(
                project_id,
                scene,
                plan,
                store,
                canonical,
                provider=primary,
            )
        except Exception as exc:  # noqa: BLE001
            if self.fallback_provider is not None:
                logger.warning(
                    "%s/%s: primary %s failed (%s); falling back",
                    scene.scene_id,
                    plan.role,
                    canonical,
                    exc,
                )
                fallback_name, fallback, fallback_model = self._resolve_provider(
                    FALLBACK_IMAGE_PROVIDER,
                    provider=self.fallback_provider,
                )
                cached_fallback = self._find_cached(
                    project_id,
                    scene,
                    plan,
                    store,
                    fallback_name,
                    model=fallback_model,
                )
                if cached_fallback is not None:
                    cached_fallback.fallback_used = True
                    return cached_fallback
                result = await self._run_generate(
                    project_id,
                    scene,
                    plan,
                    store,
                    fallback_name,
                    provider=fallback,
                )
                result.fallback_used = True
                return result
            raise

    def _cache_key(
        self,
        plan: Any,
        provider_name: str,
        *,
        project_id: str = "",
        scene_id: str = "",
        model: str | None = None,
        visual_style_hash: str = "",
    ) -> str:
        negative_prompt = ", ".join(plan.negative_constraints)
        reference_hashes = tuple(_hash_reference(path) for path in plan.reference_images)
        return role_cache_key(
            plan.prompt,
            self.seed,
            self.aspect_ratio,
            provider_name,
            model=self.model if model is None else model,
            negative_prompt=negative_prompt,
            reference_hashes=reference_hashes,
            provider_params=self.provider_params,
            visual_style_hash=visual_style_hash,
            project_id=project_id,
            scene_id=scene_id,
            role=str(getattr(plan, "role", "")),
        )

    def _find_cached(
        self,
        project_id: str,
        scene: Any,
        plan: Any,
        store: AssetStore,
        provider_name: str,
        *,
        model: str = "",
    ) -> RoleImageResult | None:
        visual_style_hash = self._visual_style_hash(store, project_id)
        key = self._cache_key(
            plan,
            provider_name,
            project_id=project_id,
            scene_id=scene.scene_id,
            model=model,
            visual_style_hash=visual_style_hash,
        )
        stem = f"{scene.scene_id}_{plan.role}_{key}"
        images_dir = store.subdir(project_id, "images")
        matches = sorted(
            [*images_dir.glob(f"{stem}_v*.jpg"), *images_dir.glob(f"{stem}_v*.png")],
            key=lambda path: path.name,
            reverse=True,
        )
        for candidate in matches:
            if candidate.stat().st_size == 0:
                continue
            width, height = _read_image_dimensions(candidate)
            if width <= 0 or height <= 0:
                continue
            try:
                version = int(candidate.stem.rsplit("_v", 1)[1])
            except (ValueError, IndexError):
                version = 1
            return RoleImageResult(
                project_id=project_id,
                scene_id=scene.scene_id,
                role=plan.role,
                path=str(candidate),
                provider=provider_name,
                prompt_hash=key,
                sha256=sha256_file(candidate),
                width=width,
                height=height,
                version=version,
                cached=True,
                visual_style_hash=visual_style_hash or None,
                model=model,
                cache_identity=key,
            )
        return None

    async def _run_generate(
        self,
        project_id: str,
        scene: Any,
        plan: Any,
        store: AssetStore,
        provider_name: str,
        *,
        provider: Any | None = None,
    ) -> RoleImageResult:
        canonical_provider, provider, provider_model = self._resolve_provider(
            provider_name,
            provider=provider,
        )
        visual_style_hash = self._visual_style_hash(store, project_id)
        key = self._cache_key(
            plan,
            canonical_provider,
            project_id=project_id,
            scene_id=scene.scene_id,
            model=provider_model,
            visual_style_hash=visual_style_hash,
        )
        stem = f"{scene.scene_id}_{plan.role}"
        version = self._next_version(store, project_id, stem)
        path = store.versioned_path(project_id, "images", f"{stem}_{key}", IMAGE_EXT, version)
        req = ImageGenerationRequest(
            prompt=plan.prompt,
            role=plan.role,
            negative_prompt=", ".join(plan.negative_constraints),
            reference_images=list(plan.reference_images),
            aspect_ratio=plan.aspect_ratio,
            seed=self.seed,
            candidate_count=1,
            output_path=str(path),
            provider_params=self.provider_params,
        )
        if provider is None:
            provider = self.provider
        if canonical_provider == "flowkit" and getattr(self, "flowkit_provider", None) is not None:
            provider = self.flowkit_provider
        if (
            provider is self.provider
            and canonical_provider == "cliproxy_image"
            and getattr(self, "cliproxy_provider", None) is not None
        ):
            provider = self.cliproxy_provider
        if provider is None:
            raise ImageGenerationError(f"no provider registered for {provider_name!r}")
        gen: ImageGenerationResult = await provider.generate(req)
        if not path.is_file() or path.stat().st_size == 0:
            raise ImageGenerationError(f"provider returned no image file: {path}")
        width, height = _read_image_dimensions(path)
        if width <= 0 or height <= 0:
            raise ImageGenerationError(f"provider returned undecodable image: {path}")
        return RoleImageResult(
            project_id=project_id,
            scene_id=scene.scene_id,
            role=plan.role,
            path=str(path),
            provider=str(getattr(provider, "provider_name", "") or canonical_provider),
            prompt_hash=key,
            sha256=gen.sha256 or sha256_file(path),
            width=gen.width or width,
            height=gen.height or height,
            version=version,
            cached=False,
            visual_style_hash=visual_style_hash or None,
            model=provider_model,
            cache_identity=key,
        )

    def _next_version(self, store: AssetStore, project_id: str, stem: str) -> int:
        images_dir = store.subdir(project_id, "images")
        matches = list(images_dir.glob(f"{stem}_*_v*.jpg")) + list(images_dir.glob(f"{stem}_*_v*.png"))
        versions = []
        for match in matches:
            try:
                versions.append(int(match.stem.rsplit("_v", 1)[1]))
            except (ValueError, IndexError):
                continue
        return max(versions, default=0) + 1

    def _select_candidate(
        self,
        session,
        project_id: str,
        scene_id: str,
        *,
        visual_style_hash: str = "",
    ) -> str | None:
        assets = AssetRepo.list(session, project_id, scene_id)
        if not assets:
            return None
        composites = [asset for asset in assets if asset.role == "composite"]
        pool = composites or assets
        if visual_style_hash:
            pool = [asset for asset in pool if asset.visual_style_hash == visual_style_hash]
            if not pool:
                return None
        target = max(pool, key=lambda asset: (asset.version, asset.id))
        for asset in assets:
            asset.selected = False
        target.selected = True
        SceneRepo.set_selected_image(session, project_id, scene_id, str(target.asset_id))
        session.commit()
        return str(target.asset_id)

    def _resolve_provider(
        self,
        provider_name: str,
        *,
        provider: Any | None = None,
    ) -> tuple[str, Any | None, str]:
        canonical = {
            "cliproxy": "cliproxy_image",
            "antigravity": "antigravity_image",
        }.get(provider_name, provider_name)
        resolved = provider if provider is not None else self.provider
        if provider is None and canonical == "flowkit" and self.flowkit_provider is not None:
            resolved = self.flowkit_provider
        if provider is None and canonical == "cliproxy_image" and self.cliproxy_provider is not None:
            resolved = self.cliproxy_provider
        model = str(getattr(resolved, "model", "") or self.model)
        return canonical, resolved, model

    def _persist_asset(self, session, meta: RoleImageResult) -> None:
        AssetRepo.upsert(
            session,
            meta.project_id,
            meta.scene_id,
            asset_id=f"{meta.scene_id}_{meta.role}_v{meta.version:03d}",
            role=meta.role,
            path=meta.path,
            provider=meta.provider,
            prompt_hash=meta.prompt_hash,
            visual_style_hash=meta.visual_style_hash,
            model=meta.model,
            cache_identity=meta.cache_identity or meta.prompt_hash,
            sha256=meta.sha256,
            width=meta.width,
            height=meta.height,
            version=meta.version,
            selected=False,
        )

    def _visual_style_hash(self, store: AssetStore, project_id: str) -> str:
        storyboard = self._load_storyboard(project_id, store)
        snapshot = storyboard.get("style_snapshot") if isinstance(storyboard, dict) else None
        return str(snapshot.get("visual_hash") or "") if isinstance(snapshot, dict) else ""

    def _load_storyboard(self, project_id: str, store: AssetStore) -> dict[str, Any]:
        try:
            raw = store.read_project_file(project_id, "manifests/storyboard.json")
            return json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}


def _hash_reference(path: str) -> str:
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        return path
    return sha256_file(candidate)


def _read_image_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:  # noqa: BLE001
        return 0, 0
