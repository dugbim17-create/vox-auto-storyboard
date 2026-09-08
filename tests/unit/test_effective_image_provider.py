from __future__ import annotations

from app.runtime_settings import RuntimeSettings, resolve_effective_image_provider


def test_auto_prefers_healthy_cliproxy_image() -> None:
    settings = RuntimeSettings(image_provider="auto", flowkit_enabled=True)
    assert resolve_effective_image_provider(
        settings,
        {"cliproxy_image": "ok", "flowkit": "ok", "antigravity_image": "ok"},
    ) == "cliproxy_image"


def test_explicit_unavailable_provider_falls_back_to_antigravity() -> None:
    settings = RuntimeSettings(image_provider="flowkit", flowkit_enabled=True)
    assert resolve_effective_image_provider(
        settings,
        {"cliproxy_image": "error", "flowkit": "unavailable", "antigravity_image": "ok"},
    ) == "antigravity_image"


def test_no_healthy_provider_returns_none() -> None:
    settings = RuntimeSettings(image_provider="auto")
    assert resolve_effective_image_provider(
        settings,
        {"cliproxy_image": "error", "flowkit": "unavailable", "antigravity_image": "error"},
    ) is None
