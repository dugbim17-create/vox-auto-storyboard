"""Pure state helpers for the four-stage Quiz workflow.

The native Qt shell keeps one document. These helpers expose the same stage and
readiness decisions without invoking providers, TTS, image generation, or video.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.services.quiz_episode_structure import validate_and_assign_round_structure

STAGES = ("channel", "content", "appearance", "voice_export")


def normalize_quiz_workflow_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Copy and normalize round metadata while leaving the source untouched."""
    result = validate_and_assign_round_structure(document)
    result.setdefault("workflow", {})
    result["workflow"] = deepcopy(result["workflow"])
    result["workflow"].setdefault("stage", "channel")
    result["workflow"].setdefault("selected_question_id", None)
    result["workflow"].setdefault("dirty", False)
    return result


def workflow_readiness(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return truthful stage readiness; this function has no side effects."""
    questions = document.get("questions") if isinstance(document, Mapping) else None
    questions = questions if isinstance(questions, list) else []
    style = document.get("visual_style") if isinstance(document, Mapping) else None
    return {
        "channel": bool(document.get("language") or document.get("channel_profile")) if isinstance(document, Mapping) else False,
        "content": bool(questions),
        "appearance": bool(questions and isinstance(style, Mapping)),
        "voice_export": bool(questions and (document.get("settings") or document.get("voice"))) if isinstance(document, Mapping) else False,
        "question_count": len(questions),
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
    }


def select_question(document: Mapping[str, Any], question_id: str | None) -> dict[str, Any]:
    """Return a copied selected question and preserve all other questions."""
    questions = document.get("questions") if isinstance(document, Mapping) else []
    for question in questions if isinstance(questions, list) else []:
        if str(question.get("id")) == str(question_id):
            return deepcopy(question)
    raise KeyError(f"question not found: {question_id}")


__all__ = ["STAGES", "normalize_quiz_workflow_document", "select_question", "workflow_readiness"]

def update_workflow_stage(document: Mapping[str, Any], stage: str) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"unsupported workflow stage: {stage}")
    result = normalize_quiz_workflow_document(document)
    result["workflow"]["stage"] = stage
    return result


__all__.append("update_workflow_stage")


def mark_workflow_dirty(document: Mapping[str, Any], dirty: bool = True) -> dict[str, Any]:
    result = normalize_quiz_workflow_document(document)
    result["workflow"]["dirty"] = bool(dirty)
    return result


__all__.append("mark_workflow_dirty")


def preserve_regeneration_context(document: Mapping[str, Any], question_id: str) -> dict[str, Any]:
    """Return the targeted question's round/style context for current generator adapters."""
    question = select_question(document, question_id)
    return {
        "question_id": str(question.get("id")),
        "round_id": str(question.get("round_id") or "legacy"),
        "format_key": str(question.get("format_key") or "multiple_choice"),
        "difficulty": str(question.get("difficulty") or "medium"),
        "visual_style": deepcopy(document.get("visual_style")),
        "provider_calls": 0,
        "tts_calls": 0,
        "video_exports": 0,
    }


__all__.append("preserve_regeneration_context")


def replace_one_question(document: Mapping[str, Any], question_id: str, replacement: Mapping[str, Any]) -> dict[str, Any]:
    """Replace one question only; preserve round structure/style and invalidate approval."""
    result = normalize_quiz_workflow_document(document)
    found = False
    for index, question in enumerate(result["questions"]):
        if str(question.get("id")) == str(question_id):
            updated = deepcopy(dict(question))
            updated.update(deepcopy(dict(replacement)))
            updated.setdefault("id", question_id)
            updated.setdefault("round_id", question.get("round_id") or "legacy")
            updated.setdefault("order", question.get("order") or index + 1)
            result["questions"][index] = updated
            found = True
            break
    if not found:
        raise KeyError(f"question not found: {question_id}")
    result["approval"] = {"status": "draft"}
    result["workflow"]["dirty"] = True
    return result


__all__.extend(["replace_one_question"])


def normalize_and_validate_workflow(document: Mapping[str, Any]) -> dict[str, Any]:
    return normalize_quiz_workflow_document(document)


__all__.append("normalize_and_validate_workflow")
