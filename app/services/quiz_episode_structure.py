"""Validated, deterministic mixed-round structure for Quiz V2 episodes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

SUPPORTED_ROUND_FORMATS = ("multiple_choice", "photo_reveal", "4cards", "visual_riddle")
STRUCTURE_SCHEMA_VERSION = 1
_ALLOWED_DIFFICULTIES = ("easy", "medium", "hard", "final", "mixed")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ch in value for ch in "\r\n\x00"):
        raise ValueError(f"invalid round {field}")
    return value.strip()


def validate_episode_structure(structure: Mapping[str, Any], *, episode_count: int) -> None:
    if not isinstance(structure, Mapping):
        raise ValueError("round structure must be an object")
    version = structure.get("schema_version", STRUCTURE_SCHEMA_VERSION)
    if isinstance(version, bool) or not isinstance(version, int) or version != STRUCTURE_SCHEMA_VERSION:
        raise ValueError(f"unsupported round structure schema version: {version}")
    if isinstance(episode_count, bool) or not isinstance(episode_count, int) or episode_count <= 0:
        raise ValueError("episode count must be positive")
    rounds = structure.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        raise ValueError("round structure must contain rounds")
    seen: set[str] = set()
    total = 0
    for index, round_item in enumerate(rounds, 1):
        if not isinstance(round_item, Mapping):
            raise ValueError(f"round {index} must be an object")
        ident = _text(round_item.get("id"), "id")
        if ident in seen:
            raise ValueError(f"duplicate round id: {ident}")
        seen.add(ident)
        _text(round_item.get("label"), "label")
        format_key = _text(round_item.get("format_key"), "format")
        if format_key not in SUPPORTED_ROUND_FORMATS:
            raise ValueError(f"unsupported round format: {format_key}")
        count = round_item.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError(f"invalid round count: {ident}")
        difficulty = round_item.get("difficulty", "medium")
        if not isinstance(difficulty, str) or difficulty not in _ALLOWED_DIFFICULTIES:
            raise ValueError(f"invalid round difficulty: {ident}")
        total += count
    if total != episode_count:
        raise ValueError(f"round count {total} does not match episode count {episode_count}")


def allocate_round_questions(structure: Mapping[str, Any], *, episode_count: int) -> list[dict[str, Any]]:
    validate_episode_structure(structure, episode_count=episode_count)
    allocation: list[dict[str, Any]] = []
    order = 1
    for round_item in structure["rounds"]:
        format_key = str(round_item["format_key"])
        requires_asset = format_key in {"photo_reveal", "4cards", "visual_riddle"}
        for _ in range(int(round_item["count"])):
            allocation.append({
                "order": order,
                "round_id": str(round_item["id"]),
                "round_label": str(round_item["label"]),
                "format_key": format_key,
                "difficulty": str(round_item.get("difficulty", "medium")),
                "requires_asset": requires_asset,
                "asset_status": "pending" if requires_asset else "not_required",
            })
            order += 1
    return allocation


def build_episode_structure(
    mode: str, *, episode_count: int, format_key: str = "photo_reveal"
) -> dict[str, Any]:
    """Build the smallest supported round plan for the native authoring flow."""
    if mode not in {"single", "mixed"}:
        raise ValueError(f"unsupported structure mode: {mode}")
    if format_key not in SUPPORTED_ROUND_FORMATS:
        raise ValueError(f"unsupported round format: {format_key}")
    if isinstance(episode_count, bool) or not isinstance(episode_count, int) or episode_count <= 0:
        raise ValueError("episode count must be positive")

    if mode == "single" or episode_count == 1:
        structure = {
            "schema_version": STRUCTURE_SCHEMA_VERSION,
            "mode": "single",
            "rounds": [
                {
                    "id": "main",
                    "label": "Xuyên suốt",
                    "format_key": format_key,
                    "count": episode_count,
                    "difficulty": "mixed",
                }
            ],
        }
    else:
        first_count = max(1, episode_count // 2)
        if format_key != "photo_reveal":
            raise ValueError(
                "mixed structure currently requires the supported multiple_choice + photo_reveal pair; "
                f"received {format_key}"
            )
        structure = {
            "schema_version": STRUCTURE_SCHEMA_VERSION,
            "mode": "mixed",
            "rounds": [
                {
                    "id": "warmup",
                    "label": "Khởi động",
                    "format_key": "multiple_choice",
                    "count": first_count,
                    "difficulty": "easy",
                },
                {
                    "id": "visual",
                    "label": "Nhìn kỹ",
                    "format_key": "photo_reveal",
                    "count": episode_count - first_count,
                    "difficulty": "medium",
                },
            ],
        }
    validate_episode_structure(structure, episode_count=episode_count)
    return structure


def apply_round_allocation(
    questions: list[dict[str, Any]], structure: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Attach and validate stable round metadata on returned generated questions."""
    allocation = allocate_round_questions(structure, episode_count=len(questions))
    from app.services.quiz_v2_contract import detect_question_mode

    result: list[dict[str, Any]] = []
    for question, slot in zip(questions, allocation, strict=True):
        if not isinstance(question, dict):
            raise ValueError("generated question must be an object")
        actual_mode = detect_question_mode(question)
        expected_mode = str(slot["format_key"])
        if actual_mode != expected_mode:
            raise ValueError(
                f"generated round allocation mismatch: expected {expected_mode}, got {actual_mode}"
            )
        item = deepcopy(question)
        item["order"] = int(slot["order"])
        item["round_id"] = str(slot["round_id"])
        item["round_label"] = str(slot["round_label"])
        item["format_key"] = actual_mode
        item["difficulty"] = str(slot["difficulty"])
        item["requires_asset"] = bool(slot["requires_asset"])
        item["asset_status"] = str(slot["asset_status"])
        result.append(item)
    return result


def assign_legacy_round(document: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise ValueError("quiz document must be an object")
    result = deepcopy(dict(document))
    questions = result.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions must be a nonempty list")
    if result.get("round_structure") is not None:
        validate_episode_structure(result["round_structure"], episode_count=len(questions))
    else:
        result["round_structure"] = {
            "schema_version": STRUCTURE_SCHEMA_VERSION,
            "mode": "single",
            "rounds": [{
                "id": "legacy",
                "label": "Legacy",
                "format_key": "multiple_choice",
                "count": len(questions),
                "difficulty": "mixed",
            }],
        }
    explicit_round_ids = {
        str(item.get("id"))
        for item in result["round_structure"].get("rounds", [])
        if isinstance(item, Mapping)
    }
    fallback_round_id = "legacy" if "legacy" in explicit_round_ids else next(iter(explicit_round_ids))
    for order, question in enumerate(result["questions"], 1):
        if isinstance(question, dict):
            question.setdefault("round_id", fallback_round_id)
            question.setdefault("order", order)
    return result


__all__ = [
    "SUPPORTED_ROUND_FORMATS",
    "STRUCTURE_SCHEMA_VERSION",
    "apply_round_allocation",
    "allocate_round_questions",
    "assign_legacy_round",
    "build_episode_structure",
    "validate_episode_structure",
]


def validate_and_assign_round_structure(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copied document with validated explicit or legacy round assignments."""
    return assign_legacy_round(document)


__all__.append("validate_and_assign_round_structure")
