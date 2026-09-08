"""Tests for P5-T01 layer package validator.

Covers the validation dimensions:

- validate image: file exists + decodable (missing/broken -> problem);
- role: unknown role rejected;
- aspect: pixel aspect matches target (with tolerance);
- alpha: subject/foreground/texture/composite -> alpha expected; background -> opaque;
- dimensions: within canvas bounds + sane max side.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.services.layer_validator import (
    ALPHA_ROLES,
    LayerPackageValidationError,
    LayerPackageValidator,
    parse_aspect,
)


@pytest.fixture()
def image_dir(tmp_path: Path) -> Path:
    return tmp_path / "images"


def make_image(path: Path, *, size=(1920, 1080), mode="RGB", alpha=None, color=(200, 30, 30)) -> Path:
    """Write an image file; RGBA when mode == 'RGBA' or alpha is not ok."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "RGBA" or alpha:
        img = Image.new("RGBA", size, color + (200,))
    else:
        img = Image.new("RGB", size, color)
    img.save(path, format="PNG")
    return path


def valid_package(image_dir: Path) -> dict:
    """5 role images with correct alpha expectations (16:9)."""
    bg = make_image(image_dir / "background.png", mode="RGB")  # opaque
    subj = make_image(image_dir / "subject.png", mode="RGBA")  # alpha
    fg = make_image(image_dir / "foreground.png", mode="RGBA")
    tex = make_image(image_dir / "texture.png", mode="RGBA")
    comp = make_image(image_dir / "composite.png", mode="RGBA")
    return {
        "background": str(bg),
        "subject": str(subj),
        "foreground": str(fg),
        "texture": str(tex),
        "composite": str(comp),
    }


# --------------------------------------------------------------------------- #
# Valid package + image validation
# --------------------------------------------------------------------------- #
def test_valid_package_passes(image_dir) -> None:
    package = valid_package(image_dir)
    result = LayerPackageValidator(aspect_ratio="16:9").validate(package)
    assert result.ok
    assert result.messages == []


def test_validate_or_raise_ok(image_dir) -> None:
    package = valid_package(image_dir)
    LayerPackageValidator(aspect_ratio="16:9").validate_or_raise(package)


def test_missing_image_reports_problem(image_dir) -> None:
    package = valid_package(image_dir)
    package["subject"] = str(image_dir / "nope.png")  # missing file
    result = LayerPackageValidator().validate(package)
    assert not result.ok
    assert any("subject" in m for m in result.messages)


def test_empty_package_reports_problem() -> None:
    result = LayerPackageValidator().validate({})
    assert not result.ok
    assert any("empty" in m for m in result.messages)


# --------------------------------------------------------------------------- #
# Role validation
# --------------------------------------------------------------------------- #
def test_unknown_role_rejected(image_dir) -> None:
    package = valid_package(image_dir)
    package["backdrop"] = package["background"]  # not a known role
    result = LayerPackageValidator().validate(package)
    assert any("backdrop" in m and "unknown role" in m for m in result.messages)


# --------------------------------------------------------------------------- #
# Alpha validation
# --------------------------------------------------------------------------- #
def test_alpha_roles_expected_rgba(image_dir) -> None:
    assert set(ALPHA_ROLES) == {"subject", "foreground", "texture", "composite"}
    # Subject given an opaque RGB image -> problem.
    package = valid_package(image_dir)
    package["subject"] = str(make_image(image_dir / "subj_rgb.png", mode="RGB"))
    result = LayerPackageValidator().validate(package)
    assert any("subject" in m and "alpha" in m for m in result.messages)


def test_background_opaque_expected(image_dir) -> None:
    package = valid_package(image_dir)
    package["background"] = str(make_image(image_dir / "bg_rgba.png", mode="RGBA"))
    result = LayerPackageValidator().validate(package)
    assert any("background" in m and "opaque" in m for m in result.messages)


# --------------------------------------------------------------------------- #
# Aspect + dimensions
# --------------------------------------------------------------------------- #
def test_aspect_mismatch_reported(image_dir) -> None:
    package = valid_package(image_dir)
    # Replace one image with a square (1:1) — far from 16:9.
    package["background"] = str(make_image(image_dir / "square.png", size=(1000, 1000), mode="RGB"))
    result = LayerPackageValidator(aspect_ratio="16:9").validate(package)
    assert any("aspect" in m for m in result.messages)


def test_aspect_within_tolerance_passes(image_dir) -> None:
    package = valid_package(image_dir)
    # Slightly off-16:9 but within 10% tolerance.
    package["background"] = str(make_image(image_dir / "near.png", size=(2000, 1140), mode="RGB"))  # 1.754
    result = LayerPackageValidator(aspect_ratio="16:9").validate(package)
    assert result.ok


def test_canvas_oversize_reported(image_dir) -> None:
    package = valid_package(image_dir)
    package["background"] = str(make_image(image_dir / "big.png", size=(3000, 2000), mode="RGB"))
    result = LayerPackageValidator(canvas_width=1920, canvas_height=1080).validate(package)
    assert any("canvas" in m for m in result.messages)


def test_no_canvas_so_no_size_limit(image_dir) -> None:
    package = valid_package(image_dir)
    result = LayerPackageValidator().validate(package)
    assert result.ok


# --------------------------------------------------------------------------- #
# validate_or_raise
# --------------------------------------------------------------------------- #
def test_validate_or_raise_raises_on_problem(image_dir) -> None:
    package = valid_package(image_dir)
    package["subject"] = "definitely/missing.png"
    with pytest.raises(LayerPackageValidationError):
        LayerPackageValidator().validate_or_raise(package)


# --------------------------------------------------------------------------- #
# parse_aspect
# --------------------------------------------------------------------------- #
def test_parse_aspect() -> None:
    assert parse_aspect("16:9") == pytest.approx(16 / 9)
    assert parse_aspect("9:16") == pytest.approx(9 / 16)
    assert parse_aspect("") is None
    assert parse_aspect(None) is None
    assert parse_aspect("bogus") is None
    assert parse_aspect("1:0") is None
