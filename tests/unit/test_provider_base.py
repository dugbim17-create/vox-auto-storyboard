"""Tests for P2-T01 provider interfaces, registry, and fake providers."""

from __future__ import annotations

import pytest

from app.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRegistry,
    ProviderRegistryError,
    TTSRequest,
    TTSResult,
)


class FakeLLM:
    async def generate_json(self, *, system_prompt, user_prompt, schema, temperature, request_id) -> dict:
        return {"ok": True, "schema_keys": sorted(schema.keys())}


class FakeImage:
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return ImageGenerationResult(path="x.png", provider="fake", width=1920, height=1080)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(status="ok")

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_text_to_image=True, aspect_ratios=["16:9"], max_concurrency=1)


class FakeTTS:
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        return TTSResult(wav_path="x.wav", duration_ms=3000, provider="fake")


def test_protocols_are_runtime_checkable() -> None:
    from app.providers.base import ImageProvider, LLMProvider, TTSProvider

    assert isinstance(FakeLLM(), LLMProvider)
    assert isinstance(FakeImage(), ImageProvider)
    assert isinstance(FakeTTS(), TTSProvider)


def test_registry_register_and_get() -> None:
    reg = ProviderRegistry()
    reg.register_llm("cliproxy", FakeLLM())
    reg.register_image("cliproxy", FakeImage())
    reg.register_tts("omnivoice", FakeTTS())

    assert isinstance(reg.llm("cliproxy"), FakeLLM)
    assert isinstance(reg.image("cliproxy"), FakeImage)
    assert isinstance(reg.tts("omnivoice"), FakeTTS)


def test_registry_missing_raises() -> None:
    reg = ProviderRegistry()
    with pytest.raises(ProviderRegistryError):
        reg.llm("nope")


def test_registry_names() -> None:
    reg = ProviderRegistry()
    reg.register_image("a", FakeImage())
    reg.register_image("b", FakeImage())
    assert sorted(reg.names("image")) == ["a", "b"]
    assert reg.names("llm") == []


def test_capabilities_discovery_image() -> None:
    reg = ProviderRegistry()
    reg.register_image("fake", FakeImage())
    caps = reg.capabilities("image", "fake")
    assert caps["supports_text_to_image"] is True
    assert caps["max_concurrency"] == 1


def test_fake_providers_run() -> None:
    # Smoke: fake LLM returns JSON; image returns result; TTS returns result.
    llm = FakeLLM()
    out = asyncio_run(llm.generate_json(system_prompt="s", user_prompt="u", schema={"a": {}}, temperature=0, request_id="r1"))
    assert out["ok"] is True


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
