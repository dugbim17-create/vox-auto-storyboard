"""Direct layer workflow (P5-T02).

Prepares a scene's layer package for the renderer. Runs when the provider
returned enough layers (Strategy A), producing normalized layers + a preview
composite + an asset manifest.

Steps per scene (MASTER_PLAN P5-T02):

- normalize canvas: each layer is scaled/placed so all layers share one common
  canvas size, aligned by role (background full-bleed, subject bottom-center,
  foreground full-frame overlay, texture full-frame);
- trim alpha: the subject/foreground transparent border is cropped to the
  tightest bounding box (cheaper composites + cleaner motion);
- preserve metadata: PNG info/tEXt (and a generated comment) are carried over;
- create preview composite: background + subject + foreground + texture are
  flattened onto a transparent canvas and exported to ``layers/preview.png``.

Output (AC):

- preview composite renders correctly (layers aligned + composited);
- layer alignment correct (each role lands in its anchor position);
- asset manifest complete (``manifests/asset_manifest.json`` with per-role
  records).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app.services.layer_validator import ALPHA_ROLES, LayerPackageValidator
from app.services.segmentation import (
    SegmentationBackend,
    derive_background,
    segment_subject,
)
from app.storage.asset_store import AssetStore

logger = logging.getLogger(__name__)


@dataclass
class PreparedLayer:
    """One normalized, metadata-preserved layer ready for the renderer."""

    role: str
    path: str  # normalized path under layers/
    width: int
    height: int
    ox: int  # offset x on canvas
    oy: int  # offset y on canvas
    alpha: bool


@dataclass
class SceneLayerResult:
    """Outcome of preparing one scene's layers."""

    scene_id: str
    ok: bool
    layers: list[PreparedLayer] = field(default_factory=list)
    preview_path: str = ""
    manifest_path: str = ""
    error: str = ""
    strategy: str = ""
    subject_found: bool = False
    subject_coverage: float = 0.0


class LayerWorkflowError(Exception):
    """Raised when layer preparation fails for a scene."""


