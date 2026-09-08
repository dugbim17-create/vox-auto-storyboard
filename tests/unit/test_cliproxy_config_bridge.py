from __future__ import annotations

from app.cli import _cliproxy_config


def test_cli_config_bridge_uses_discovered_key_when_runtime_key_is_blank(monkeypatch) -> None:
    runtime = type(
        "Runtime",
        (),
        {
            "cliproxy_base_url": "http://runtime/v1",
            "cliproxy_model": "runtime-model",
            "cliproxy_api_key": "",
            "cliproxy_timeout_seconds": 120,
        },
    )()
    settings = type(
        "Settings",
        (),
        {
            "cliproxy_base_url": "http://settings/v1",
            "cliproxy_model": "settings-model",
            "cliproxy_api_key": "discovered-secret",
            "cliproxy_timeout_seconds": 180,
        },
    )()
    monkeypatch.setattr("app.cli.load_runtime_settings", lambda: runtime)
    monkeypatch.setattr("app.cli.get_settings", lambda: settings)
    result = _cliproxy_config()
    assert result["base_url"] == "http://runtime/v1"
    assert result["model"] == "runtime-model"
    assert result["api_key"] == "discovered-secret"
    assert result["timeout_seconds"] == 120


def test_cli_config_bridge_prefers_explicit_runtime_key(monkeypatch) -> None:
    runtime = type(
        "Runtime",
        (),
        {
            "cliproxy_base_url": "http://runtime/v1",
            "cliproxy_model": "runtime-model",
            "cliproxy_api_key": "runtime-secret",
            "cliproxy_timeout_seconds": 90,
        },
    )()
    settings = type("Settings", (), {"cliproxy_api_key": "discovered-secret"})()
    monkeypatch.setattr("app.cli.load_runtime_settings", lambda: runtime)
    monkeypatch.setattr("app.cli.get_settings", lambda: settings)
    assert _cliproxy_config()["api_key"] == "runtime-secret"
