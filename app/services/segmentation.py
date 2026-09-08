"""Segmentation fallback adapter (P5-T03, Strategy B).

When an image provider only returns a single full composite (Strategy B in
MASTER_PLAN section 10.2), the renderer still needs an alpha-carrying subject
and an opaque background. This module slices those out of the composite:

- composite -> subject RGBA (foreground cut from the composed image);
- background fallback (an opaque layer derived from the composite when none is
  provided);
- mask cleanup (threshold + keep the largest connected component);
- edge feather (blur the alpha so the cut subject composites smoothly).

The segmentation backend (``rembg`` by default) is a small Protocol so tests
can inject a deterministic fake and skip a model download / GPU load. The real
backend is imported lazily — importing this module never imports ``rembg``.

Acceptance criteria (MASTER_PLAN P5-T03):

- fixture subject produces a valid alpha channel;
- does not crash when no subject is found;
- fallback uses the composite layer.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Protocol, cast

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

# Fallback model for the real rembg backend. Deterministic per process.
DEFAULT_MODEL = "isnet-general-use"

# A binary mask below this covered fraction counts as "no subject found",
# triggering the composite fallback.
MIN_SUBJECT_COVERAGE = 0.005
# Alpha values below this are treated as background before component analysis.
THRESHOLD = 128


class SegmentationBackend(Protocol):
    """Produce a foreground mask for a full composite.

    Implementations return an image whose luminance is 0 (background) .. 255
    (foreground); the alpha channel may also already carry the cut-out (a
    full RGBA output is collapsed to its alpha channel).
    """

    def produce_mask(self, image: Image.Image) -> Image.Image:
        """Return a mask for the image in [0, 255], 255 = subject."""
        ...


class RembgBackend:
    """Segmentation backend backed by ``rembg`` (lazy session).

    The onnx session is created on first use (heavy), so importing this class
    costs nothing until the model actually runs.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._session = None
        self._lock = threading.Lock()

    def _get_session(self):
        from rembg import new_session  # lazy: heavy import stays out of import path

        if self._session is None:
            with self._lock:
                if self._session is None:
                    logger.info("loaded rembg session '%s'", self.model_name)
                    self._session = new_session(self.model_name)
        return self._session

    def produce_mask(self, image: Image.Image) -> Image.Image:
        from rembg import remove  # lazy

        out = remove(image.convert("RGB"), session=self._get_session())
        out_img: Image.Image = cast(Image.Image, out)
        return out_img.convert("RGBA").split()[3]  # alpha channel as the mask


@dataclass
class SegmentationResult:
    """Outcome of segmenting one composite image."""

    subject: Image.Image  # RGBA, subject cut out of the composite
    subject_found: bool  # False -> ``subject`` is the whole composite (fallback)
    coverage: float  # fraction of frame occupied by the (clean) subject mask
    method: str = "segmentation"  # 'segmentation' | 'fallback'
    # Optional. When set, a native PIL operation path exists.
    backend: str = ""


@dataclass
class BackgroundResult:
    """Outcome of deriving an opaque background layer."""

    background: Image.Image  # opaque RGB/RGBA or fallback composite
    source: str  # 'provided' | 'derived' | 'composite_fallback'
    inpainted: bool = False


def segment_subject(
    composite: Image.Image,
    *,
    backend: SegmentationBackend | None = None,
    threshold: int = THRESHOLD,
    min_coverage: float = MIN_SUBJECT_COVERAGE,
    feather_radius: int = 2,
) -> SegmentationResult:
    """Turn a composite into an RGBA subject layer.

    Steps: run the backend to get a raw mask, clean it (threshold + largest
    connected component), then cut the subject out of the composite. When the
    mask is empty/by too small, fall back to the full composite.
    """
    backend = backend or _default_backend()
    img = composite.convert("RGBA")

    try:
        raw_mask = backend.produce_mask(img)
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        logger.warning("segmentation backend failed (%s); using composite fallback", exc)
        raw_mask = None

    if raw_mask is not None:
        mask = _refine_mask(raw_mask, threshold)
        if mask is not None:
            coverage = _coverage(mask)
            if coverage >= min_coverage:
                subject = _apply_mask(img, mask)
                subject = _feather(subject, feather_radius)
                return SegmentationResult(
                    subject=subject, subject_found=True, coverage=coverage,
                    backend=str(type(backend).__name__),
                )
            logger.debug("subject coverage %.3f below %.3f; composite fallback", coverage, min_coverage)

    # Fallback: the composite is the subject (Strategy B, AC: fallback uses composite).
    return SegmentationResult(
        subject=img, subject_found=False, coverage=1.0, backend="fallback"
    )


