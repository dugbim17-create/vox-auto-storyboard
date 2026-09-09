from __future__ import annotations

import pytest

from app.services.quiz_layout_spec import LayoutSpecError, resolve_layout


def _text_only() -> dict:
    return {"question": "What causes the runway number to change?", "choices": [{"id": "A", "text": "Magnetic heading"}, {"id": "B", "text": "Opening year"}, {"id": "C", "text": "Runway length"}, {"id": "D", "text": "Airline choice"}]}


def _style(style_id: str = "clear-knowledge", safe_margin: int = 56) -> dict:
    return {"id": style_id, "snapshot": {"spacing": {"safe_margin": safe_margin}}}


def test_text_only_does_not_allocate_visual_slot_and_uses_freed_space() -> None:
    layout = resolve_layout(_text_only(), "16:9", _style())

    assert layout.mode == "text-only"
    assert layout.visual is None
    assert layout.question.width == 1920 - 2 * layout.safe_margin
    assert layout.choices
    assert all(layout.canvas.contains(rect) for rect in (*layout.choices, layout.question))


def test_text_only_portrait_still_has_no_placeholder_visual_slot() -> None:
    layout = resolve_layout(_text_only(), "9:16", _style())

    assert layout.mode == "text-only"
    assert layout.visual is None
    assert len(layout.choices) == 4
    assert all(layout.canvas.contains(rect) for rect in layout.choices)


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_two_choice_layout_keeps_exactly_two_visible_rectangles(aspect: str) -> None:
    content = {"question": "Which explanation fits?", "choices": [{"id": "A", "text": "Magnetic heading"}, {"id": "B", "text": "Opening year"}]}
    layout = resolve_layout(content, aspect, _style())

    assert layout.mode == "two-choice"
    assert len(layout.choices) == 2
    assert not layout.choices[0].overlaps(layout.choices[1])
    assert all(layout.canvas.contains(rect) for rect in layout.choices)
    if aspect == "16:9":
        assert layout.choices[0].y == layout.choices[1].y
        assert layout.choices[0].x < layout.choices[1].x
    else:
        assert layout.choices[0].y < layout.choices[1].y


def test_hero_image_uses_contain_policy_and_separate_visual_area() -> None:
    content = {"question": "What is shown?", "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}], "reveal_image_path": "existing.png"}
    layout = resolve_layout(content, "16:9", _style())

    assert layout.mode == "hero-image"
    assert layout.visual is not None
    assert layout.fit == "contain-complete-subject"
    assert not layout.visual.overlaps(layout.choices[0])


def test_four_card_count_keeps_all_four_card_rectangles() -> None:
    content = {"question": "Count the objects", "cards": [{"id": str(i), "label": str(i), "image_path": "asset.png"} for i in range(4)]}
    layout = resolve_layout(content, "9:16", _style())

    assert layout.mode == "four-card"
    assert len(layout.choices) == 4
    assert layout.visual is not None
    assert all(layout.canvas.contains(rect) for rect in layout.choices)


def test_long_question_fails_with_actionable_overflow_message() -> None:
    content = {"question": " ".join(["long-question"] * 80), "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}]}

    with pytest.raises(LayoutSpecError, match="blocked_overflow.*wider composition|shorten"):
        resolve_layout(content, "9:16", _style())


def test_long_fact_fails_closed_instead_of_silent_truncation() -> None:
    content = {"question": "Short?", "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}], "fact": "fact " * 100}

    with pytest.raises(LayoutSpecError, match="bounded reveal"):
        resolve_layout(content, "16:9", _style())


def test_invalid_aspect_or_safe_margin_fails_closed() -> None:
    with pytest.raises(LayoutSpecError, match="aspect"):
        resolve_layout(_text_only(), "1:1", _style())
    with pytest.raises(LayoutSpecError, match="safe_margin"):
        resolve_layout(_text_only(), "16:9", _style(safe_margin=999))


def test_fact_area_is_after_choices_and_safe_for_short_fact() -> None:
    content = {
        "question": "Short?",
        "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}],
        "fact": "A short verified fact.",
    }
    layout = resolve_layout(content, "16:9", _style())
    assert layout.fact is not None
    assert layout.fact.y >= max(choice.bottom for choice in layout.choices)
    assert all(not layout.fact.overlaps(choice) for choice in layout.choices)


def test_style_specific_geometry_changes_without_changing_content_mode() -> None:
    content = _text_only()
    compact = resolve_layout(content, "16:9", _style("sport-scoreboard", safe_margin=48))
    open_layout = resolve_layout(content, "16:9", _style("clear-knowledge", safe_margin=56))
    assert compact.mode == open_layout.mode == "text-only"
    assert compact.safe_margin != open_layout.safe_margin
    assert compact.question != open_layout.question


def test_portrait_four_card_layout_exposes_badge_and_keeps_all_cards_visible() -> None:
    layout = resolve_layout(
        {"question": "Count", "cards": [{"id": str(i), "label": str(i), "image_path": "asset.png"} for i in range(4)]},
        "9:16",
        _style(),
    )
    assert layout.visual is not None
    assert layout.badge is not None
    assert len(layout.choices) == 4
    assert all(layout.canvas.contains(choice) for choice in layout.choices)
    assert all(not layout.badge.overlaps(choice) for choice in layout.choices)
