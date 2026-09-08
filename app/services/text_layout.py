"""Text-safe layout service (P5-T04).

Computes a headline placement on the canvas that:

- computes the region where the headline may go (a safe area inset from the
  frame edges);
- avoids covering the subject when a segmentation mask is available (the box
  is moved to the emptiest corner);
- resolves a font that actually contains the glyphs for the text (font
  fallback across system fonts), so Vietnamese diacritics never render as
  boxes;
- wraps long lines so nothing exceeds the safe area.

Acceptance criteria (MASTER_PLAN P5-T04):

- 16:9 and 9:16 canvases both produce an in-bounds headline box;
- Vietnamese text with diacritics renders (the resolved font covers every
  non-space character);
- the text box never exceeds the safe area (shrinks the font when needed).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageFont
from PIL.ImageFont import FreeTypeFont

# Windows system font directory (the tool is a local Windows app).
DEFAULT_FONT_DIRS: tuple[str, ...] = (r"C:\Windows\Fonts",)

# Fallback candidates, best-first. All cover Vietnamese (verified against the
# Windows font cmaps); Arial/Tahoma/Segoe UI are the primary trio.
DEFAULT_FONT_CANDIDATES: tuple[str, ...] = (
    "arial.ttf",
    "arialbd.ttf",
    "tahoma.ttf",
    "tahomabd.ttf",
    "segoeui.ttf",
    "segoeuib.ttf",
    "calibri.ttf",
    "verdana.ttf",
    "times.ttf",
    "cour.ttf",
)

# All placement anchors the service can choose from.
ALL_PLACEMENTS: tuple[str, ...] = (
    "top_left",
    "top_center",
    "top_right",
    "center",
    "bottom_left",
    "bottom_center",
    "bottom_right",
)

# Default inset of the safe area from the frame edges (pixels on a 1080p frame).
DEFAULT_SAFE_MARGIN = 96
# Headline box may occupy at most this fraction of the safe area width.
DEFAULT_MAX_TEXT_WIDTH = 0.62
# Vertical spacing between wrapped lines as a multiple of the font size.
LINE_SPACING = 1.25
# Never shrink the font below this when fitting the safe area.
MIN_FONT_SIZE = 16


class FontNotFoundError(Exception):
    """Raised when no configured font can be located on disk."""


class TextLayoutError(Exception):
    """Raised for invalid layout input."""


@dataclass(frozen=True)
class TextBox:
    """One rendered line of the headline."""

    text: str
    x: int
    y: int
    width: int
    height: int


@dataclass
class TextLayoutResult:
    """Computed headline layout: where to place the text + how to render it."""

    text: str
    font_path: str
    font_size: int
    lines: list[str] = field(default_factory=list)
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    placement: str = "top_left"
    line_boxes: list[TextBox] = field(default_factory=list)
    mask_avoided: bool = False
    overflow: bool = False

    @property
    def box(self) -> tuple[int, int, int, int]:
        """(left, top, right, bottom) of the headline block."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


# --------------------------------------------------------------------------- #
# Font resolution + glyph coverage
# --------------------------------------------------------------------------- #
_cmap_cache: dict[str, frozenset[int]] = {}


def font_covers(font_path: str, chars: Iterable[str]) -> bool:
    """True when the font's cmap contains every non-space character."""
    cmap = _cmap(font_path)
    return all(ord(c) in cmap for c in chars if not c.isspace())


def _cmap(font_path: str) -> frozenset[int]:
    cached = _cmap_cache.get(font_path)
    if cached is not None:
        return cached
    try:
        cmap = TTFont(font_path).getBestCmap()
        codepoints = frozenset(cmap.keys()) if cmap else frozenset()
    except Exception:  # noqa: BLE001
        codepoints = frozenset()
    _cmap_cache[font_path] = codepoints
    return codepoints


def _find_font(name: str, dirs: Iterable[str]) -> str | None:
    """Locate a font by filename (or absolute path) under the given dirs."""
    cand = Path(name)
    if cand.is_absolute() and cand.is_file():
        return str(cand)
    for d in dirs:
        for candidate in (cand, Path(name.lower()), Path(name.upper())):
            p = Path(d) / candidate.name
            if p.is_file():
                return str(p)
    return None


