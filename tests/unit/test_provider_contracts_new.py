from __future__ import annotations

import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.providers.base import ImageGenerationRequest
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.providers.image.flowkit import FlowKitImageProvider


def _png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (12, 9), (20, 100, 200)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_cliproxy_image_uses_openai_compatible_contract(tmp_path) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"data": [{"b64_json": _png_b64()}]})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://proxy.test"
    )
    provider = CliproxyImageProvider(
        base_url="http://proxy.test/v1",
        model="gpt-image-2",
        api_key="test-key",
        httpx_client=client,
    )
    out = tmp_path / "image.png"
    result = await provider.generate(
        ImageGenerationRequest(prompt="a test image", role="background", output_path=str(out))
    )
    assert seen["path"] == "/v1/images/generations"
    assert seen["body"]["model"] == "gpt-image-2"  # type: ignore[index]
    assert result.provider == "cliproxy_image"
    assert result.width == 12
    assert result.height == 9
    assert out.is_file()
    await provider.aclose()


@pytest.mark.asyncio
async def test_flowkit_health_and_submit_poll_download_contract(tmp_path) -> None:
    calls: list[str] = []
    payload = _png_b64()

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/generate":
            return httpx.Response(200, json={"job_id": "job-1", "status": "queued"})
        if request.url.path == "/jobs/job-1":
            return httpx.Response(200, json={"status": "completed", "image_base64": payload})
        return httpx.Response(404, json={"detail": "missing"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://flow.test"
    )
    provider = FlowKitImageProvider(
        base_url="http://flow.test",
        health_path="/health",
        submit_path="/generate",
        status_path_template="/jobs/{job_id}",
        httpx_client=client,
        poll_interval_seconds=0,
    )
    assert (await provider.health()).status == "ok"
    out = tmp_path / "flow.png"
    result = await provider.generate(
        ImageGenerationRequest(prompt="flow image", role="subject", output_path=str(out))
    )
    assert result.provider == "flowkit"
    assert out.is_file()
    assert calls == ["/health", "/generate", "/jobs/job-1"]
    await provider.aclose()
