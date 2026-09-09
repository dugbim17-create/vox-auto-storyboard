from __future__ import annotations

from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw

from app.services.quiz_channel_renderer import render
from app.services.quiz_engine_v2 import get_font
from app.services.quiz_style_packs import resolve_style_snapshot


def _render_with_style(style_id: str) -> Image.Image:
    snapshot = resolve_style_snapshot(style_id, locale="de-DE")
    engine = SimpleNamespace(
        opt=SimpleNamespace(channel_profile="de-wissen", visual_style=snapshot),
        _normalize_choices=lambda question: [("A", "Antwort A"), ("B", "Antwort B")],
    )
    canvas = Image.new("RGB", (1920, 1080), "black")
    event = {
        "idx": 1,
        "total_q": 10,
        "rev_start": 8,
        "cd_start": 2,
        "data": {
            "question": "Welche Richtung ist korrekt?",
            "correct_id": "A",
            "difficulty": "medium",
            "series": "Wissen",
        },
    }
    return render(engine, canvas, ImageDraw.Draw(canvas), get_font, event=event, time=3)


def test_persisted_style_snapshot_reaches_compositor_and_changes_visual_output() -> None:
    sport = _render_with_style("sport-scoreboard")
    editorial = _render_with_style("editorial-culture")
    assert ImageChops.difference(sport, editorial).getbbox() is not None


def test_no_visual_style_keeps_channel_profile_palette() -> None:
    engine = SimpleNamespace(
        opt=SimpleNamespace(channel_profile="de-wissen"),
        _normalize_choices=lambda question: [("A", "Antwort A"), ("B", "Antwort B")],
    )
    canvas = Image.new("RGB", (1920, 1080), "black")
    event = {
        "idx": 1,
        "total_q": 10,
        "rev_start": 8,
        "cd_start": 2,
        "data": {"question": "Welche Richtung ist korrekt?", "correct_id": "A", "difficulty": "medium"},
    }
    rendered = render(engine, canvas, ImageDraw.Draw(canvas), get_font, event=event, time=3)
    assert rendered.getpixel((0, 0)) == (25, 29, 32)
