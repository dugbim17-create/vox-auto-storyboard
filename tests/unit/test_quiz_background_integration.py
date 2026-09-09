from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image


def test_renderer_default_background_is_local_and_does_not_call_network(monkeypatch) -> None:
    from app.services import quiz_background
    from app.services import quiz_channel_renderer as renderer
    from app.services.quiz_engine_v2 import get_font
    from app.services.quiz_style_packs import resolve_style_snapshot

    calls: list[str] = []
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: calls.append("network"))
    style = resolve_style_snapshot("clear-knowledge", locale="en-US")
    engine = SimpleNamespace(
        opt=SimpleNamespace(channel_profile="de-wissen", visual_style=style),
        _normalize_choices=lambda q: [("A", "One"), ("B", "Two")],
    )
    background = quiz_background.resolve_background(style)
    canvas = Image.new("RGB", (1920, 1080), "black")
    renderer.render(
        engine,
        canvas,
        __import__("PIL").ImageDraw.Draw(canvas),
        get_font,
        event={"idx": 1, "total_q": 1, "rev_start": 8, "cd_start": 2, "data": {"question": "Question?", "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}], "correct_id": "A"}},
        time=3,
    )
    assert background["kind"] == "procedural"
    assert background["source"] is None
    assert calls == []


def test_approved_background_is_not_replaced_by_unapproved_path(tmp_path: Path) -> None:
    from app.services.quiz_background import resolve_background

    source = tmp_path / "approved.png"
    Image.new("RGB", (32, 32), "white").save(source)
    result = resolve_background({"id": "sport-scoreboard"}, local_path=source, approved_root=tmp_path)
    assert result["kind"] == "local"
    assert result["source"] == str(source.resolve())