class LayerWorkflow:
    """Prepare layer packages for the renderer (Direct layer workflow)."""

    def __init__(
        self,
        *,
        canvas_width: int = 1920,
        canvas_height: int = 1080,
        aspect_ratio: str = "16:9",
        project_root: str | Path | None = None,
        segmentation_backend: SegmentationBackend | None = None,
    ) -> None:
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.aspect_ratio = aspect_ratio
        self.project_root = project_root
        self.segmentation_backend = segmentation_backend

    # ------------------------------------------------------------------ #
    # Entrypoint
    # ------------------------------------------------------------------ #
    def prepare_scene(
        self,
        project_id: str,
        scene_id: str,
        layer_package: dict,
        *,
        store: AssetStore | None = None,
    ) -> SceneLayerResult:
        """Build normalized layers + preview composite + asset manifest for one scene."""
        store = store or AssetStore(self.project_root)
        result = SceneLayerResult(scene_id=scene_id, ok=True)

        # Validate first (P5-T01). Reject on structural problems.
        validator = LayerPackageValidator(
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            aspect_ratio=self.aspect_ratio,
        )
        vresult = validator.validate(layer_package)
        if not vresult.ok:
            result.ok = False
            result.error = "; ".join(vresult.messages)
            return result

        layers_dir = store.subdir(project_id, "layers")
        prepared: list[PreparedLayer] = []
        try:
            for role, entry in layer_package.items():
                src_path = entry if isinstance(entry, str) else entry.get("path")
                layer = self._prepare_one(
                    scene_id, role, str(src_path), layers_dir
                )
                prepared.append(layer)
            result.layers = prepared

            # Compose preview + write manifest.
            preview_path = self._write_preview(
                project_id, scene_id, prepared, store
            )
            result.preview_path = str(preview_path)

            manifest_path = self._write_manifest(
                project_id, scene_id, prepared, result.preview_path, store
            )
            result.manifest_path = str(manifest_path)
        except Exception as exc:  # noqa: BLE001
            result.ok = False
            result.error = str(exc)
            return result
        return result

    # ------------------------------------------------------------------ #
    # Strategy B entrypoint (P5-T03) — composite -> subject + background
    # ------------------------------------------------------------------ #
    def prepare_composite(
        self,
        project_id: str,
        scene_id: str,
        composite_path: str,
        *,
        store: AssetStore | None = None,
        require_subject: bool = False,
    ) -> SceneLayerResult:
        """Segment a single composite into a subject RGBA + opaque background.

        Runs when the provider only returned a full composite (Strategy B in
        MASTER_PLAN section 10.2). The composite is sliced via the segmentation
        adapter (P5-T03) into:

        - a ``composite`` layer (the full frame, alpha-carrying when a subject
          was found, else the opaque composite as-is);
        - a ``subject`` layer (RGBA cut-out when a subject was found, else the
          full composite as the fallback composite layer);
        - an opaque ``background`` layer (inpainted-lite or composite-derived).

        Returns a ``SceneLayerResult`` exactly like ``prepare_scene`` so callers
        can treat both strategies uniformly. Never raises for a missing subject —
        it falls back to the composite (AC: fallback uses the composite layer).
        """
        store = store or AssetStore(self.project_root)
        result = SceneLayerResult(scene_id=scene_id, ok=True)
        composite = Image.open(composite_path)
        composite = composite.convert("RGBA")

        try:
            seg = segment_subject(composite, backend=self.segmentation_backend)
            if require_subject and not seg.subject_found:
                result.ok = False
                result.error = "subject separation required for VOX layered render"
                result.strategy = "composite_fallback"
                return result
            subject_mask = seg.subject.getchannel("A") if seg.subject_found else None
            bg_result = derive_background(composite, subject_mask)

            layers_dir = store.subdir(project_id, "layers")
            prepared: list[PreparedLayer] = []
            # Preserve the legacy inspection/fallback contract for callers that
            # did not request strict VOX separation. The strict production path
            # intentionally excludes the full-frame composite so it cannot be
            # mistaken for an independently animated layer.
            if not require_subject:
                prepared.append(
                    self._save_layer(scene_id, "composite", composite, layers_dir),
                )
            if seg.subject_found:
                prepared.append(
                    self._save_layer(scene_id, "subject", seg.subject, layers_dir),
                )
            prepared.append(
                self._save_layer(
                    scene_id, "background", bg_result.background, layers_dir, opaque=True
                ),
            )

            result.layers = prepared
            result.strategy = (
                "segmented_composite" if seg.subject_found else "composite_fallback"
            )
            result.subject_found = seg.subject_found
            result.subject_coverage = seg.coverage
            preview_path = self._write_preview(project_id, scene_id, prepared, store)
            result.preview_path = str(preview_path)
            manifest_path = self._write_manifest(
                project_id,
                scene_id,
                prepared,
                result.preview_path,
                store,
                strategy=result.strategy,
                subject_found=result.subject_found,
                subject_coverage=result.subject_coverage,
            )
            result.manifest_path = str(manifest_path)
        except Exception as exc:  # noqa: BLE001
            result.ok = False
            result.error = str(exc)
            return result
        return result

    # ------------------------------------------------------------------ #
    # Per-layer preparation
    # ------------------------------------------------------------------ #
    def _prepare_one(
        self,
        scene_id: str,
        role: str,
        src_path: str,
        layers_dir: Path,
    ) -> PreparedLayer:
        """Normalize one layer + trim alpha + preserve metadata."""
        with Image.open(src_path) as img:
            img.load()
            base_mode = img.mode
            has_alpha = "A" in base_mode.upper()

            # Normalize to RGBA so compositing is uniform.
            img = img.convert("RGBA")

            # Trim transparent border on alpha layers.
            if has_alpha:
                img = _trim_alpha(img, role)

            # Scale/cover-fit to canvas keeping aspect, then place at anchor.
            scaled = _cover_fit(img, self.canvas_width, self.canvas_height)
            ox, oy = _anchor_offset(role, scaled.size, self.canvas_width, self.canvas_height)

        # Preserve metadata into the saved PNG comment.
        meta = _metadata(src_path, role)
        out_name = f"{scene_id}_{role}.png"
        out_path = layers_dir / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        scaled.save(out_path, format="PNG", pnginfo=_png_info(meta))

        return PreparedLayer(
            role=role,
            path=str(out_path),
            width=self.canvas_width,
            height=self.canvas_height,
            ox=ox,
            oy=oy,
            alpha=role in ALPHA_ROLES,
        )

    def _save_layer(
        self,
        scene_id: str,
        role: str,
        img: Image.Image,
        layers_dir: Path,
        *,
        opaque: bool = False,
    ) -> PreparedLayer:
        """Save an in-memory RGBA image as a normalized layer (Strategy B).

        Mirrors ``_prepare_one`` but for images that are already processed
        (a segmented subject / derived background / raw composite), so the
        Strategy B path can reuse the same preview + manifest writers.
        """
        img = img.convert("RGBA")
        if opaque or role not in ALPHA_ROLES:
            img = _force_opaque(img)

        scaled = _cover_fit(img, self.canvas_width, self.canvas_height)
        ox, oy = _anchor_offset(role, scaled.size, self.canvas_width, self.canvas_height)

        meta = {"Role": role, "Comment": "prepared by layer_workflow (segmentation)"}
        out_name = f"{scene_id}_{role}.png"
        out_path = layers_dir / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        scaled.save(out_path, format="PNG", pnginfo=_png_info(meta))

        return PreparedLayer(
            role=role,
            path=str(out_path),
            width=self.canvas_width,
            height=self.canvas_height,
            ox=ox,
            oy=oy,
            alpha=role in ALPHA_ROLES,
        )

    def _write_preview(
        self, project_id: str, scene_id: str, layers: list[PreparedLayer], store: AssetStore
    ) -> Path:
        """Composite all layers (by z-order) onto a transparent canvas."""
        canvas = Image.new("RGBA", (self.canvas_width, self.canvas_height), (0, 0, 0, 0))
        for layer in layers:
            with Image.open(layer.path) as img:
                img = img.convert("RGBA")
            # Background (opaque) first, then alpha layers on top.
            if layer.role == "background":
                canvas.paste(img, (layer.ox, layer.oy))
            else:
                canvas.alpha_composite(img, (layer.ox, layer.oy))

        preview_dir = store.subdir(project_id, "layers")
        out_path = preview_dir / f"{scene_id}_preview.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path, format="PNG")
        return out_path

    def _write_manifest(
        self,
        project_id: str,
        scene_id: str,
        layers: list[PreparedLayer],
        preview_path: str,
        store: AssetStore,
        *,
        strategy: str = "provider_layers",
        subject_found: bool = False,
        subject_coverage: float = 0.0,
    ) -> Path:
        """Persist the asset manifest under manifests/."""
        record = {
            "scene_id": scene_id,
            "canvas": {
                "width": self.canvas_width,
                "height": self.canvas_height,
                "aspect_ratio": self.aspect_ratio,
            },
            "preview": preview_path,
            "strategy": strategy,
            "subject_found": subject_found,
            "subject_coverage": subject_coverage,
            "layers": [
                {
                    "role": layer.role,
                    "path": layer.path,
                    "width": layer.width,
                    "height": layer.height,
                    "ox": layer.ox,
                    "oy": layer.oy,
                    "alpha": layer.alpha,
                }
                for layer in layers
            ],
        }
        path, _digest = store.write_manifest(
            project_id, f"asset_manifest_{scene_id}.json", record
        )
        return path


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _force_opaque(img: Image.Image) -> Image.Image:
    """Return a copy of the image with a fully opaque alpha channel."""
    out = img.convert("RGBA")
    out.putalpha(Image.new("L", img.size, 255))
    return out


