"""Shared contract, schema validation, and preflight at custom Quiz import and render boundaries."""
import math
from pathlib import Path
from typing import Any
from PIL import Image


SUPPORTED_MODES = (
    "4cards",
    "visual_riddle",
    "photo_reveal",
    "multiple_choice",
    "word_tiles",
    "mystery_box",
    "this_or_that",
)


def detect_question_mode(q: dict[str, Any]) -> str:
    """Detect question archetype mode from question keys."""
    if "cards" in q:
        return "4cards"
    if "scene_image" in q or "scene_prompt" in q:
        return "visual_riddle"
    if ("reveal_image_path" in q or "reveal_image_prompt" in q) and "choices" in q:
        return "photo_reveal"
    if "choices" in q:
        return "multiple_choice"
    if "word_tiles" in q:
        return "word_tiles"
    if "boxes" in q:
        return "mystery_box"
    if "side_a" in q and "side_b" in q:
        return "this_or_that"
    return "unknown"


def validate_questions(questions: Any, *, require_assets: bool = False) -> None:
    """
    Strict contract validation for Quiz questions.
    Raises ValueError with actionable message if any question violates the contract.
    If require_assets=True, verifies all declared asset filepaths exist and decode properly.
    """
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions must be a nonempty list")

    seen_ids = set()
    for index, q in enumerate(questions, 1):
        prefix = f"Question {index}"
        if not isinstance(q, dict):
            raise ValueError(f"{prefix}: object required")

        ident = q.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen_ids:
            raise ValueError(f"{prefix}: missing or duplicate id")
        seen_ids.add(ident)

        q_text = q.get("question")
        if not isinstance(q_text, str) or not q_text.strip():
            raise ValueError(f"{prefix}: question required")

        duration = q.get("countdown_seconds", 3.5)
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise ValueError(f"{prefix}: countdown must be positive and finite")

        mode = detect_question_mode(q)
        if mode == "unknown":
            raise ValueError(
                f"{prefix}: unrecognized mode. Must declare 'cards' (4cards), "
                f"'scene_image'/'scene_prompt' (visual_riddle), 'choices' (multiple_choice / photo_reveal), "
                f"'word_tiles', 'boxes' (mystery_box), or 'side_a'/'side_b' (this_or_that)."
            )

        assets_to_check: list[tuple[str, Any]] = []

        if mode == "4cards":
            cards = q.get("cards")
            if not isinstance(cards, list) or len(cards) != 4 or not all(isinstance(c, dict) for c in cards):
                raise ValueError(f"{prefix}: four cards required")
            card_ids = []
            for ci, c in enumerate(cards, 1):
                cid = c.get("id")
                if not isinstance(cid, str) or not cid.strip():
                    raise ValueError(f"{prefix} card {ci}: id required")
                card_ids.append(cid)
                lbl = c.get("label")
                if not isinstance(lbl, str) or not lbl.strip():
                    raise ValueError(f"{prefix} card {ci}: label required")
                img_p = c.get("image_path")
                img_prompt = c.get("image_prompt")
                if not img_p and not img_prompt:
                    raise ValueError(f"{prefix} card {ci}: either image_path or image_prompt required")
                if img_p:
                    assets_to_check.append((f"card {cid} image", img_p))
                elif require_assets:
                    raise ValueError(f"{prefix} card {ci}: asset image_path missing (unresolved prompt: {img_prompt!r})")

            if len(set(card_ids)) != 4 or q.get("correct_option") not in card_ids:
                raise ValueError(f"{prefix}: invalid card answer/ids")

        elif mode == "visual_riddle":
            options = q.get("options")
            if (
                not isinstance(options, list)
                or len(options) < 2
                or not all(isinstance(option, str) and option.strip() for option in options)
                or len(set(options)) != len(options)
                or q.get("correct_option") not in options
            ):
                raise ValueError(f"{prefix}: invalid riddle options/answer")

            scene_img = q.get("scene_image")
            scene_prompt = q.get("scene_prompt")
            if not scene_img and not scene_prompt:
                raise ValueError(f"{prefix}: scene_image or scene_prompt required for visual riddle")
            if scene_img:
                assets_to_check.append(("scene_image", scene_img))
            elif require_assets:
                raise ValueError(f"{prefix}: scene_image missing (unresolved prompt: {scene_prompt!r})")

            clue = q.get("clue_highlight")
            if clue is not None:
                if not isinstance(clue, dict):
                    raise ValueError(f"{prefix}: clue_highlight must be an object")
                coord = clue.get("coord")
                if coord is not None:
                    if (
                        not isinstance(coord, (list, tuple))
                        or len(coord) != 2
                        or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in coord)
                    ):
                        raise ValueError(f"{prefix}: clue_highlight.coord must be [x, y] coordinates")

        elif mode in ("photo_reveal", "multiple_choice"):
            choices = q.get("choices")
            if not isinstance(choices, list) or len(choices) < 2:
                raise ValueError(f"{prefix}: choices required")
            ids = []
            for choice in choices:
                if isinstance(choice, dict):
                    key, text = choice.get("id"), choice.get("text")
                elif isinstance(choice, (list, tuple)) and len(choice) == 2:
                    key, text = choice
                else:
                    raise ValueError(f"{prefix}: invalid choice")
                if not isinstance(key, str) or not key.strip() or not isinstance(text, str) or not text.strip():
                    raise ValueError(f"{prefix}: choice id/text required")
                ids.append(key)
            if len(set(ids)) != len(ids) or q.get("correct_id") not in ids:
                raise ValueError(f"{prefix}: invalid correct_id/duplicate choices")

            if mode == "photo_reveal":
                rev_img = q.get("reveal_image_path")
                rev_prompt = q.get("reveal_image_prompt")
                if not rev_img and not rev_prompt:
                    raise ValueError(f"{prefix}: reveal_image_path or reveal_image_prompt required for photo reveal")
                if rev_img:
                    assets_to_check.append(("reveal_image_path", rev_img))
                elif require_assets:
                    raise ValueError(f"{prefix}: reveal_image_path missing (unresolved prompt: {rev_prompt!r})")

        elif mode == "word_tiles":
            tiles = q.get("word_tiles")
            if not isinstance(tiles, list) or len(tiles) == 0:
                raise ValueError(f"{prefix}: word_tiles must be a non-empty list")

        elif mode == "mystery_box":
            boxes = q.get("boxes")
            if not isinstance(boxes, list) or len(boxes) < 2:
                raise ValueError(f"{prefix}: boxes must contain at least 2 boxes")

        elif mode == "this_or_that":
            if not isinstance(q.get("side_a"), dict) or not isinstance(q.get("side_b"), dict):
                raise ValueError(f"{prefix}: this_or_that requires side_a and side_b objects")

        # Additional optional images
        for extra_key in ("scene_image", "reveal_image_path"):
            if extra_key in q and (extra_key, q[extra_key]) not in assets_to_check:
                assets_to_check.append((extra_key, q[extra_key]))

        if require_assets:
            for label, asset in assets_to_check:
                if not isinstance(asset, str) or not asset.strip() or not Path(asset).is_file():
                    raise ValueError(f"{prefix}: missing asset {label} {asset!r}")
                try:
                    with Image.open(asset) as image:
                        image.verify()
                except Exception as exc:
                    raise ValueError(f"{prefix}: invalid image asset {label} {asset!r}") from exc
