"""Tests for P3-T02 OmniVoice TTS adapter.

The adapter calls the OmniVoice worker over HTTP. Tests inject an
``httpx.MockTransport`` so no live worker is required. Covers the AC:

- sinh WAV tiếng Việt (adapter returns TTSResult with wav_path/duration);
- request thứ hai không reload model (worker-owned model; adapter passes
  through — verified by the worker tests + no reload call on 2nd request);
- lỗi input trả JSON rõ (HTTP 400 -> OmniVoiceInputError with detail).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.providers.base import TTSRequest
from app.providers.tts.omnivoice import (
    OmniVoiceInputError,
    OmniVoiceProvider,
    OmniVoiceUnavailable,
)


def make_provider(handler: Any) -> OmniVoiceProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://worker")
    return OmniVoiceProvider(
        base_url="http://worker", timeout_seconds=30, httpx_client=client
    )


def ok_handler() -> Any:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/synthesize"
        body = {
            "status": "ok",
            "wav_path": "C:/tmp/out.wav",
            "duration_ms": 3520,
            "sample_rate": 24000,
            "channels": 1,
            "provider": "omnivoice",
        }
        return httpx.Response(200, json=body)

    return _handler


@pytest.mark.asyncio
async def test_synthesize_returns_wav_result() -> None:
    provider = make_provider(ok_handler())
    req = TTSRequest(
        segment_id="scene_001",
        text="Xin chào Việt Nam",
        output_path="C:/tmp/out.wav",
    )
    result = await provider.synthesize(req)
    assert result.provider == "omnivoice"
    assert result.wav_path == "C:/tmp/out.wav"
    assert result.duration_ms == 3520
    assert result.sample_rate == 24000


@pytest.mark.asyncio
async def test_synthesize_preserves_measured_word_timings() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "wav_path": "C:/tmp/out.wav",
                "duration_ms": 900,
                "word_timings": [
                    {"text": "Xin", "start_ms": 100, "end_ms": 350},
                    {"text": "chào", "start_ms": 420, "end_ms": 800},
                ],
            },
        )

    provider = make_provider(handler)
    result = await provider.synthesize(
        TTSRequest(segment_id="scene_001", text="Xin chào", output_path="C:/tmp/out.wav")
    )

    assert [(word.text, word.start_ms, word.end_ms) for word in result.word_timings] == [
        ("Xin", 100, 350),
        ("chào", 420, 800),
    ]


@pytest.mark.asyncio
async def test_synthesize_sends_ref_wav() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"status": "ok", "wav_path": "x.wav", "duration_ms": 100})

    provider = make_provider(handler)
    await provider.synthesize(
        TTSRequest(
            segment_id="s1",
            text="Test",
            reference_audio_path="voices/ref.wav",
            output_path="x.wav",
        )
    )
    import json

    body = json.loads(captured["body"])
    assert body["ref_wav"] == "voices/ref.wav"
    assert body["text"] == "Test"
    assert body["language"] == "vi"


@pytest.mark.asyncio
async def test_synthesize_sends_voice_identity_and_speed() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "ok", "wav_path": "x.wav", "duration_ms": 100})

    provider = make_provider(handler)
    await provider.synthesize(
        TTSRequest(
            segment_id="s1",
            text="Test",
            voice_profile_id="voice_custom",
            seed=99,
            speed=0.8,
            provider_params={"style": "calm"},
            output_path="x.wav",
        )
    )

    assert captured["body"]["voice_profile_id"] == "voice_custom"
    assert captured["body"]["seed"] == 99
    assert captured["body"]["speed"] == 0.8
    assert captured["body"]["provider_params"] == {"style": "calm"}


@pytest.mark.asyncio
async def test_second_request_does_not_reload_model() -> None:
    # The adapter does not issue a model-load call itself; both requests hit
    # /synthesize only. Count /synthesize calls and assert no /warmup.
    calls = {"synthesize": 0, "warmup": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/warmup":
            calls["warmup"] += 1
        if request.url.path == "/synthesize":
            calls["synthesize"] += 1
        return httpx.Response(200, json={"status": "ok", "wav_path": "x.wav", "duration_ms": 100})

    provider = make_provider(handler)
    for _ in range(2):
        await provider.synthesize(TTSRequest(segment_id="s", text="Hello", output_path="x.wav"))
    assert calls["synthesize"] == 2
    assert calls["warmup"] == 0  # model is not reloaded per request


@pytest.mark.asyncio
async def test_input_error_raises_clear_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "text is empty"})

    provider = make_provider(handler)
    with pytest.raises(OmniVoiceInputError) as excinfo:
        await provider.synthesize(TTSRequest(segment_id="s", text="", output_path="x.wav"))
    assert "text is empty" in str(excinfo.value)


@pytest.mark.asyncio
async def test_worker_unreachable_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = make_provider(handler)
    with pytest.raises(OmniVoiceUnavailable):
        await provider.synthesize(TTSRequest(segment_id="s", text="Hello", output_path="x.wav"))


@pytest.mark.asyncio
async def test_health_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "model_loaded": True})

    provider = make_provider(handler)
    health = await provider.health()
    assert health.ok
    assert health.detail["model_loaded"] is True


@pytest.mark.asyncio
async def test_health_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    provider = make_provider(handler)
    health = await provider.health()
    assert health.status == "unavailable"


@pytest.mark.asyncio
async def test_warmup_calls_worker() -> None:
    captured = {"warmup": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/warmup":
            captured["warmup"] = True
            return httpx.Response(200, json={"status": "loaded"})
        return httpx.Response(404)

    provider = make_provider(handler)
    await provider.warmup()
    assert captured["warmup"] is True


@pytest.mark.asyncio
async def test_provider_is_runtime_checkable() -> None:
    from app.providers.base import TTSProvider

    provider = OmniVoiceProvider(
        base_url="http://worker",
        timeout_seconds=5,
        httpx_client=httpx.AsyncClient(
            transport=httpx.MockTransport(ok_handler()), base_url="http://worker"
        ),
    )
    assert isinstance(provider, TTSProvider)
