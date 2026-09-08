"""Scene image prompt builder (P4-T04).

Builds deterministic, per-role image prompts for every scene of a validated
storyboard, ready to feed an ``ImageGenerationRequest`` per layer role.

Unlike the planner prompt (P2-T04/P2-T05), this builder does NOT call an LLM:
it composes a fixed prompt string on a template basis so the image stage is
fast, reproducible, and never asks the model for text (the renderer types text
itself — a hard project rule).

Roles (MASTER_PLAN section 8.2 / image_prompt.md):

- ``background``  -> clean wide environment, style/continuity, wide empty area;
- ``subject``     -> the character(s) / hero element, verbatim character desc;
- ``foreground``  -> a depth/parallax element overlapping the frame edge;
- ``texture``     -> a detail/overlay texture patch on style palette;
- ``composite``   -> a full-frame composite combining all layers + reference.

Continuity (AC3) comes from re-using the same style anchor + verbatim character
descriptions across all scenes. Text-free safety (AC1/AC2) is enforced via a
shared ``TEXT_SAFE_STUB`` in every role prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.base import IMAGE_ROLES, ImageGenerationRequest
from app.schemas.style_contract import StyleSnapshotV1

# Text-safe clause appended to every role prompt so the model never renders
# letters/typography (the local renderer draws text itself).
TEXT_SAFE_STUB = (
    "No text, no words, no letters, no numbers, no caption, no watermark, "
    "no logo, no sign, no typography anywhere in the image."
)

# Order of the interior (non-composite) role prompts emitted per scene.
_INTERIOR_ROLES: tuple[str, ...] = ("background", "subject", "foreground", "texture")
_COMPOSITE_ROLE = "composite"


@dataclass(frozen=True)
class BuiltPrompt:
    """One role's prompt for one scene, ready to become an ImageGenerationRequest."""

    scene_id: str
    role: str  # one of IMAGE_ROLES
    prompt: str
    negative_constraints: tuple[str, ...]
    aspect_ratio: str
    reference_images: tuple[str, ...]


class SceneImagePromptBuilderError(Exception):
    """Base error for the prompt builder."""


class SceneImagePromptBuilder:
    """Compose per-role image prompts for a storyboard."""

    def __init__(self, *, aspect_ratio: str = "16:9") -> None:
        self.aspect_ratio = aspect_ratio or "16:9"

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def build(self, storyboard: dict[str, Any]) -> dict[str, list[BuiltPrompt]]:
        """Return ``{scene_id: [BuiltPrompt, ...]}`` for all scenes.

        ``storyboard`` is a validated storyboard dict (as produced by
        ScriptAnalyzer): it has ``style_anchor``, ``characters``, ``locations``
        and ``scenes[].image_prompt``. The composite prompt is always first so
        the orchestrator can use it as the primary/reference request.
        """
        style = _style(storyboard)
        style_negatives = tuple(style.get("negative_prompt") or ())
        characters = _characters(storyboard)
        locations = _locations(storyboard)

        out: dict[str, list[BuiltPrompt]] = {}
        for scene in storyboard.get("scenes", []):
            scene_id = scene.get("scene_id", "")
            if not scene_id:
                raise SceneImagePromptBuilderError("scene missing scene_id")
            negs = tuple(
                dict.fromkeys(
                    (*tuple(scene.get("negative_constraints") or ()), *style_negatives)
                )
            )
            base_prompt = scene.get("image_prompt", "")
            if not base_prompt:
                raise SceneImagePromptBuilderError(f"{scene_id}: missing image_prompt")

            ref = _reference_images(characters)
            plans = [
                BuiltPrompt(
                    scene_id=scene_id,
                    role=_COMPOSITE_ROLE,
                    prompt=self._composite_prompt(base_prompt, characters, locations, style),
                    negative_constraints=negs,
                    aspect_ratio=self.aspect_ratio,
                    reference_images=ref,
                )
            ]
            for role in _INTERIOR_ROLES:
                plans.append(
                    BuiltPrompt(
                        scene_id=scene_id,
                        role=role,
                        prompt=self._role_prompt(role, base_prompt, scene, characters, style),
                        negative_constraints=negs + ("flat",) if role == "foreground" else negs,
                        aspect_ratio=self.aspect_ratio,
                        reference_images=(),
                    )
                )
            out[scene_id] = plans
        return out

    def build_role(
        self,
        storyboard: dict[str, Any],
        scene_id: str,
        role: str,
    ) -> BuiltPrompt:
        """Build a single role for a single scene."""
        if role not in IMAGE_ROLES:
            raise SceneImagePromptBuilderError(
                f"invalid role {role!r}; expected one of {IMAGE_ROLES}"
            )
        built = self.build(storyboard).get(scene_id)
        if not built:
            raise SceneImagePromptBuilderError(f"scene {scene_id!r} not found")
        for plan in built:
            if plan.role == role:
                return plan
        raise SceneImagePromptBuilderError(f"{scene_id}: no {role!r} plan built")

    def to_request(
        self,
        plan: BuiltPrompt,
        *,
        seed: int | None = None,
        output_path: str = "",
    ) -> ImageGenerationRequest:
        """Wrap a built prompt into an ImageGenerationRequest."""
        return ImageGenerationRequest(
            prompt=plan.prompt,
            role=plan.role,
            negative_prompt=", ".join(plan.negative_constraints),
            reference_images=list(plan.reference_images),
            aspect_ratio=plan.aspect_ratio,
            seed=seed,
            candidate_count=1,
            output_path=output_path,
        )

    # ------------------------------------------------------------------ #
    # Role composition
    # ------------------------------------------------------------------ #
    def _role_prompt(
        self,
        role: str,
        base_prompt: str,
        scene: dict[str, Any],
        characters: list[dict[str, Any]],
        style: dict[str, Any],
    ) -> str:
        style_block = _style_block(style)
        if role == "background":
            return (
                "Wide clean background layer only. Empty implied backdrop and "
                f"atmosphere. {base_prompt} Do not place the subject here; keep "
                f"distance and open space. {style_block} {TEXT_SAFE_STUB}"
            ).strip()
        if role == "subject":
            people = _character_block(scene, characters)
            return (
                f"Hero subject layer. {people} {base_prompt} "
                f"{style_block} {TEXT_SAFE_STUB}"
            ).strip()
        if role == "foreground":
            return (
                "Foreground overlay layer for depth. A stylized element at the "
                "frame edge (blurred branch/pillar/shapes), out of focus, "
                f"providing parallax separation. {base_prompt} {style_block} "
                f"{TEXT_SAFE_STUB}"
            ).strip()
        if role == "texture":
            return (
                "Abstract texture/overlay patch only, matching the storyboard "
                "style. Solid or subtle, no scene content. "
                f"{style_block} {TEXT_SAFE_STUB}"
            ).strip()
        raise SceneImagePromptBuilderError(f"unhandled role {role!r}")

    def _composite_prompt(
        self,
        base_prompt: str,
        characters: list[dict[str, Any]],
        locations: list[dict[str, Any]],
        style: dict[str, Any],
    ) -> str:
        char_names = ", ".join(_name(c) for c in characters) or "none"
        loc_names = ", ".join(_name(location) for location in locations) or "open static set"
        return (
            f"Full composite reference frame. {base_prompt} "
            f"Characters: {char_names}. Location: {loc_names}. "
            f"{_style_block(style)} Keep the three-layer separation clean "
            f"(background / subject / foreground). {TEXT_SAFE_STUB}"
        ).strip()


