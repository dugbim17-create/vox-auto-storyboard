"""Tests for P2-T02 Cliproxy LLM adapter.

Covers the acceptance criteria:

- integration test with the local CLIProxy (skipped when the service is down);
- mock test for 429 (retry then success);
- mock test for malformed JSON (non-retryable validation error);
- credentials never logged.

The HTTP client is injected via ``httpx.MockTransport`` so these tests do not
require the CLIProxy service to be running, except the explicit integration
test which probes the real local endpoint.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest

from app.providers.llm.cliproxy import (
    CliproxyAuthError,
    CliproxyLLMError,
    CliproxyLLMProvider,
    CliproxyModelNotFoundError,
    CliproxyValidationError,
)

SCHEMA = {
    "type": "object",
    "required": ["scene_count", "summary"],
    "properties": {
        "scene_count": {"type": "integer"},
        "summary": {"type": "string"},
    },
}


def make_provider(handler: Any) -> CliproxyLLMProvider:
    """Build a provider with an injected mock transport client."""
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test/v1")
    return CliproxyLLMProvider(
        base_url="http://test/v1",
        api_key="test-key",
        model="gemini-test",
        max_retries=3,
        httpx_client=client,
    )


def ok_handler(json_body: dict) -> Any:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json_body)

    return _handler


def chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@pytest.mark.asyncio
async def test_generate_json_success() -> None:
    provider = make_provider(
        ok_handler(chat_response(json.dumps({"scene_count": 2, "summary": "s"})))
    )
    result = await provider.generate_json(
        system_prompt="s",
        user_prompt="u",
        schema=SCHEMA,
        temperature=0.2,
        request_id="req-1",
    )
    assert result == {"scene_count": 2, "summary": "s"}


@pytest.mark.asyncio
async def test_generate_json_accepts_markdown_fence() -> None:
    body = chat_response('```json\n{"scene_count": 1, "summary": "x"}\n```')
    provider = make_provider(ok_handler(body))
    result = await provider.generate_json(
        system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
    )
    assert result == {"scene_count": 1, "summary": "x"}


@pytest.mark.asyncio
async def test_retry_on_429_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(
            200, json=chat_response(json.dumps({"scene_count": 3, "summary": "ok"}))
        )

    provider = make_provider(handler)
    result = await provider.generate_json(
        system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
    )
    assert result["scene_count"] == 3
    assert calls["n"] == 3  # two retries happened


@pytest.mark.asyncio
async def test_retry_on_503_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(
            200, json=chat_response(json.dumps({"scene_count": 1, "summary": "ok"}))
        )

    provider = make_provider(handler)
    await provider.generate_json(
        system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
    )
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_429_exhausts_retries_raises() -> None:
    provider = make_provider(
        lambda request: httpx.Response(429, text="always limited")
    )
    with pytest.raises(CliproxyLLMError):
        await provider.generate_json(
            system_prompt="s",
            user_prompt="u",
            schema=SCHEMA,
            temperature=0,
            request_id="r",
        )


@pytest.mark.asyncio
async def test_malformed_json_raises_validation_error() -> None:
    provider = make_provider(ok_handler(chat_response("not json at all")))
    with pytest.raises(CliproxyValidationError):
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
        )


@pytest.mark.asyncio
async def test_non_object_json_raises_validation_error() -> None:
    provider = make_provider(ok_handler(chat_response("[1, 2, 3]")))
    with pytest.raises(CliproxyValidationError):
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
        )


@pytest.mark.asyncio
async def test_missing_required_keys_raises_validation_error() -> None:
    # Valid JSON but missing the required `summary` key.
    provider = make_provider(ok_handler(chat_response('{"scene_count": 2}')))
    with pytest.raises(CliproxyValidationError) as excinfo:
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
        )
    assert "summary" in str(excinfo.value)


@pytest.mark.asyncio
async def test_validation_error_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=chat_response("bad json"))

    provider = make_provider(handler)
    with pytest.raises(CliproxyValidationError):
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
        )
    assert calls["n"] == 1  # no retry on validation error


@pytest.mark.asyncio
async def test_401_raises_auth_error() -> None:
    provider = make_provider(lambda request: httpx.Response(401, text="unauthorized"))
    with pytest.raises(CliproxyAuthError):
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
        )


@pytest.mark.asyncio
async def test_404_raises_model_not_found() -> None:
    provider = make_provider(lambda request: httpx.Response(404, text="not found"))
    with pytest.raises(CliproxyModelNotFoundError):
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="r"
        )


@pytest.mark.asyncio
async def test_health_ok() -> None:
    provider = make_provider(
        lambda request: httpx.Response(
            200, json={"data": [{"id": "gemini-test"}]}
        )
    )
    health = await provider.health()
    assert health.ok
    assert health.detail["model_count"] == 1


@pytest.mark.asyncio
async def test_health_unavailable_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = make_provider(handler)
    health = await provider.health()
    assert health.status == "unavailable"


@pytest.mark.asyncio
async def test_health_error_on_401() -> None:
    provider = make_provider(lambda request: httpx.Response(401, text="no"))
    health = await provider.health()
    assert health.status == "error"


@pytest.mark.asyncio
async def test_request_contains_auth_header_and_request_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=chat_response(json.dumps({"scene_count": 1, "summary": "s"})))

    provider = make_provider(handler)
    await provider.generate_json(
        system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="req-x"
    )
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"]["request_id"] == "req-x"
    assert captured["body"]["model"] == "gemini-test"


@pytest.mark.asyncio
async def test_credentials_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, text="slow down")
        return httpx.Response(
            200, json=chat_response(json.dumps({"scene_count": 1, "summary": "ok"}))
        )

    provider = make_provider(handler)
    with caplog.at_level(logging.INFO):
        await provider.generate_json(
            system_prompt="s", user_prompt="u", schema=SCHEMA, temperature=0, request_id="req-secret"
        )
    log_text = caplog.text
    assert "test-key" not in log_text
    assert "Bearer" not in log_text
    assert "req-secret" in log_text  # request id is fine to log


@pytest.mark.asyncio
async def test_provider_is_registered_and_runtime_checkable() -> None:
    from app.providers.base import LLMProvider, ProviderRegistry

    provider = CliproxyLLMProvider(
        base_url="http://test/v1",
        api_key="test-key",
        model="gemini-test",
        max_retries=1,
        httpx_client=httpx.AsyncClient(transport=httpx.MockTransport(ok_handler(chat_response("{}"))), base_url="http://test/v1"),
    )
    assert isinstance(provider, LLMProvider)

    reg = ProviderRegistry()
    reg.register_llm("cliproxy", provider)
    assert isinstance(reg.llm("cliproxy"), CliproxyLLMProvider)


# --------------------------------------------------------------------------- #
# Integration test with the real local CLIProxy.
# --------------------------------------------------------------------------- #
@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_generate_json_with_local_cliproxy() -> None:
    """Reach the real CLIProxy service discovered in P0-T03.

    Skipped automatically when the local service is unreachable so the unit
    suite stays green on machines where CLIProxy is not running.
    """
    try:
        provider = CliproxyLLMProvider()
    except Exception:
        pytest.skip("CLIProxy unavailable")

    try:
        health = await provider.health()
    except Exception:
        await provider.aclose()
        pytest.skip("CLIProxy health probe failed")

    if not health.ok:
        await provider.aclose()
        pytest.skip(f"CLIProxy not ok: {health.detail}")

    try:
        result = await provider.generate_json(
            system_prompt="You are a storyboard planner. Return JSON only.",
            user_prompt="Plan a 2-scene storyboard for a short ad about coffee. Keep it brief.",
            schema=SCHEMA,
            temperature=0.2,
            request_id="pytest-integration-p2t02",
        )
    finally:
        await provider.aclose()

    assert isinstance(result, dict)
    assert "scene_count" in result
    assert "summary" in result
