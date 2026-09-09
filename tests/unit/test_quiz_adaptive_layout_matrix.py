from __future__ import annotations

import pytest

from app.services.quiz_layout_spec import Rect, resolve_layout

LOCALES = ("en-US", "vi-VN", "de-DE", "fr-FR", "it-IT", "ja-JP", "ko-KR", "es-ES")
ASPECTS = ("16:9", "9:16")


def _content(mode: str, locale: str) -> dict:
    question = {
        "en-US": "Which explanation fits the rule?",
        "vi-VN": "Lời giải thích nào phù hợp với quy tắc?",
        "de-DE": "Welche Erklärung passt zur Regel?",
        "fr-FR": "Quelle explication correspond à la règle ?",
        "it-IT": "Quale spiegazione corrisponde alla regola?",
        "ja-JP": "この規則に合う説明はどれですか？",
        "ko-KR": "이 규칙에 맞는 설명은 무엇인가요?",
        "es-ES": "¿Qué explicación corresponde a la regla?",
    }[locale]
    if mode == "text-only":
        return {
            "question": question,
            "choices": [{"id": x, "text": x} for x in "ABCD"],
        }
    if mode == "two-choice":
        return {
            "question": question,
            "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}],
        }
    if mode == "hero-image":
        return {
            "question": question,
            "choices": [{"id": "A", "text": "Yes"}, {"id": "B", "text": "No"}],
            "reveal_image_path": "asset.png",
        }
    return {
        "question": question,
        "cards": [{"id": str(i), "label": f"Card {i}", "image_path": "asset.png"} for i in range(4)],
    }


def _style(style_id: str = "clear-knowledge", safe_margin: int = 56) -> dict:
    return {"id": style_id, "snapshot": {"spacing": {"safe_margin": safe_margin}}}


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("aspect", ASPECTS)
@pytest.mark.parametrize("mode", ("text-only", "two-choice", "hero-image", "four-card"))
def test_all_supported_locales_and_aspects_resolve_without_overlap(locale: str, aspect: str, mode: str) -> None:
    layout = resolve_layout(_content(mode, locale), aspect, _style())

    assert layout.mode == mode
    if mode in {"text-only", "two-choice"}:
        assert layout.visual is None
    else:
        assert layout.visual is not None
    assert all(layout.canvas.contains(rect) for rect in (layout.question, *layout.choices))
    if layout.visual is not None:
        assert layout.canvas.contains(layout.visual)
    assert all(
        not left.overlaps(right)
        for index, left in enumerate(layout.choices)
        for right in layout.choices[index + 1 :]
    )


def test_style_safe_margin_is_shared_by_all_rectangles() -> None:
    layout = resolve_layout(_content("text-only", "vi-VN"), "16:9", _style(safe_margin=72))
    assert layout.safe_margin == 72
    assert layout.header.x == 72
    assert layout.question.x == 72
    assert all(choice.x == 72 for choice in layout.choices)


def test_four_card_layout_exposes_badge_safe_zone_outside_visual_evidence() -> None:
    layout = resolve_layout(_content("four-card", "en-US"), "16:9", _style())
    assert layout.visual is not None
    assert layout.badge is not None
    assert not layout.badge.overlaps(layout.visual)
    assert all(not layout.badge.overlaps(choice) for choice in layout.choices)
