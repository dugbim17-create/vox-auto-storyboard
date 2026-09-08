"""Unit tests for PaperCraftService (torn paper cutout, 3D pushpin, corner tape & film grain)."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from app.services.paper_craft import PaperCraftService, PaperCutoutOptions


def test_create_torn_cutout_adds_border_and_shadow() -> None:
    # Create simple circular subject on transparent background
    img = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((20, 20, 100, 100), fill=(200, 40, 40, 255))

    opts = PaperCutoutOptions(border_width=8, shadow=True)
    cutout = PaperCraftService.create_torn_cutout(img, opts)

    assert cutout.width > img.width
    assert cutout.height > img.height
    assert cutout.mode == "RGBA"

    arr = np.array(cutout)
    alpha = arr[:, :, 3]
    assert np.any(alpha > 0)


def test_create_torn_cutout_converts_rgb_to_rgba() -> None:
    img = Image.new("RGB", (80, 80), (100, 150, 200))
    cutout = PaperCraftService.create_torn_cutout(img)
    assert cutout.mode == "RGBA"
    assert cutout.width >= 80


def test_draw_3d_pushpin_generates_valid_rgba_dome() -> None:
    pin = PaperCraftService.draw_3d_pushpin(radius=16, color=(220, 30, 30))
    assert pin.mode == "RGBA"
    assert pin.width >= 32
    assert pin.height >= 32
    arr = np.array(pin)
    # Check red channel is prominent
    assert np.max(arr[:, :, 0]) > 200
    # Check alpha channel exists
    assert np.any(arr[:, :, 3] > 0)


def test_apply_corner_tape_mounts_attaches_to_all_corners() -> None:
    img = Image.new("RGBA", (200, 200), (240, 235, 220, 255))
    mounted = PaperCraftService.apply_corner_tape_mounts(img, tape_size=(50, 20))
    assert mounted.size == (200, 200)
    assert mounted.mode == "RGBA"


def test_generate_film_grain_texture() -> None:
    grain = PaperCraftService.generate_film_grain_texture(320, 180, intensity=0.08)
    assert grain.size == (320, 180)
    assert grain.mode == "RGBA"
    arr = np.array(grain)
    assert np.mean(arr[:, :, 3]) > 0
