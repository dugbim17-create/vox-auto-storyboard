"""Tests for .env config loading + CLIProxy key discovery (P0-T03)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import config


def test_defaults_load() -> None:
    assert config.get("APP_ENV") in {"local", ""}
    assert config.get("CLIPROXY_BASE_URL").startswith("http")


def test_discover_cliproxy_key_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The discovery parser extracts the api-key and strips surrounding quotes."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        'api-keys:\n  - "sk-test-real-key"\n'
        "foo: bar\n",
        encoding="utf-8",
    )
    # Point discovery at the tmp config (monkeypatch the candidate list).
    monkeypatch.setattr(config, "_CLIPROXY_CONFIG_CANDIDATES", [cfg])
    key = config._discover_cliproxy_api_key()
    assert key == "sk-test-real-key"


def test_discover_returns_empty_when_api_keys_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: x\n", encoding="utf-8")
    monkeypatch.setattr(config, "_CLIPROXY_CONFIG_CANDIDATES", [cfg])
    assert config._discover_cliproxy_api_key() == ""


def test_get_prefers_env_over_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIPROXY_BASE_URL", "http://env:9999")
    assert config.get("CLIPROXY_BASE_URL") == "http://env:9999"


def test_omnivoice_discovery_from_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OMNIVOICE_VENV_PYTHON falls back to the discovered venv when unset."""
    fake_py = tmp_path / "python.exe"
    fake_py.write_bytes(b"")
    monkeypatch.setattr(config, "_OMNIVOICE_VENV_PYTHON_CANDIDATES", [fake_py])
    monkeypatch.delenv("OMNIVOICE_VENV_PYTHON", raising=False)
    # Reset cache so discovery re-runs against the patched candidate.
    monkeypatch.setattr(config, "_loaded", None)
    got = config.get("OMNIVOICE_VENV_PYTHON")
    assert got == str(fake_py)