def resolve_font(
    text: str,
    *,
    candidates: Iterable[str] | None = None,
    dirs: Iterable[str] | None = None,
) -> str:
    """Return the first candidate font whose cmap covers all text characters.

    Falls back to the first font that exists on disk even if coverage is
    incomplete (best effort), and raises ``FontNotFoundError`` when nothing
    could be located.
    """
    names = tuple(candidates or DEFAULT_FONT_CANDIDATES)
    font_dirs = tuple(dirs or DEFAULT_FONT_DIRS)
    chars = {c for c in text if not c.isspace()}
    for name in names:
        path = _find_font(name, font_dirs)
        if path and font_covers(path, chars):
            return path
    for name in names:
        path = _find_font(name, font_dirs)
        if path:
            return path
    raise FontNotFoundError(f"no font found in {font_dirs} for candidates {names}")


# --------------------------------------------------------------------------- #
# Line wrapping
# --------------------------------------------------------------------------- #
def wrap_text(text: str, font: FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word-wrap ``text`` to fit ``max_width`` (hard-breaks long words)."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = ""
    for word in words:
        candidate = f"{cur} {word}".strip()
        if cur and font.getlength(candidate) <= max_width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            if font.getlength(word) > max_width:
                pieces = _hard_break(word, font, max_width)
                lines.extend(pieces[:-1])
                cur = pieces[-1]
            else:
                cur = word
    if cur:
        lines.append(cur)
    return lines


def _hard_break(word: str, font: FreeTypeFont, max_width: int) -> list[str]:
    pieces: list[str] = []
    cur = ""
    for ch in word:
        if cur and font.getlength(cur + ch) > max_width:
            pieces.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        pieces.append(cur)
    return pieces


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
class TextLayoutService:
    """Compute a safe, mask-aware, font-resolved headline layout."""

    def __init__(
        self,
        *,
        font_candidates: Iterable[str] | None = None,
        font_dirs: Iterable[str] | None = None,
        safe_margin: int | None = None,
        max_text_width: float | None = None,
        mask_threshold: int = 16,
        mask_padding: int = 24,
    ) -> None:
        self.font_candidates = tuple(font_candidates or DEFAULT_FONT_CANDIDATES)
        self.font_dirs = tuple(font_dirs or DEFAULT_FONT_DIRS)
        self.safe_margin = int(safe_margin or DEFAULT_SAFE_MARGIN)
        self.max_text_width = float(max_text_width or DEFAULT_MAX_TEXT_WIDTH)
        self.mask_threshold = mask_threshold
        self.mask_padding = mask_padding

    # ------------------------------------------------------------------ #
    # Entrypoint
    # ------------------------------------------------------------------ #
    def layout(
        self,
        text: str,
        *,
        canvas_size: tuple[int, int] = (1920, 1080),
        placement: str = "top_left",
        font_size: int = 64,
        mask: str | Path | Image.Image | None = None,
    ) -> TextLayoutResult:
        """Compute the headline layout for ``text`` on the canvas.

        ``placement`` is the preferred anchor; when ``mask`` is provided, the
        box is moved to whichever anchor overlaps the subject the least.
        """
        if placement not in ALL_PLACEMENTS:
            raise TextLayoutError(
                f"unknown placement {placement!r}; expected one of {ALL_PLACEMENTS}"
            )
        font_path = resolve_font(text, candidates=self.font_candidates, dirs=self.font_dirs)

        if not text.strip():
            return TextLayoutResult(
                text=text, font_path=font_path, font_size=font_size,
                placement=placement, x=self.safe_margin, y=self.safe_margin,
            )

        mask_bbox = self._subject_bbox(mask, canvas_size)
        anchors = self._anchor_order(placement, mask_bbox)

        best: TextLayoutResult | None = None
        best_overlap: int | None = None
        for anchor in anchors:
            candidate = self._candidate(text, anchor, font_path, canvas_size, font_size)
            overlap = _rect_overlap(candidate.box, mask_bbox) if mask_bbox else 0
            if best_overlap is None or overlap < best_overlap:
                best, best_overlap = candidate, overlap

        assert best is not None
        best.mask_avoided = mask_bbox is not None and best_overlap == 0
        return best

    # ------------------------------------------------------------------ #
    # Mask handling
    # ------------------------------------------------------------------ #
    def _subject_bbox(
        self, mask: str | Path | Image.Image | None, canvas_size: tuple[int, int]
    ) -> tuple[int, int, int, int] | None:
        """Bounding box (padded) of the opaque subject in a mask image."""
        if mask is None:
            return None
        img = mask if isinstance(mask, Image.Image) else Image.open(mask)
        alpha = img.getchannel("A") if "A" in img.mode else img.convert("L")
        arr = np.asarray(alpha)
        ys, xs = np.where(arr > self.mask_threshold)
        if not len(xs):
            return None
        cw, ch = canvas_size
        pad = self.mask_padding
        x0 = max(0, int(xs.min()) - pad)
        y0 = max(0, int(ys.min()) - pad)
        x1 = min(cw, int(xs.max()) + 1 + pad)
        y1 = min(ch, int(ys.max()) + 1 + pad)
        return (x0, y0, x1, y1)

    @staticmethod
    def _anchor_order(
        placement: str, mask_bbox: tuple[int, int, int, int] | None
    ) -> list[str]:
        """Anchors to try, best first.

        The preferred placement is tried first; when a mask is present the
        remaining anchors follow so the emptiest corner can win the tie-break.
        """
        if mask_bbox is None:
            return [placement]
        return [placement] + [a for a in ALL_PLACEMENTS if a != placement]

    # ------------------------------------------------------------------ #
    # Candidate computation
    # ------------------------------------------------------------------ #
    def _candidate(
        self,
        text: str,
        anchor: str,
        font_path: str,
        canvas_size: tuple[int, int],
        max_font_size: int,
    ) -> TextLayoutResult:
        canvas_w, canvas_h = canvas_size
        margin = self.safe_margin
        safe_w = canvas_w - 2 * margin
        safe_h = canvas_h - 2 * margin
        max_w = int(safe_w * self.max_text_width)

        # Shrink the font until the wrapped block fits the safe height.
        size = max_font_size
        for _ in range(20):
            font = ImageFont.truetype(font_path, size)
            lines = wrap_text(text, font, max_w)
            line_h = int(size * LINE_SPACING)
            block_h = len(lines) * line_h
            if block_h <= safe_h or size <= MIN_FONT_SIZE:
                break
            size = max(MIN_FONT_SIZE, int(size * safe_h / block_h))

        font = ImageFont.truetype(font_path, size)
        lines = wrap_text(text, font, max_w)
        line_h = int(size * LINE_SPACING)
        block_w = max((int(font.getlength(line)) for line in lines), default=0)
        block_h = len(lines) * line_h

        x, y = self._anchor_origin(anchor, block_w, block_h, safe_w, safe_h, margin)
        line_boxes = self._line_boxes(lines, font, anchor, x, y, line_h, block_w)

        overflow = (
            block_w > safe_w
            or x + block_w > margin + safe_w
            or y + block_h > margin + safe_h
        )
        return TextLayoutResult(
            text=text,
            font_path=font_path,
            font_size=size,
            lines=lines,
            x=x,
            y=y,
            width=block_w,
            height=block_h,
            placement=anchor,
            line_boxes=line_boxes,
            overflow=overflow,
        )

    @staticmethod
    def _anchor_origin(
        anchor: str,
        block_w: int,
        block_h: int,
        safe_w: int,
        safe_h: int,
        margin: int,
    ) -> tuple[int, int]:
        if anchor == "top_left":
            return margin, margin
        if anchor == "top_center":
            return margin + (safe_w - block_w) // 2, margin
        if anchor == "top_right":
            return margin + safe_w - block_w, margin
        if anchor == "center":
            return margin + (safe_w - block_w) // 2, margin + (safe_h - block_h) // 2
        if anchor == "bottom_left":
            return margin, margin + safe_h - block_h
        if anchor == "bottom_center":
            return margin + (safe_w - block_w) // 2, margin + safe_h - block_h
        if anchor == "bottom_right":
            return margin + safe_w - block_w, margin + safe_h - block_h
        return margin, margin  # unreachable for validated anchors

    @staticmethod
    def _line_boxes(
        lines: list[str],
        font: FreeTypeFont,
        anchor: str,
        x: int,
        y: int,
        line_h: int,
        block_w: int,
    ) -> list[TextBox]:
        # center anchor centers both horizontally and vertically, so its lines
        # align center; *_center anchors center; *_right anchors align right.
        align = anchor if anchor == "center" else anchor.split("_", 1)[1]
        boxes: list[TextBox] = []
        for i, line in enumerate(lines):
            lw = int(font.getlength(line))
            if align == "center":
                lx = x + (block_w - lw) // 2
            elif align == "right":
                lx = x + block_w - lw
            else:
                lx = x
            boxes.append(TextBox(text=line, x=lx, y=y + i * line_h, width=lw, height=line_h))
        return boxes


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _rect_overlap(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int] | None
) -> int:
    """Intersection area of two (left, top, right, bottom) rectangles."""
    if b is None:
        return 0
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy
