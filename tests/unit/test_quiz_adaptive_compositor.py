from __future__ import annotations

from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.services import quiz_channel_renderer as renderer
from app.services.quiz_engine_v2 import get_font
from app.services.quiz_style_packs import resolve_style_snapshot


def _engine(style_id: str = "clear-knowledge") -> SimpleNamespace:
    snapshot = resolve_style_snapshot(style_id, locale="de-DE")
    return SimpleNamespace(
        opt=SimpleNamespace(channel_profile="de-wissen", visual_style=snapshot),
        _normalize_choices=lambda question: [
            (str(choice["id"]), str(choice["text"]))
            for choice in question.get("choices", [])
        ],
    )


def _event(question: dict) -> dict:
    return {"idx": 1, "total_q": 10, "rev_start": 8, "cd_start": 2, "data": question}


def test_styled_text_only_does_not_draw_image_instruction_or_placeholder(monkeypatch) -> None:
    texts: list[tuple[str, tuple[int, int, int, int]]] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append((str(text), tuple(box)))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        _engine(),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "What causes the runway number to change?",
            "choices": [
                {"id": "A", "text": "Magnetic heading"},
                {"id": "B", "text": "Opening year"},
                {"id": "C", "text": "Runway length"},
                {"id": "D", "text": "Airline choice"},
            ],
            "correct_id": "A",
        }),
        time=3,
    )

    assert all(text != "WÄHLE DIE RICHTIGE ANTWORT" for text, _box in texts)
    assert all(text != "?" for text, _box in texts)


def test_styled_two_choice_landscape_uses_balanced_same_row_boxes(monkeypatch) -> None:
    texts: list[tuple[str, tuple[int, int, int, int]]] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append((str(text), tuple(box)))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        _engine("clear-knowledge"),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "Which explanation fits?",
            "choices": [
                {"id": "A", "text": "Magnetic heading"},
                {"id": "B", "text": "Opening year"},
            ],
            "correct_id": "A",
        }),
        time=3,
    )

    choice_boxes = [box for text, box in texts if text.startswith("A  ") or text.startswith("B  ")]
    assert len(choice_boxes) == 2
    assert choice_boxes[0][1] == choice_boxes[1][1]
    assert choice_boxes[0][0] < choice_boxes[1][0]


def test_styled_four_card_layout_keeps_badge_text_outside_visual_area(monkeypatch) -> None:
    texts: list[tuple[str, tuple[int, int, int, int]]] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append((str(text), tuple(box)))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        _engine("clear-knowledge"),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "Count the objects.",
            "cards": [
                {"id": "1", "label": "ONE"},
                {"id": "2", "label": "TWO"},
                {"id": "3", "label": "THREE"},
                {"id": "4", "label": "FOUR"},
            ],
            "correct_option": "1",
        }),
        time=3,
    )

    card_labels = [box for text, box in texts if text in {"ONE", "TWO", "THREE", "FOUR"}]
    assert len(card_labels) == 4


def test_styled_question_uses_dark_text_on_light_clear_background(monkeypatch) -> None:
    texts: list[tuple[str, tuple[int, int, int, int], object]] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append((str(text), tuple(box), fill))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        _engine("clear-knowledge"),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "Which explanation fits?",
            "choices": [{"id": "A", "text": "Magnetic heading"}, {"id": "B", "text": "Opening year"}],
            "correct_id": "A",
        }),
        time=3,
    )

    question_fill = next(fill for text, _box, fill in texts if text == "Which explanation fits?")
    assert question_fill == (31, 43, 42)


def test_styled_two_choice_landscape_has_compact_choice_boxes(monkeypatch) -> None:
    texts: list[tuple[str, tuple[int, int, int, int]]] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append((str(text), tuple(box)))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        _engine("clear-knowledge"),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "Which explanation fits?",
            "choices": [{"id": "A", "text": "Magnetic heading"}, {"id": "B", "text": "Opening year"}],
            "correct_id": "A",
        }),
        time=3,
    )

    choice_boxes = [box for text, box in texts if text.startswith("A  ") or text.startswith("B  ")]
    assert all(box[3] - box[1] <= 210 for box in choice_boxes)


def test_styled_portrait_two_choice_uses_separate_vertical_boxes(monkeypatch) -> None:
    texts: list[tuple[str, tuple[int, int, int, int]]] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append((str(text), tuple(box)))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1080, 1920), "black")
    renderer.render(
        _engine("clear-knowledge"),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "Which explanation fits?",
            "choices": [
                {"id": "A", "text": "Magnetic heading"},
                {"id": "B", "text": "Opening year"},
            ],
            "correct_id": "A",
        }),
        time=3,
    )

    choice_boxes = [box for text, box in texts if text.startswith("A  ") or text.startswith("B  ")]
    assert len(choice_boxes) == 2
    assert choice_boxes[0][1] < choice_boxes[1][1]
    assert choice_boxes[0][0] == choice_boxes[1][0]


def test_styled_reveal_fact_is_rendered_instead_of_dropped(monkeypatch) -> None:
    texts: list[str] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        texts.append(str(text))

    monkeypatch.setattr(renderer, "text_box", capture)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        _engine("clear-knowledge"),
        canvas,
        ImageDraw.Draw(canvas),
        get_font,
        event=_event({
            "question": "Which explanation fits?",
            "choices": [{"id": "A", "text": "Magnetic heading"}, {"id": "B", "text": "Opening year"}],
            "correct_id": "A",
            "explanation_text": "The heading follows magnetic north.",
        }),
        time=9,
    )

    assert any("The heading follows magnetic north." in text for text in texts)
