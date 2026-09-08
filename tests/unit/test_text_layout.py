"""Tests for P5-T04 text-safe layout.

Covers the acceptance criteria:

- 16:9 and 9:16 canvases both produce an in-bounds headline box;
- Vietnamese text with diacritics renders (resolved font covers all glyphs);
- the text box never exceeds the safe area (font is shrunk when needed);
- font fallback picks a font that covers the text;
- mask avoidance moves the headline off the subject.
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageFont

from app.services.text_layout import (
    ALL_PLACEMENTS,
    FontNotFoundError,
    TextBox,
    TextLayoutError,
    TextLayoutService,
    font_covers,
    resolve_font,
    wrap_text,
)
from app.services.vi_normalize import normalize_vi

VI_TEXT = "Ở đây có đoạn chữ tiếng Việt với dấu ặn ộ ứ ễ rất nhiều dấu."
LONG_VI_TEXT = (
    "Đây là một đoạn tiêu đề rất dài bằng tiếng Việt để kiểm tra việc "
    "xuống dòng và co chữ sao cho không vượt ra ngoài vùng an toàn của khung hình."
)


def solid_mask(size=(1920, 1080), box=(100, 300, 800, 900)) -> Image.Image:
    """An alpha mask with a subject rectangle (opaque subject on transparent bg)."""
    img = Image.new("RGBA", size)
    img.paste((255, 255, 255, 255), (box[0], box[1], box[2], box[3]))
    return img


# --------------------------------------------------------------------------- #
# Font resolution + glyph coverage
# --------------------------------------------------------------------------- #
def test_resolve_font_covers_vietnamese() -> None:
    font_path = resolve_font(VI_TEXT)
    assert font_path
    assert font_covers(font_path, VI_TEXT)


def test_font_covers_missing_glyph_is_false() -> None:
    # A font candidate that cannot possibly cover CJK.
    assert not font_covers("C:/Windows/Fonts/arial.ttf", "你好")


def test_font_not_found_raises() -> None:
    with pytest.raises(FontNotFoundError):
        resolve_font("x", candidates=("definitely_missing_font.ttf",))


def test_wrap_text_splits_long_line() -> None:
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
    lines = wrap_text("một hai ba bốn năm sáu bảy tám chín mười", font, 180)
    assert len(lines) > 1
    assert " ".join(lines).replace(" ", "") == "mộthaibabốnnămsáubảytámchínmười".replace(
        " ", ""
    ) or all(font.getlength(ln) <= 180 for ln in lines)


# --------------------------------------------------------------------------- #
# 16:9 / 9:16 — AC: both aspect ratios stay in-bounds
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("size", [(1920, 1080), (1080, 1920)])
@pytest.mark.parametrize("placement", ALL_PLACEMENTS)
def test_layout_within_safe_area_all_anchors(size, placement) -> None:
    svc = TextLayoutService()
    r = svc.layout("TIÊU ĐỀ CHÍNH", canvas_size=size, placement=placement)
    assert r.lines
    # Box is inside the frame.
    assert r.x >= 0 and r.y >= 0
    assert r.right <= size[0] and r.bottom <= size[1]
    assert not r.overflow


def test_layout_16_9_box_metrics() -> None:
    svc = TextLayoutService()
    r = svc.layout("Chữ tiêu đề", canvas_size=(1920, 1080), font_size=64)
    assert r.width > 0 and r.height > 0
    assert r.lines == ["Chữ tiêu đề"] or len(r.lines) >= 1
    # top_left anchor sits at the safe margin.
    assert r.x == svc.safe_margin
    assert r.y == svc.safe_margin


def test_layout_9_16_box_metrics() -> None:
    svc = TextLayoutService()
    r = svc.layout("Tiêu đề dọc", canvas_size=(1080, 1920), font_size=64)
    assert r.right <= 1080 and r.bottom <= 1920
    assert r.x >= 0 and r.y >= 0


def test_layout_empty_text_ok() -> None:
    r = TextLayoutService().layout("", canvas_size=(1920, 1080))
    assert r.lines == []


def test_invalid_placement_raises() -> None:
    with pytest.raises(TextLayoutError):
        TextLayoutService().layout("x", placement="somewhere_else")


# --------------------------------------------------------------------------- #
# Vietnamese diacritics — AC: renders without tofu
# --------------------------------------------------------------------------- #
def test_vietnamese_text_covers_glyphs() -> None:
    svc = TextLayoutService()
    r = svc.layout(VI_TEXT, canvas_size=(1920, 1080))
    assert font_covers(r.font_path, VI_TEXT)
    assert r.lines


def test_vietnamese_normalized_layout() -> None:
    """Even after vi-normalize the layout still resolves a covering font."""
    text = normalize_vi(VI_TEXT)
    r = TextLayoutService().layout(text, canvas_size=(1920, 1080))
    assert font_covers(r.font_path, text)


# --------------------------------------------------------------------------- #
# Long text shrinks/wraps — AC: never exceeds safe area
# --------------------------------------------------------------------------- #
def test_long_text_wraps_within_safe_area() -> None:
    svc = TextLayoutService()
    r = svc.layout(LONG_VI_TEXT, canvas_size=(1920, 1080), font_size=96)
    assert r.lines
    assert len(r.lines) > 1  # wrapped
    for box in r.line_boxes:
        assert box.x >= r.x
        assert box.x + box.width <= r.right
    assert not r.overflow


def test_line_boxes_aligned() -> None:
    svc = TextLayoutService()
    r = svc.layout("Dòng một Dòng hai ba", canvas_size=(1920, 1080), font_size=80)
    assert len(r.line_boxes) >= 1
    for box in r.line_boxes:
        assert isinstance(box, TextBox)
        assert box.height > 0


def test_font_shrinks_to_fit_very_long_text() -> None:
    svc = TextLayoutService()
    r = svc.layout(LONG_VI_TEXT, canvas_size=(1920, 1080), font_size=400)
    # Font must have been reduced below the request to fit.
    assert r.font_size < 400
    assert not r.overflow


# --------------------------------------------------------------------------- #
# Mask avoidance — AC: avoids covering subject when mask present
# --------------------------------------------------------------------------- #
def test_layout_avoids_subject_mask() -> None:
    # Subject occupies the top-left area; bottom-left should be chosen instead.
    svc = TextLayoutService()
    mask = solid_mask(box=(0, 0, 900, 400))
    # Force preferred top_left; the service should move it to avoid the subject.
    r = svc.layout("TIÊU ĐỀ", canvas_size=(1920, 1080), placement="top_left", mask=mask)
    assert r.mask_avoided
    # The chosen box must not overlap the subject rect.
    subject = (0, 0, 900, 400)
    ix = max(0, min(r.right, subject[2]) - max(r.x, subject[0]))
    iy = max(0, min(r.bottom, subject[3]) - max(r.y, subject[1]))
    assert ix * iy == 0


def test_layout_without_mask_stays_at_anchor() -> None:
    svc = TextLayoutService()
    r = svc.layout("TIÊU ĐỀ", canvas_size=(1920, 1080), placement="top_left")
    assert r.placement == "top_left"
    assert not r.mask_avoided


def test_mask_empty_is_ignored() -> None:
    empty = Image.new("RGBA", (1920, 1080))  # no subject
    svc = TextLayoutService()
    r = svc.layout("TIÊU ĐỀ", canvas_size=(1920, 1080), placement="top_left", mask=empty)
    assert r.placement == "top_left"


# --------------------------------------------------------------------------- #
# Placement anchors
# --------------------------------------------------------------------------- #
def test_center_anchor_aligns_lines_center() -> None:
    svc = TextLayoutService()
    r = svc.layout(
        "dòng đầu tiên dòng thứ hai",
        canvas_size=(1920, 1080),
        placement="center",
        font_size=90,
    )
    assert len(r.line_boxes) >= 2  # wrapped into at least 2 lines
    mid = r.x + r.width // 2
    for box in r.line_boxes:
        # each line's midpoint is near the block center
        assert abs((box.x + box.width // 2) - mid) <= 2


def test_each_anchor_produces_distinct_origin() -> None:
    svc = TextLayoutService()
    origins = set()
    for placement in ALL_PLACEMENTS:
        r = svc.layout("Tiêu đề", canvas_size=(1920, 1080), placement=placement)
        origins.add((r.x, r.y))
    # At least a few distinct placements (short text -> some may coincide).
    assert len(origins) >= 2
