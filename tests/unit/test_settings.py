"""Tests for the P1-T01 Pydantic-Settings config system."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import config as app_config
from app import settings
from app.settings import Settings


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the Settings singleton between tests so env mutations apply."""
    monkeypatch.setattr(settings, "_settings", None)


def test_defaults_load() -> None:
    s = Settings(_env_file=None)
    assert s.app_host == "127.0.0.1"
    assert s.default_fps == 30
    assert s.default_image_provider == "antigravity_image"
    assert s.omnivoice_default_language == "vi"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "9999")
    monkeypatch.setenv("DEFAULT_FPS", "24")
    s = Settings(_env_file=None)
    assert s.app_port == 9999
    assert s.default_fps == 24


def test_project_root_resolves_and_creates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_config, "REPO_ROOT", tmp_path)
    target = tmp_path / "nested" / "projects"
    monkeypatch.setenv("PROJECT_ROOT", "nested/projects")
    s = Settings(_env_file=None)
    # project_root validated to absolute under repo root
    assert Path(s.project_root) == target


def test_secret_redacted_in_dump() -> None:
    s = Settings(_env_file=None)
    d = s.redacted_dict()
    assert d["cliproxy_api_key"] == "<redacted>"
    assert "<redacted>" not in str(s)


def test_missing_secret_not_printed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing/placeholder key never leaks the real value into output."""
    monkeypatch.delenv("CLIPROXY_API_KEY", raising=False)
    s = Settings(_env_file=None)
    print(s)  # __str__ must not contain the raw key
    captured = capsys.readouterr()
    assert "sk-" not in captured.out
    assert "local-placeholder" not in captured.out  # value never printed, only field name


def test_discovered_omnivoice_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Placeholder OmniVoice path falls back to the discovered venv python."""
    fake = tmp_path / "python.exe"
    fake.write_bytes(b"")
    monkeypatch.setattr(app_config, "_OMNIVOICE_VENV_PYTHON_CANDIDATES", [fake])
    monkeypatch.setenv("OMNIVOICE_VENV_PYTHON", "C:/PATH/TO/OMNIVOICE/venv/Scripts/python.exe")
    s = Settings(_env_file=None)
    assert s.omnivoice_venv_python == str(fake)


def test_get_settings_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    a = settings.get_settings()
    b = settings.get_settings()
    assert a is b
