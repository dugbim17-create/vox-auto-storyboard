from __future__ import annotations

from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw

from app.services import quiz_channel_renderer as renderer
from app.services.quiz_engine_v2 import get_font
from app.services.quiz_style_packs import resolve_style_snapshot


def _event() -> dict:
    return {
        "idx": 1,
        "total_q": 10,
        "rev_start": 8,
        "cd_start": 2,
        "data": {
            "question": "Which explanation fits?",
            "choices": [
                {"id": "A", "text": "Magnetic heading"},
                {"id": "B", "text": "Opening year"},
            ],
            "correct_id": "A",
            "difficulty": "medium",
        },
    }


def _render(motion: str, time: float) -> Image.Image:
    snapshot = resolve_style_snapshot("clear-knowledge", locale="en-US", motion=motion)
    engine = SimpleNamespace(
        opt=SimpleNamespace(channel_profile="de-wissen", visual_style=snapshot),
        _normalize_choices=lambda question: [(str(c["id"]), str(c["text"])) for c in question["choices"]],
    )
    canvas = Image.new("RGB", (1920, 1080), "black")
    return renderer.render(engine, canvas, ImageDraw.Draw(canvas), get_font, event=_event(), time=time)


def test_same_style_and_time_is_pixel_deterministic() -> None:
    first = _render("medium", 3.0)
    second = _render("medium", 3.0)
    assert first.tobytes() == second.tobytes()


def test_motion_level_changes_rendered_state_without_changing_answer_content() -> None:
    low = _render("low", 3.0)
    high = _render("high", 3.0)
    assert ImageChops.difference(low, high).getbbox() is not None


def test_question_and_reveal_preserve_answer_text_across_motion_levels(monkeypatch) -> None:
    captured: list[str] = []

    def capture(draw, text, box, font_factory, size=42, fill="white"):
        captured.append(str(text))

    monkeypatch.setattr(renderer, "text_box", capture)
    for motion in ("low", "medium", "high"):
        captured.clear()
        _render(motion, 3.0)
        question_text = tuple(captured)
        captured.clear()
        _render(motion, 9.0)
        reveal_text = tuple(captured)
        assert any("Magnetic heading" in text for text in question_text)
        assert any("Magnetic heading" in text for text in reveal_text)


def test_motion_marker_stays_inside_top_safe_band() -> None:
    frame = _render("high", 3.0)
    assert frame.getbbox() == (0, 0, 1920, 1080)
    assert frame.getpixel((0, 118)) != (0, 0, 0)


def test_motion_change_does_not_change_answer_text_or_geometry() -> None:
    from app.services.quiz_layout_spec import resolve_layout

    content = _event()["data"]
    style = resolve_style_snapshot("clear-knowledge", locale="en-US", motion="high")
    layout = resolve_layout(content, "16:9", style)
    assert layout.choices[0].as_tuple() == (56, 500, 944, 690)
    assert layout.choices[1].as_tuple() == (976, 500, 1864, 690)