def derive_background(
    composite: Image.Image,
    subject_mask: Image.Image | None = None,
) -> BackgroundResult:
    """Derive an opaque background layer, with a provided composite.

    When a subject mask is given, the subject region is filled with a heavily
    blurred copy of the composite (cheap inpaint-lite); otherwise the composite
    is used as an opaque background. Always returns an image with fully opaque
    alpha.
    """
    img = composite.convert("RGBA")
    if subject_mask is not None:
        mask = _refine_mask(subject_mask, THRESHOLD)
        if mask is not None:
            blurred = img.filter(ImageFilter.GaussianBlur(60))
            # where mask = subject -> blurred (hides the subject); bg = original.
            blended = Image.composite(blurred, img, mask)
            blended.putalpha(Image.new("L", img.size, 255))
            return BackgroundResult(background=blended, source="derived", inpainted=True)

    # No mask: composite used opaque as-is.
    opaque = img.copy()
    opaque.putalpha(Image.new("L", img.size, 255))
    return BackgroundResult(background=opaque, source="composite_fallback")


def ensure_background(
    image: Image.Image, *, provided: Image.Image | None = None
) -> BackgroundResult:
    """Return an opaque background, preferring a provided opaque layer."""
    if provided is not None:
        bg = provided.convert("RGBA")
        if bg.getchannel("A").getextrema()[0] >= 255:  # already opaque
            return BackgroundResult(background=bg, source="provided")
        return BackgroundResult(
            background=_force_opaque(bg), source="provided", inpainted=True
        )
    return derive_background(image)


# --------------------------------------------------------------------------- #
# Mask helpers
# --------------------------------------------------------------------------- #
def _refine_mask(mask: Image.Image, threshold: int) -> Image.Image | None:
    """Threshold the mask and keep only its largest connected component."""
    arr = np.asarray(mask.convert("L"), dtype=np.uint8)
    binary = arr >= threshold
    if not binary.any():
        return None
    binary = _largest_component(binary)
    if not binary.any():
        return None
    out = np.where(binary, 255, 0).astype(np.uint8)
    return Image.fromarray(out, mode="L")


def _largest_component(binary: np.ndarray) -> np.ndarray:
    """Return a bool array masking only the largest 4-connected component."""
    if not binary.any():
        return binary
    h, w = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    best = None
    best_area = 0
    stack = []
    for sy in range(h):
        for sx in range(w):
            if binary[sy, sx] and not visited[sy, sx]:
                # BFS/DFS to mark this component.
                comp = np.zeros_like(binary, dtype=bool)
                stack[:] = []
                stack.append((sy, sx))
                visited[sy, sx] = True
                area = 0
                while stack:
                    y, x = stack.pop()
                    if not binary[y, x]:
                        continue
                    comp[y, x] = True
                    area += 1
                    for ny, nx in _neighbors(y, x, h, w):
                        if binary[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                if area > best_area:
                    best_area = area
                    best = comp
    return best if best is not None else binary


def _neighbors(y: int, x: int, h: int, w: int):
    if y > 0:
        yield y - 1, x
    if y < h - 1:
        yield y + 1, x
    if x > 0:
        yield y, x - 1
    if x < w - 1:
        yield y, x + 1


def _coverage(mask: Image.Image) -> float:
    arr = np.asarray(mask.convert("L"), dtype=np.uint8)
    total = arr.size
    if total == 0:
        return 0.0
    foreground = int((arr > 0).sum())
    return foreground / total


def _apply_mask(img_rgba: Image.Image, mask: Image.Image) -> Image.Image:
    r, g, b, _ = img_rgba.split()
    return Image.merge("RGBA", (r, g, b, mask))


def _feather(img: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return img
    r, g, b, a = img.split()
    a = a.filter(ImageFilter.GaussianBlur(radius))
    return Image.merge("RGBA", (r, g, b, a))


def _force_opaque(img: Image.Image) -> Image.Image:
    out = img.convert("RGBA")
    out.putalpha(Image.new("L", img.size, 255))
    return out


_default = None


def _default_backend() -> SegmentationBackend:
    global _default
    if _default is None:
        _default = RembgBackend()
    return _default
