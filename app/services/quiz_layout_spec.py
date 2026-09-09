"""Pure adaptive layout contract for opt-in channel style rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class LayoutSpecError(ValueError):
    """Raised when content cannot fit the requested safe layout."""


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.right, self.bottom

    def contains(self, other: Rect) -> bool:
        return self.x <= other.x and self.y <= other.y and self.right >= other.right and self.bottom >= other.bottom

    def overlaps(self, other: Rect) -> bool:
        return self.x < other.right and other.x < self.right and self.y < other.bottom and other.y < self.bottom


@dataclass(frozen=True)
class LayoutSpec:
    aspect: str
    canvas: Rect
    header: Rect
    question: Rect
    visual: Rect | None
    choices: tuple[Rect, ...]
    fact: Rect | None
    badge: Rect | None
    fit: str
    mode: str
    safe_margin: int

    def to_dict(self) -> dict[str, Any]:
        def rect(value: Rect | None) -> list[int] | None:
            return list(value.as_tuple()) if value is not None else None

        return {
            "aspect": self.aspect,
            "canvas": rect(self.canvas),
            "header": rect(self.header),
            "question": rect(self.question),
            "visual": rect(self.visual),
            "choices": [rect(choice) for choice in self.choices],
            "fact": rect(self.fact),
            "badge": rect(self.badge),
            "fit": self.fit,
            "mode": self.mode,
            "safe_margin": self.safe_margin,
        }


def _aspect_size(aspect: str) -> tuple[int, int]:
    if aspect == "16:9":
        return 1920, 1080
    if aspect == "9:16":
        return 1080, 1920
    raise LayoutSpecError(f"unsupported aspect: {aspect}")


def _style_values(style: Mapping[str, Any] | None) -> tuple[int, str]:
    data = style or {}
    snapshot = data.get("snapshot") if isinstance(data, Mapping) else None
    spacing = snapshot.get("spacing") if isinstance(snapshot, Mapping) else None
    safe_margin = spacing.get("safe_margin", 56) if isinstance(spacing, Mapping) else 56
    if isinstance(safe_margin, bool) or not isinstance(safe_margin, int) or not 0 <= safe_margin <= 240:
        raise LayoutSpecError("invalid style safe_margin")
    style_id = str(data.get("id") or "clear-knowledge") if isinstance(data, Mapping) else "clear-knowledge"
    return safe_margin, style_id


def _content_mode(content: Mapping[str, Any]) -> str:
    if content.get("cards"):
        return "four-card"
    if content.get("scene_image") or content.get("reveal_image_path"):
        return "hero-image"
    choices = content.get("choices") or content.get("options") or []
    if len(choices) == 2:
        return "two-choice"
    return "text-only"


def _choice_count(content: Mapping[str, Any]) -> int:
    choices = content.get("choices") or content.get("options") or content.get("cards") or []
    return len(choices)


def _validate_text_budget(content: Mapping[str, Any], question: Rect, fact: Rect | None, *, style_id: str) -> None:
    question_text = str(content.get("question") or "")
    question_limit = 132 if question.width >= 1100 else 96
    if len(question_text) > question_limit:
        raise LayoutSpecError(
            f"blocked_overflow: question text length {len(question_text)} exceeds bounded layout budget {question_limit}; use a wider composition or shorten the question"
        )
    fact_text = str(content.get("fact") or content.get("explanation_text") or "")
    if fact is not None and len(fact_text) > 220:
        raise LayoutSpecError(
            f"blocked_overflow: fact text length {len(fact_text)} exceeds bounded reveal area; provide a bounded reveal substate"
        )
    if style_id == "sport-scoreboard" and question.width < 900:
        raise LayoutSpecError("blocked_overflow: sport question column is too narrow")


def resolve_layout(
    content: Mapping[str, Any],
    aspect: str = "16:9",
    style: Mapping[str, Any] | None = None,
) -> LayoutSpec:
    if not isinstance(content, Mapping):
        raise LayoutSpecError("content must be an object")
    width, height = _aspect_size(aspect)
    safe_margin, style_id = _style_values(style)
    canvas = Rect(0, 0, width, height)
    header = Rect(safe_margin, safe_margin, width - 2 * safe_margin, 100)
    mode = _content_mode(content)
    if aspect == "16:9":
        question = Rect(safe_margin, 190, width - 2 * safe_margin, 240)
        visual = None
        fact = None
        badge = None
        if mode == "hero-image":
            visual = Rect(safe_margin, 470, 540, 360)
        elif mode == "four-card":
            visual = Rect(safe_margin, 470, 900, 400)
            badge = Rect(safe_margin, 426, 900, 32)
        elif mode == "two-choice":
            visual = None
        if mode in {"hero-image", "four-card"}:
            choices_x, choices_y, choices_w = 1120, 470, width - 1120 - safe_margin
        elif mode == "two-choice":
            choices_x, choices_y, choices_w = safe_margin, 500, width - 2 * safe_margin
        else:
            choices_x, choices_y, choices_w = safe_margin, 500, width - 2 * safe_margin
        count = _choice_count(content)
        if mode == "two-choice":
            choice_gap = 32
            choice_w = (choices_w - choice_gap) // 2
            choices = (
                Rect(choices_x, choices_y, choice_w, 190),
                Rect(choices_x + choice_w + choice_gap, choices_y, choice_w, 190),
            )
        elif mode == "four-card":
            choices = tuple(Rect(choices_x, choices_y + i * 120, choices_w, 94) for i in range(count))
        else:
            choices = tuple(Rect(choices_x, choices_y + i * 112, choices_w, 84) for i in range(count))
        if content.get("fact") or content.get("explanation_text"):
            fact = Rect(safe_margin, 850, width - 2 * safe_margin, 100)
            if fact.y + fact.height > height - safe_margin:
                fact = Rect(safe_margin, 800, width - 2 * safe_margin, 100)
    else:
        question = Rect(safe_margin, 210, width - 2 * safe_margin, 240)
        visual = None
        fact = None
        badge = None
        if mode == "hero-image":
            visual = Rect(safe_margin, 500, width - 2 * safe_margin, 480)
        elif mode == "four-card":
            visual = Rect(safe_margin, 500, width - 2 * safe_margin, 500)
            badge = Rect(safe_margin, 456, width - 2 * safe_margin, 32)
        count = _choice_count(content)
        choices_y = 1080 if visual else 520
        choice_h = 180 if count <= 2 else 130
        gap = 28
        choices = tuple(Rect(safe_margin, choices_y + i * (choice_h + gap), width - 2 * safe_margin, choice_h) for i in range(count))
        if content.get("fact") or content.get("explanation_text"):
            fact = Rect(safe_margin, 1720, width - 2 * safe_margin, 130)

    _validate_text_budget(content, question, fact, style_id=style_id)
    occupied = [header, question, *choices]
    if visual is not None:
        occupied.append(visual)
    if badge is not None:
        for choice in choices:
            if badge.overlaps(choice):
                raise LayoutSpecError(f"badge overlaps choice: {badge.as_tuple()} vs {choice.as_tuple()}")
    if fact is not None:
        occupied.append(fact)
    for item in occupied:
        if not canvas.contains(item) or item.x < safe_margin or item.y < safe_margin or item.right > width - safe_margin or item.bottom > height - safe_margin:
            raise LayoutSpecError(f"safe bounds violation: {item.as_tuple()}")
    for index, left in enumerate(occupied):
        for right in occupied[index + 1:]:
            if left.overlaps(right):
                raise LayoutSpecError(f"layout overlap: {left.as_tuple()} vs {right.as_tuple()}")
    fit = "contain-complete-subject" if mode == "hero-image" else "none"
    return LayoutSpec(aspect, canvas, header, question, visual, choices, fact, badge, fit, mode, safe_margin)


__all__ = ["LayoutSpec", "LayoutSpecError", "Rect", "resolve_layout"]
