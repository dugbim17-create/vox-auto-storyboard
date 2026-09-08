"""Procedural document highlighter and marker sweep generator for Vox editorial style."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# Standard highlighter palette in Vox / documentary graphics
HIGHLIGHTER_COLORS: dict[str, tuple[int, int, int]] = {
    "yellow": (255, 235, 20),    # Classic fluorescent yellow
    "cyan": (40, 230, 255),      # Neon electric blue
    "green": (57, 255, 20),      # Acid green
    "pink": (255, 60, 120),      # Magenta marker
    "orange": (255, 140, 0),     # Amber alert
}


@dataclass(frozen=True)
class HighlightOptions:
    """Styling options for fluorescent highlighter stroke."""

    color_name: str = "yellow"
    opacity: float = 0.55
    blur_radius: int = 1
    slant_px: int = 3
    padding: tuple[int, int] = (4, 2)  # horizontal, vertical padding around target box


class DocumentHighlighterService:
    """Apply realistic highlighter strokes across documents, newspaper scans, and text blocks."""

    @staticmethod
    def apply_highlight_sweep(
        base_image: Image.Image,
        box: tuple[int, int, int, int],
        progress: float = 1.0,
        options: HighlightOptions | None = None,
    ) -> Image.Image:
        """Apply a marker sweep from left to right covering [x0, y0, x1, y1] with given progress (0..1)."""
        opts = options or HighlightOptions()
        if base_image.mode != "RGBA":
            base_image = base_image.convert("RGBA")

        x0, y0, x1, y1 = box
        px, py = opts.padding
        x0 -= px
        y0 -= py
        x1 += px
        y1 += py

        total_width = max(1, x1 - x0)
        current_width = int(total_width * max(0.0, min(1.0, progress)))
        if current_width <= 0:
            return base_image

        color = HIGHLIGHTER_COLORS.get(opts.color_name.lower(), HIGHLIGHTER_COLORS["yellow"])
        highlight_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(highlight_layer)

        cur_x1 = x0 + current_width
        slant = opts.slant_px

        # Polygon with realistic organic angled tip
        points = [
            (x0, y0 + 1),
            (cur_x1, y0),
            (cur_x1 + slant, y1),
            (x0 - 1, y1),
        ]
        alpha = int(255 * opts.opacity)
        draw.polygon(points, fill=(*color, alpha))

        if opts.blur_radius > 0:
            highlight_layer = highlight_layer.filter(ImageFilter.BoxBlur(opts.blur_radius))

        return Image.alpha_composite(base_image, highlight_layer)

    @classmethod
    def highlight_multiple_lines(
        cls,
        base_image: Image.Image,
        boxes: list[tuple[int, int, int, int]],
        progress: float = 1.0,
        options: HighlightOptions | None = None,
    ) -> Image.Image:
        """Progressively highlight a series of text lines in sequence."""
        if not boxes:
            return base_image
        total_lines = len(boxes)
        result = base_image
        for i, box in enumerate(boxes):
            line_start = i / total_lines
            line_end = (i + 1) / total_lines
            if progress <= line_start:
                line_prog = 0.0
            elif progress >= line_end:
                line_prog = 1.0
            else:
                line_prog = (progress - line_start) / (line_end - line_start)
            result = cls.apply_highlight_sweep(result, box, progress=line_prog, options=options)
        return result
