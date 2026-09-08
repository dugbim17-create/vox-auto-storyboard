"""Layer package validator (P5-T01).

Validates a scene's layer package — the dict mapping ``role -> image path``
produced by the image stage (P4-T05) — before it reaches the renderer. Checks
(MASTER_PLAN P5-T01):

- validate image: file exists and is decodable by Pillow;
- role: key is one of the known layer roles;
- aspect: pixel aspect matches an optional target, with tolerance;
- alpha: subject/foreground/texture/composite expected to carry alpha (RGBA);
  background expected opaque;
- dimensions: within an optional canvas bound and a sane maximum side.

The validator is non-destructive: it collects problems rather than raising, so
the orchestrator can gather all issues for a scene at once. A convenience
``validate_or_raise`` raises ``LayerPackageValidationError`` on any problem.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image

from app.providers.base import IMAGE_ROLES

# Roles expected to carry an alpha channel for compositing.
ALPHA_ROLES: tuple[str, ...] = ("subject", "foreground", "texture", "composite")
# Roles expected fully opaque.
OPAQUE_ROLES: tuple[str, ...] = ("background",)

# Aspect tolerance: pixel ratio must be within this fraction of the target.
_ASPECT_TOLERANCE = 0.10
# Sane maximum image side; larger images are rejected as degenerate.
_MAX_SIDE = 16384


class LayerPackageValidationError(Exception):
    """Raised by ``validate_or_raise`` when a layer package has problems."""


@dataclass(frozen=True)
class ValidationProblem:
    """One issue found while validating a layer package."""

    role: str
    message: str

    def __str__(self) -> str:
        return f"{self.role}: {self.message}"


@dataclass
class ImageInfo:
    """Facts about a validated layer image."""

    path: str
    role: str
    width: int
    height: int
    mode: str
    has_alpha: bool


@dataclass
class LayerValidationResult:
    """Outcome of validating one layer package."""

    problems: list[ValidationProblem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def messages(self) -> list[str]:
        return [str(p) for p in self.problems]


# Loader signature: (path) -> PIL.Image. Uses Pillow by default; tests may inject.
def _pillow_open(path: str) -> Image.Image:
    return Image.open(path)


class LayerPackageValidator:
    """Validate a scene layer package (role -> image path)."""

    def __init__(
        self,
        *,
        canvas_width: int | None = None,
        canvas_height: int | None = None,
        aspect_ratio: str | None = None,
        loader: Callable[[str], Image.Image] | None = None,
    ) -> None:
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.aspect_ratio = aspect_ratio
        self._loader = loader or _pillow_open

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def validate(self, layer_package: dict) -> LayerValidationResult:
        """Validate a dict mapping role -> image path."""
        result = LayerValidationResult()

        if not isinstance(layer_package, dict) or not layer_package:
            result.problems.append(ValidationProblem("(package)", "empty or not a dict"))
            return result

        for role, entry in layer_package.items():
            self._validate_role(role, result)
            self._validate_entry(role, entry, result)
        return result

    def validate_or_raise(self, layer_package: dict) -> LayerValidationResult:
        """Validate; raise ``LayerPackageValidationError`` on any problem."""
        result = self.validate(layer_package)
        if result.problems:
            raise LayerPackageValidationError(
                "layer package invalid: " + "; ".join(result.messages)
            )
        return result

    # ------------------------------------------------------------------ #
    # Per-entry checks
    # ------------------------------------------------------------------ #
    def _validate_role(self, role: str, result: LayerValidationResult) -> None:
        if role not in IMAGE_ROLES:
            result.problems.append(
                ValidationProblem(role, f"unknown role; expected one of {IMAGE_ROLES}")
            )

    def _validate_entry(self, role: str, entry, result: LayerValidationResult) -> None:
        path = entry if isinstance(entry, str) else (entry.get("path") if isinstance(entry, dict) else None)
        if not path:
            result.problems.append(ValidationProblem(role, "missing path"))
            return

        info = self._inspect(str(path), role)
        if info is None:
            result.problems.append(ValidationProblem(role, f"missing or undecodable image: {path}"))
            return

        if self.aspect_ratio:
            self._check_aspect(info, result)
        self._check_dimensions(info, result)
        self._check_alpha(role, info, result)

    def _inspect(self, path: str, role: str) -> ImageInfo | None:
        """Decode the image and return its info; None on failure."""
        try:
            with self._loader(path) as img:
                width, height = img.size
                mode = img.mode
                # Detect whether the mode has an alpha channel.
                has_alpha = "A" in mode.upper()
                return ImageInfo(
                    path=str(path), role=role, width=width, height=height,
                    mode=mode, has_alpha=has_alpha,
                )
        except Exception:  # noqa: BLE001
            return None

    def _check_aspect(self, info: ImageInfo, result: LayerValidationResult) -> None:
        if info.width <= 0 or info.height <= 0:
            return
        target = parse_aspect(self.aspect_ratio)
        if target is None:
            return
        ratio = info.width / info.height
        if abs(ratio - target) / target > _ASPECT_TOLERANCE:
            result.problems.append(
                ValidationProblem(
                    info.role,
                    f"aspect {ratio:.3f} does not match target {self.aspect_ratio}",
                )
            )

    def _check_dimensions(self, info: ImageInfo, result: LayerValidationResult) -> None:
        if info.width > _MAX_SIDE or info.height > _MAX_SIDE:
            result.problems.append(
                ValidationProblem(info.role, f"dimensions too large ({info.width}x{info.height})")
            )
        if self.canvas_width and self.canvas_height and (
            info.width > self.canvas_width or info.height > self.canvas_height
        ):
                result.problems.append(
                    ValidationProblem(
                        info.role,
                        f"larger than canvas {self.canvas_width}x{self.canvas_height}",
                    )
                )

    def _check_alpha(self, role: str, info: ImageInfo, result: LayerValidationResult) -> None:
        if role in ALPHA_ROLES and not info.has_alpha:
            result.problems.append(
                ValidationProblem(role, "expected alpha channel (RGBA) but got opaque")
            )
        if role in OPAQUE_ROLES and info.has_alpha:
            result.problems.append(
                ValidationProblem(role, "expected opaque (no alpha) but got transparency")
            )


def parse_aspect(aspect: str | None) -> float | None:
    """Turn '16:9' into 16/9; None on parse failure or empty."""
    if not aspect:
        return None
    try:
        a, _, b = aspect.partition(":")
        return float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return None
