"""Tests for P5-T03 segmentation fallback.

Covers the acceptance criteria:

- fixture subject produces a valid alpha channel;
- does not crash when no subject is found (falls back to the composite layer);
- mask cleanup (threshold + largest connected component removes specks);
- edge feather (alpha softens at the boundary);
- background fallback (an opaque background derived from the composite).
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.services.segmentation import (
    BackgroundResult,
    RembgBackend,
    SegmentationResult,
    _coverage,
    _refine_mask,
    derive_background,
    ensure_background,
    segment_subject,
)


class FakeBackend:
    """Deterministic segmentation backend for tests (no model download)."""

    def __init__(self, mask: Image.Image | None) -> None:
        self.mask = mask

    def produce_mask(self, image: Image.Image) -> Image.Image:
        del image  # ignored: a deterministic mask is returned regardless
        return self.mask


def composite(*, size=(320, 240), color=(30, 60, 120)) -> Image.Image:
    return Image.new("RGBA", size, color + (255,))


def rect_mask(size=(320, 240), box=(80, 50, 200, 150)) -> Image.Image:
    """A solid white subject region on black background."""
    m = Image.new("L", size, 0)
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            m.putpixel((x, y), 255)
    return m


def composite_with_subject(*, size=(320, 240), bg=(30, 60, 120), subject=(255, 0, 0)) -> Image.Image:
    """Composite whose subject box carries a color distinct from the background."""
    img = Image.new("RGBA", size, bg + (255,))
    for y in range(50, 150):
        for x in range(80, 200):
            img.putpixel((x, y), subject + (255,))
    return img


def empty_mask(size=(320, 240)) -> Image.Image:
    return Image.new("L", size, 0)


def speckled_mask(size=(320, 240), box=(80, 50, 200, 150)) -> Image.Image:
    """Subject region plus a few isolated specks (to be cleaned)."""
    m = rect_mask(size, box)
    m.putpixel((2, 2), 255)
    m.putpixel((300, 230), 255)
    m.putpixel((5, 220), 255)
    return m


# --------------------------------------------------------------------------- #
# AC: fixture subject produces a valid alpha channel
# --------------------------------------------------------------------------- #
def test_segment_subject_produces_alpha() -> None:
    img = composite()
    r = segment_subject(img, backend=FakeBackend(rect_mask()), feather_radius=0)
    assert isinstance(r, SegmentationResult)
    assert r.subject_found
    assert r.subject.mode == "RGBA"
    arr = np.asarray(r.subject)
    # alpha is nonzero only inside the subject rectangle
    alpha = arr[..., 3]
    assert (alpha > 0).sum() > 0
    assert alpha.max() == 255
    assert r.subject.getbbox() == (80, 50, 200, 150)


def test_subject_alpha_matches_mask_bounds() -> None:
    img = composite()
    r = segment_subject(img, backend=FakeBackend(rect_mask()), feather_radius=0)
    arr = np.asarray(r.subject)
    alpha = arr[..., 3]
    # all mask-covered pixels become opaque
    for (x, y) in ((90, 60), (199, 149), (150, 100)):
        assert alpha[y, x] == 255
    # a background pixel stays transparent
    assert alpha[10, 10] == 0


# --------------------------------------------------------------------------- #
# AC: no crash when subject not found -> composite fallback
# --------------------------------------------------------------------------- #
def test_empty_mask_falls_back_to_composite() -> None:
    img = composite()
    r = segment_subject(img, backend=FakeBackend(empty_mask()), feather_radius=0)
    assert not r.subject_found
    assert r.subject.size == img.size  # full composite is the subject
    # fallback keeps the full frame opaque (subject == composite)
    arr = np.asarray(r.subject)
    assert (arr[..., 3] > 0).all()


def test_backend_exception_falls_back() -> None:
    class ExplodingBackend:
        def produce_mask(self, image: Image.Image) -> Image.Image:
            raise RuntimeError("model crashed")

    r = segment_subject(composite(), backend=ExplodingBackend(), feather_radius=0)
    assert not r.subject_found
    assert r.subject.size == (320, 240)


def test_default_backend_import_error_falls_back(monkeypatch) -> None:
    def unavailable(self, image):
        del self, image
        raise ImportError("No onnxruntime backend found")

    monkeypatch.setattr(RembgBackend, "produce_mask", unavailable)
    result = segment_subject(composite(), feather_radius=0)
    assert not result.subject_found
    assert result.backend == "fallback"


def test_backend_system_exit_falls_back() -> None:
    class MissingRuntimeBackend:
        def produce_mask(self, image):
            del image
            raise SystemExit("No onnxruntime backend found")

    result = segment_subject(composite(), backend=MissingRuntimeBackend(), feather_radius=0)
    assert not result.subject_found
    assert result.backend == "fallback"


def test_tiny_mask_falls_back() -> None:
    """Coverage below the minimum threshold -> composite fallback."""
    tiny = Image.new("L", (320, 240), 0)
    tiny.putpixel((160, 120), 255)  # single pixel << min_coverage
    r = segment_subject(composite(), backend=FakeBackend(tiny), feather_radius=0)
    assert not r.subject_found


# --------------------------------------------------------------------------- #
# Mask cleanup
# --------------------------------------------------------------------------- #
def test_refine_mask_keeps_largest_component_only() -> None:
    m = speckled_mask()
    cleaned = _refine_mask(m, threshold=128)
    assert cleaned is not None
    arr = np.asarray(cleaned, dtype=np.uint8)
    # specks are gone, subject rectangle remains
    assert (arr > 0).sum() == 120 * 100
    assert arr[2, 2] == 0
    assert arr[230, 300] == 0  # bottom-right speck removed
    assert arr[100, 100] == 255  # subject retained


def test_refine_mask_empty_returns_none() -> None:
    assert _refine_mask(empty_mask(), threshold=128) is None


def test_coverage_reports_fraction() -> None:
    m = rect_mask(size=(320, 240), box=(0, 0, 160, 120))
    assert _coverage(m) == pytest.approx(0.25)


# --------------------------------------------------------------------------- #
# Edge feather
# --------------------------------------------------------------------------- #
def test_feather_softens_alpha_edges() -> None:
    img = composite()
    r_hard = segment_subject(img, backend=FakeBackend(rect_mask()), feather_radius=0)
    r_soft = segment_subject(img, backend=FakeBackend(rect_mask()), feather_radius=3)

    hard = np.asarray(r_hard.subject)[..., 3]
    soft = np.asarray(r_soft.subject)[..., 3]
    # a pixel one step outside the hard mask boundary now has partial alpha
    assert hard[49, 90] == 0  # row just above the rectangle top (y=50)
    assert 0 < soft[49, 90] < 255
    # inside the subject still fully opaque
    assert soft[100, 100] == 255


def test_feather_zero_is_noop() -> None:
    img = composite()
    r = segment_subject(img, backend=FakeBackend(rect_mask()), feather_radius=0)
    assert np.asarray(r.subject)[..., 3].max() == 255


def test_feather_returns_same_mode() -> None:
    img = composite()
    r = segment_subject(img, backend=FakeBackend(rect_mask()), feather_radius=2)
    assert r.subject.mode == "RGBA"


# --------------------------------------------------------------------------- #
# Background fallback
# --------------------------------------------------------------------------- #
def test_derive_background_with_mask_inpaints_subject() -> None:
    img = composite_with_subject()
    bg = derive_background(img, subject_mask=rect_mask())
    assert isinstance(bg, BackgroundResult)
    assert bg.source == "derived"
    assert bg.inpainted
    # opaque output
    assert bg.background.getchannel("A").getextrema()[0] == 255
    # subject region no longer carries the original subject color (blurred away)
    assert bg.background.getpixel((100, 100)) != img.getpixel((100, 100))
    # the background color is preserved where there is no subject
    assert bg.background.getpixel((10, 10)) == img.getpixel((10, 10))


def test_derive_background_without_mask_uses_composite() -> None:
    img = composite()
    bg = derive_background(img)
    assert bg.source == "composite_fallback"
    assert bg.background.getchannel("A").getextrema()[0] == 255
    assert bg.background.size == img.size


def _solid_rgba(size, rgba) -> Image.Image:
    img = Image.new("RGBA", size)
    img.paste(rgba, (0, 0, size[0], size[1]))
    return img


def test_ensure_background_prefers_provided_opaque() -> None:
    provided = _solid_rgba((320, 240), (10, 10, 10, 255))
    bg = ensure_background(composite(), provided=provided)
    assert bg.source == "provided"
    assert not bg.inpainted


def test_ensure_background_forces_opaque_when_provided_transparent() -> None:
    provided = _solid_rgba((320, 240), (10, 10, 10, 0))  # fully transparent
    bg = ensure_background(composite(), provided=provided)
    assert bg.source == "provided"
    assert bg.background.getchannel("A").getextrema()[0] == 255
    assert bg.inpainted


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def test_refine_mask_returns_l_mode() -> None:
    cleaned = _refine_mask(rect_mask(), threshold=128)
    assert cleaned is not None
    assert cleaned.mode == "L"
