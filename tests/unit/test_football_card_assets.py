"""Regression gates for photo-backed, glyph-safe football cards."""
import ast
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/generate_football_cards.py"


def load_definitions():
    # Do not execute the legacy script's top-level file writes during RED.
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    tree.body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    ns = {"__file__": str(SCRIPT)}
    exec(compile(tree, str(SCRIPT), "exec"), ns)
    return ns


def test_reveal_requires_and_displays_supplied_photo(tmp_path):
    ns = load_definitions()
    assert callable(ns.get("render_photo_reveal")), "Photo-backed reveal renderer is missing"
    photo = tmp_path / "portrait.png"
    Image.new("RGB", (240, 320), (193, 27, 143)).save(photo)
    p = {"name": "CRISTIANO RONALDO", "nat": "PORTUGAL 🇵🇹", "num": "7", "pos": "ST", "clue": "Über 900 Karrieretore"}
    image = ns["render_photo_reveal"](p, photo, "Photo: Test / CC BY-SA 3.0")
    assert image.size == (580, 360)
    assert image.getpixel((100, 140))[:3] == (193, 27, 143)
    with pytest.raises(FileNotFoundError):
        ns["render_photo_reveal"](p, tmp_path / "missing.png", "Photo: Test")


def test_nationality_text_does_not_require_emoji_font():
    ns = load_definitions()
    assert callable(ns.get("nationality_text")), "Emoji-independent nationality formatter is missing"
    assert ns["nationality_text"]("PORTUGAL 🇵🇹") == "PORTUGAL"
    assert ns["nationality_text"]("DEUTSCHLAND 🇩🇪") == "DEUTSCHLAND"
    assert ns["nationality_text"]("ÖSTERREICH") == "ÖSTERREICH"


def test_import_does_not_generate_or_overwrite_assets():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.For) for n in tree.body), "Import currently writes legacy assets"
    assert not any(isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "mkdir" for n in tree.body)
