"""Unit tests for DocumentHighlighterService."""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.services.document_highlighter import DocumentHighlighterService, HighlightOptions


def test_apply_highlight_sweep_progress_0_returns_unchanged() -> None:
    doc = Image.new("RGBA", (200, 100), (255, 255, 255, 255))
    out = DocumentHighlighterService.apply_highlight_sweep(doc, (20, 30, 180, 50), progress=0.0)
    assert np.array_equal(np.array(doc), np.array(out))


def test_apply_highlight_sweep_progress_1_applies_color() -> None:
    doc = Image.new("RGBA", (200, 100), (255, 255, 255, 255))
    opts = HighlightOptions(color_name="yellow", opacity=0.8)
    out = DocumentHighlighterService.apply_highlight_sweep(doc, (20, 30, 180, 50), progress=1.0, options=opts)

    assert out.size == (200, 100)
    arr = np.array(out)
    # Check pixels inside highlight region have yellow tint (high red/green, lower blue)
    sample = arr[40, 100]
    assert sample[0] > 200  # R
    assert sample[1] > 200  # G
    assert sample[2] < 200  # B (yellow has low blue compared to pure white 255)


def test_highlight_multiple_lines_sequences_properly() -> None:
    doc = Image.new("RGBA", (300, 300), (255, 255, 255, 255))
    lines = [
        (30, 50, 270, 80),
        (30, 100, 270, 130),
        (30, 150, 270, 180),
    ]
    # At progress=0.5, first line is fully done, second line is halfway, third line is untouched
    out = DocumentHighlighterService.highlight_multiple_lines(doc, lines, progress=0.5)
    arr = np.array(out)

    # Line 1 middle should be highlighted
    assert arr[65, 150][2] < 240
    # Line 3 middle should still be pure white
    assert arr[165, 150][2] == 255
