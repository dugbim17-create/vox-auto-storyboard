"""Tests for P4-T03 Antigravity image adapter.

The adapter calls the CLIProxy Antigravity generateContent route over HTTP.
Tests inject an ``httpx.MockTransport`` so no live service is required. Covers
the AC:

- implement theo discovered contract (payload shape, route, inlineData decode);
- normalize result (ImageGenerationResult with dimensions + sha256, file written);
- error handling (401 -> AuthError, 404 -> NotFound, bad payload -> Validation);
- health / capabilities;
- provider switching is config-driven (base_url/model from settings).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from app.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)
from app.providers.image.antigravity import (
    AntigravityImageAuthError,
    AntigravityImageNotFoundError,
    AntigravityImageProvider,
    AntigravityImageRetryableError,
    AntigravityImageValidationError,
)


def _make_png_bytes() -> bytes:
    """A tiny real PNG (10x8 RGB) to use as the model's inlineData payload."""
    buf = io.BytesIO()
    Image.new("RGB", (10, 8), color=(200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _ok_response_bytes() -> str:
    return base64.b64encode(_make_png_bytes()).decode("ascii")


def make_provider(handler: Any) -> AntigravityImageProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://antigravity")
    return AntigravityImageProvider(
        base_url="http://antigravity",
        api_key="sk-test",
        timeout_seconds=30,
        httpx_client=client,
    )


def ok_handler() -> Any:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "data": _ok_response_bytes(),
                                        "mimeType": "image/png",
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    return _handler


@pytest.mark.asyncio
async def test_generate_writes_file_and_normalizes_result(tmp_path: Path) -> None:
    provider = make_provider(ok_handler())
    out = str(tmp_path / "scene_001.png")
    req = ImageGenerationRequest(prompt="a red cat", role="background", output_path=out)
    result = await provider.generate(req)

    assert isinstance(result, ImageGenerationResult)
    assert result.provider == "antigravity_image"
    assert result.width == 10
    assert result.height == 8
    assert len(result.prompt_hash) == 16
    assert len(result.sha256) == 64

    written = Path(out)
    assert written.is_file()
    assert written.read_bytes() == _make_png_bytes()


@pytest.mark.asyncio
async def test_generate_sends_discovered_contract() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"inlineData": {"data": _ok_response_bytes()}}]}}
                ]
            },
        )

    provider = make_provider(handler)
    import json

    await provider.generate(
        ImageGenerationRequest(
            prompt="a cat",
            role="subject",
            output_path="tmp/scene.png",
        )
    )
    assert captured["url"].endswith(
        "/v1beta/models/gemini-3.1-flash-image:generateContent"
    )
    body = json.loads(captured["body"])
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert body["contents"][0]["parts"][0]["text"] == "a cat"


@pytest.mark.asyncio
async def test_negative_prompt_folded_into_text() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"inlineData": {"data": _ok_response_bytes()}}]}}]},
        )

    provider = make_provider(handler)
    import json

    await provider.generate(
        ImageGenerationRequest(
            prompt="a cat",
            role="foreground",
            negative_prompt="blurry",
            output_path="tmp/scene.png",
        )
    )
    body = json.loads(captured["body"])
    assert "blurry" in body["contents"][0]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_generate_requires_output_path() -> None:
    provider = make_provider(ok_handler())
    req = ImageGenerationRequest(prompt="p", role="background")
    with pytest.raises(AntigravityImageValidationError):
        await provider.generate(req)


@pytest.mark.asyncio
async def test_auth_error_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    provider = make_provider(handler)
    with pytest.raises(AntigravityImageAuthError):
        await provider.generate(
            ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
        )


@pytest.mark.asyncio
async def test_not_found_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    provider = make_provider(handler)
    with pytest.raises(AntigravityImageNotFoundError):
        await provider.generate(
            ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
        )


@pytest.mark.asyncio
async def test_no_inline_data_raises_validation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "nope"}]}}]},
        )

    provider = make_provider(handler)
    with pytest.raises(AntigravityImageValidationError):
        await provider.generate(
            ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
        )


@pytest.mark.asyncio
async def test_invalid_base64_raises_validation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"inlineData": {"data": "!!!not-b64!!!"}}]}}
                ]
            },
        )

    provider = make_provider(handler)
    with pytest.raises(AntigravityImageValidationError):
        await provider.generate(
            ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
        )


@pytest.mark.asyncio
async def test_transport_error_retried_then_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"inlineData": {"data": _ok_response_bytes()}}]}}]},
        )

    provider = make_provider(handler)
    result = await provider.generate(
        ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
    )
    assert calls["count"] == 2
    assert result.provider == "antigravity_image"


@pytest.mark.asyncio
async def test_retry_429_then_success() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"inlineData": {"data": _ok_response_bytes()}}]}}]},
        )

    provider = make_provider(handler)
    result = await provider.generate(
        ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
    )
    assert calls["count"] == 2
    assert result.width == 10


@pytest.mark.asyncio
async def test_retries_exhausted_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    provider = make_provider(handler)
    with pytest.raises(AntigravityImageRetryableError):
        await provider.generate(
            ImageGenerationRequest(prompt="p", role="background", output_path="tmp/a.png")
        )


@pytest.mark.asyncio
async def test_health_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "gemini-3.1-flash-image"}, {"id": "gpt-image-2"}]},
        )

    provider = make_provider(handler)
    health = await provider.health()
    assert health.status == "ok"
    assert "image" in str(health.detail["image_models"])


@pytest.mark.asyncio
async def test_health_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    provider = make_provider(handler)
    health = await provider.health()
    assert health.status == "unavailable"


@pytest.mark.asyncio
async def test_capabilities() -> None:
    provider = make_provider(ok_handler())
    caps = await provider.capabilities()
    assert caps.supports_text_to_image is True
    assert caps.supports_reference_image is False
    assert caps.supports_alpha is False
    assert caps.aspect_ratios == ["16:9"]
    assert caps.max_concurrency == 1


@pytest.mark.asyncio
async def test_provider_is_runtime_checkable() -> None:
    from app.providers.base import ImageProvider

    provider = make_provider(ok_handler())
    assert isinstance(provider, ImageProvider)
