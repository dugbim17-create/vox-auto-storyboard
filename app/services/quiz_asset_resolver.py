"""
Quiz Asset Resolver Service:
Resolves image prompts in quiz questions to validated local file assets.
Prioritizes existing valid files -> cached content-addressed assets -> AI generation via CLIProxy.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any
from PIL import Image

from app.services.quiz_v2_contract import validate_questions, detect_question_mode
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.providers.base import ImageGenerationRequest
from app.services.quiz_generation_budget import GenerationBudget
from app.services.quiz_image_layout import image_slot, inspect_layout, layout_prompt, prompt_kind


async def generate_quiz_image(prompt: str, output_path: Path, model: str = "gpt-image-2", *, budget_limit: int = 6) -> Path:
    kind = prompt_kind(prompt)
    slot = image_slot(kind)
    budget = GenerationBudget(output_path.parent, limit=budget_limit)
    ticket = budget.reserve(hashlib.sha256(f"{model}|{prompt}".encode()).hexdigest())
    if model.startswith("gemini"):
        from app.providers.image.antigravity import AntigravityImageProvider
        provider = AntigravityImageProvider(model=model)
    else:
        provider = CliproxyImageProvider(model=model, fallback_models=[model])
    temporary = output_path.with_name(output_path.stem + '.pending.png')
    try:
        await provider.generate(ImageGenerationRequest(prompt=prompt, role="composite", output_path=str(temporary), candidate_count=1,
            aspect_ratio=slot.aspect_ratio, provider_params={"size": slot.provider_size}))
        if not _is_valid_image(temporary):
            raise RuntimeError("Generated quiz image cannot decode; submission remains unknown")
        inspect_layout(temporary, kind, generated=True)
        temporary.replace(output_path)
        budget.complete(ticket)
        return output_path
    finally:
        await provider.aclose()


# Compatibility seam used by resolver tests; no sticker prompt rewriting.
generate_ai_image_asset = generate_quiz_image


def _is_valid_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


async def resolve_quiz_assets(
    questions: list[dict[str, Any]],
    output_dir: Path,
    image_model: str = "gpt-image-2",
    *,
    allow_generation: bool = False,
    rights_policy: str = "legacy",
    budget_limit: int = 6,
) -> list[dict[str, Any]]:
    """
    Asynchronously resolves visual prompts to local image assets.
    Updates questions with local 'image_path', 'scene_image', and 'reveal_image_path'.
    Validates final questions before returning.
    """
    if rights_policy == "verified_or_generate":
        from app.services.quiz_asset_policy import resolve_with_policy
        validate_questions(questions, require_assets=False)
        async def generate_for_episode(prompt, path, model):
            if budget_limit == 6:
                return await generate_ai_image_asset(prompt, path, model=model)
            return await generate_ai_image_asset(prompt, path, model=model, budget_limit=budget_limit)
        resolved = await resolve_with_policy(questions, output_dir, image_model, allow_generation, generate_for_episode)
        validate_questions(resolved, require_assets=True)
        return resolved
    if rights_policy != "legacy":
        raise ValueError("Unknown Quiz image rights policy")
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    resolved_questions: list[dict[str, Any]] = []

    for q in questions:
        q_copy = dict(q)
        qid = str(q_copy.get("id") or "q")
        mode = detect_question_mode(q_copy)

        if mode == "4cards":
            cards = q_copy.get("cards") or []
            new_cards = []
            for c in cards:
                c_copy = dict(c)
                cid = str(c_copy.get("id") or "1")
                existing_p = c_copy.get("image_path")
                if existing_p and _is_valid_image(Path(existing_p)):
                    c_copy["image_layout"] = inspect_layout(existing_p, "card")
                    new_cards.append(c_copy)
                    continue

                prompt = c_copy.get("image_prompt")
                if not prompt:
                    raise ValueError(f"Question {qid} card {cid} has neither valid image_path nor image_prompt")

                prompt = layout_prompt(prompt, "card")
                p_hash = hashlib.sha256(f"cliproxy|{image_model}|{prompt}".encode("utf-8")).hexdigest()[:24]
                target_p = output_dir / f"{qid}_card_{cid}_{p_hash}.png"
                if not _is_valid_image(target_p):
                    if not allow_generation:
                        raise RuntimeError(f"Asset {qid}/{cid} unresolved; image generation requires explicit permission")
                    await generate_ai_image_asset(prompt, target_p, model=image_model)
                if not _is_valid_image(target_p):
                    raise RuntimeError(f"Failed to resolve image for question {qid} card {cid} from prompt: {prompt!r}")
                c_copy["image_path"] = str(target_p.resolve())
                c_copy["image_layout"] = inspect_layout(target_p, "card", generated=True)
                new_cards.append(c_copy)
            q_copy["cards"] = new_cards

        elif mode == "visual_riddle":
            existing_scene = q_copy.get("scene_image")
            if existing_scene and _is_valid_image(Path(existing_scene)):
                q_copy["scene_image_layout"] = inspect_layout(existing_scene, "scene")
                resolved_questions.append(q_copy)
                continue

            scene_prompt = q_copy.get("scene_prompt")
            if not scene_prompt:
                raise ValueError(f"Question {qid} (visual_riddle) has neither valid scene_image nor scene_prompt")

            scene_prompt = layout_prompt(scene_prompt, "scene")
            p_hash = hashlib.sha256(f"cliproxy|{image_model}|{scene_prompt}".encode("utf-8")).hexdigest()[:24]
            target_p = output_dir / f"{qid}_scene_{p_hash}.png"
            if not _is_valid_image(target_p):
                if not allow_generation:
                    raise RuntimeError(f"Asset {qid}/scene unresolved; image generation requires explicit permission")
                await generate_ai_image_asset(scene_prompt, target_p, model=image_model)
            if not _is_valid_image(target_p):
                raise RuntimeError(f"Failed to resolve scene_image for question {qid} from prompt: {scene_prompt!r}")
            q_copy["scene_image"] = str(target_p.resolve())
            q_copy["scene_image_layout"] = inspect_layout(target_p, "scene", generated=True)

        elif mode in ("photo_reveal", "multiple_choice"):
            existing_rev = q_copy.get("reveal_image_path")
            if existing_rev and _is_valid_image(Path(existing_rev)):
                q_copy["reveal_image_layout"] = inspect_layout(existing_rev, "reveal")
                resolved_questions.append(q_copy)
                continue

            rev_prompt = q_copy.get("reveal_image_prompt")
            if rev_prompt:
                rev_prompt = layout_prompt(rev_prompt, "reveal")
                p_hash = hashlib.sha256(f"cliproxy|{image_model}|{rev_prompt}".encode("utf-8")).hexdigest()[:24]
                target_p = output_dir / f"{qid}_reveal_{p_hash}.png"
                if not _is_valid_image(target_p):
                    if not allow_generation:
                        raise RuntimeError(f"Asset {qid}/reveal unresolved; image generation requires explicit permission")
                    await generate_ai_image_asset(rev_prompt, target_p, model=image_model)
                if not _is_valid_image(target_p):
                    raise RuntimeError(f"Failed to resolve reveal_image for question {qid} from prompt: {rev_prompt!r}")
                q_copy["reveal_image_path"] = str(target_p.resolve())
                q_copy["reveal_image_layout"] = inspect_layout(target_p, "reveal", generated=True)

        resolved_questions.append(q_copy)

    # Post-condition verification: all required assets must exist and decode
    validate_questions(resolved_questions, require_assets=True)
    return resolved_questions