# --------------------------------------------------------------------------- #
# Storyboard extraction helpers
# --------------------------------------------------------------------------- #
def _style(storyboard: dict[str, Any]) -> dict[str, Any]:
    snapshot = storyboard.get("style_snapshot")
    if isinstance(snapshot, dict) and snapshot:
        normalized = StyleSnapshotV1.from_mapping(snapshot)
        return {
            "visual_language": normalized.visual_language,
            "palette": list(normalized.palette),
            "texture": list(normalized.texture),
            "typography": normalized.typography,
            "negative_prompt": list(normalized.negative_prompt),
            "continuity_rules": list(normalized.continuity_rules),
        }
    anchor = storyboard.get("style_anchor")
    if not isinstance(anchor, dict):
        return {}
    return {
        "visual_language": anchor.get("visual_language", ""),
        "palette": anchor.get("palette", []),
        "texture": anchor.get("texture", []),
        "typography": anchor.get("typography", ""),
        "negative_prompt": anchor.get("negative_prompt", []),
        "continuity_rules": anchor.get("continuity_rules", []),
    }


def _characters(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in storyboard.get("characters", []) if isinstance(c, dict)]


def _locations(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    return [loc for loc in storyboard.get("locations", []) if isinstance(loc, dict)]


def _name(entity: dict[str, Any]) -> str:
    return str(entity.get("name") or entity.get("character_id") or entity.get("location_id") or "")


def _description(entity: dict[str, Any]) -> str:
    return str(entity.get("description") or "").strip()


def _style_block(style: dict[str, Any]) -> str:
    """Inline the style anchor as a compact continuity clause."""
    parts: list[str] = []
    if style.get("visual_language"):
        parts.append(f"Visual language: {style['visual_language']}")
    palette = style.get("palette")
    if palette:
        joined = ", ".join(str(p) for p in palette) if isinstance(palette, (list, tuple)) else str(palette)
        parts.append(f"Palette: {joined}")
    texture = style.get("texture")
    if texture:
        joined = ", ".join(str(t) for t in texture) if isinstance(texture, (list, tuple)) else str(texture)
        parts.append(f"Texture: {joined}")
    if parts:
        return "Style: " + " | ".join(parts) + "."
    return "Style: keep consistent with the storyboard look."


def _character_block(scene: dict[str, Any], characters: list[dict[str, Any]]) -> str:
    """Name the characters present in this scene with their verbatim description.

    Falls back to "consistent main character" when the scene does not declare
    characters — continuity still holds via the shared style block.
    """
    if not characters:
        return "Consistent main character, matching the storyboard design."
    named: list[str] = []
    for char in characters:
        name = _name(char)
        desc = _description(char)
        if desc:
            named.append(f"{name} ({desc})")
        else:
            named.append(name)
    return "; ".join(named) + "."


def _reference_images(
    characters: list[dict[str, Any]],
    explicit: Any = None,
) -> tuple[str, ...]:
    """Return reference image paths for this scene.

    Uses the first character's image (if any) as a style reference so the
    subject stays consistent across scenes. Explicit per-scene reference
    images are not part of the validated storyboard shape, so characters are
    the only source today.
    """
    if isinstance(explicit, list) and explicit:
        return tuple(str(path) for path in explicit)
    if isinstance(explicit, str) and explicit:
        return (explicit,)
    if characters:
        char_ref = characters[0].get("image") or characters[0].get("image_path")
        if char_ref:
            return (str(char_ref),)
    return ()
