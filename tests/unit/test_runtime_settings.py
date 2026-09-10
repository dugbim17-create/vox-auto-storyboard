from __future__ import annotations

import json

from app.runtime_settings import RuntimeSettings, load_runtime_settings, save_runtime_settings


def test_runtime_settings_round_trip_masks_secret(tmp_path) -> None:
    path = tmp_path / "settings.json"
    original = RuntimeSettings(
        cliproxy_base_url="http://proxy.test/v1",
        cliproxy_model="gpt-test",
        cliproxy_api_key="secret-value",
        flowkit_enabled=True,
        flowkit_base_url="http://flow.test",
        flowkit_health_path="/healthz",
        image_provider="flowkit",
    )
    save_runtime_settings(original, path)
    loaded = load_runtime_settings(path)
    assert loaded.cliproxy_base_url == "http://proxy.test/v1"
    assert loaded.cliproxy_model == "gpt-test"
    assert loaded.cliproxy_api_key == "secret-value"
    assert loaded.flowkit_enabled is True
    assert loaded.image_provider == "flowkit"
    assert "secret-value" not in json.dumps(loaded.redacted_dict())


def test_runtime_settings_defaults_are_safe(tmp_path) -> None:
    loaded = load_runtime_settings(tmp_path / "missing.json")
    assert loaded.image_provider == "auto"
    assert loaded.cliproxy_model
    assert loaded.flowkit_health_path == "/health"


def test_runtime_settings_invalid_provider_falls_back(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"image_provider": "unknown"}), encoding="utf-8")
    loaded = load_runtime_settings(path)
    assert loaded.image_provider == "auto"