def _cover_fit(img: Image.Image, canvas_width: int, canvas_height: int) -> Image.Image:
    """Scale+center-crop to fill the canvas while preserving aspect (cover-fit)."""
    src_w, src_h = img.size
    target_ratio = canvas_width / canvas_height
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        # Too wide -> crop width; scale by height.
        new_h = canvas_height
        new_w = int(canvas_height * src_ratio)
    else:
        new_w = canvas_width
        new_h = int(canvas_width / src_ratio)
    img = img.resize((max(new_w, 1), max(new_h, 1)), Image.LANCZOS)
    left = (img.width - canvas_width) // 2
    top = (img.height - canvas_height) // 2
    return img.crop((left, top, left + canvas_width, top + canvas_height))


def _trim_alpha(image: Image.Image, role: str) -> Image.Image:
    """Crop the transparent bounding box of an alpha layer (subject/fg)."""
    try:
        bbox = image.getbbox()
    except Exception:  # noqa: BLE001
        return image
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return image.crop(bbox)


def _anchor_offset(
    role: str, size: tuple[int, int], canvas_width: int, canvas_height: int
) -> tuple[int, int]:
    """Return the top-left position (ox, oy) for a role on the canvas.

    - background: full-bleed (top-left 0,0);
    - subject / composite: horizontally centered, vertically bottom-anchored
      (hero sits on the ground line);
    - texture / foreground: centered (overlay areas).
    """
    w, h = size
    if role == "background":
        return 0, 0
    if role in ("subject", "composite"):
        return (canvas_width - w) // 2, canvas_height - h
    return (canvas_width - w) // 2, (canvas_height - h) // 2


def _metadata(src_path: str, role: str) -> dict[str, str]:
    """Extract PNG metadata (tEXt/ZTXt) + add role for preservation."""
    info: dict[str, str] = {}
    try:
        with Image.open(src_path) as img:
            for key in ("Comment", "Software", "Source", "Role"):
                if key in img.info:
                    info[key] = str(img.info[key])
    except Exception:  # noqa: BLE001
        pass
    info["Role"] = role
    info["Comment"] = "prepared by layer_workflow"
    return info


def _png_info(meta: dict[str, str]):
    """Return a PngInfo carrying the preserved metadata."""
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    for key, value in meta.items():
        info.add_text(key, value)
    return info
