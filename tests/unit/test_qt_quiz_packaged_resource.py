from __future__ import annotations

from pathlib import Path

from app.gui_qt import resolve_packaged_resource


def test_source_resource_keeps_existing_relative_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "presets" / "quiz.json"
    path.parent.mkdir()
    path.write_text("{}", encoding="utf-8")

    assert resolve_packaged_resource("presets/quiz.json") == path


def test_frozen_resource_resolves_under_meipass(tmp_path: Path, monkeypatch) -> None:
    bundled = tmp_path / "presets" / "quiz.json"
    bundled.parent.mkdir()
    bundled.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setattr("app.gui_qt.sys._MEIPASS", str(tmp_path), raising=False)

    assert resolve_packaged_resource("presets/quiz.json") == bundled
