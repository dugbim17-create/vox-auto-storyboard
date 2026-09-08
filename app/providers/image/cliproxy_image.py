"""OpenAI-compatible CLIProxy image provider.

The repository's discovery record documents ``POST /v1/images/generations``
with a ``{data: [{b64_json: ...}]}`` response and ``gpt-image-2``. This adapter
keeps that route separate from the Antigravity generateContent adapter.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ProviderCapabilities,
    ProviderHealth,
)
from app.runtime_settings import load_runtime_settings


class CliproxyImageError(Exception):
    """Base error for the CLIProxy image provider."""


class CliproxyImageUnavailable(CliproxyImageError):
    """The configured image endpoint cannot be reached."""


class CliproxyImageValidationError(CliproxyImageError):
    """The provider returned an unusable response."""


class CliproxyImageProvider:
    """Generate images through an OpenAI-compatible local CLIProxy route."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = load_runtime_settings()
        configured_base = (base_url or settings.cliproxy_base_url).rstrip("/")
        self.base_url = configured_base
        client_base_url = configured_base
        if httpx_client is None and configured_base.endswith("/v1"):
            client_base_url = configured_base[:-3].rstrip("/")
        self.model = model or "gpt-image-1.5"
        self.fallback_models = fallback_models or ["gpt-image-2", "gpt-image-1.5"]
        self.provider_name = "cliproxy_image"
        self.api_key = api_key if api_key is not None else settings.cliproxy_api_key
        self.timeout_seconds = timeout_seconds or settings.cliproxy_timeout_seconds
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.AsyncClient(
            base_url=client_base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
        )
        self._route_prefix = "v1/"

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not request.output_path:
            raise CliproxyImageValidationError("request.output_path is required")
        models_to_try = [self.model, *[m for m in self.fallback_models if m != self.model]]
        last_error = ""

        for candidate_model in models_to_try:
            payload: dict[str, Any] = {
                "model": candidate_model,
                "prompt": request.prompt,
                "n": request.candidate_count,
                "size": (request.provider_params or {}).get("size", "1024x1024"),
            }
            if request.negative_prompt:
                payload["prompt"] = f"{request.prompt}\n\nAvoid: {request.negative_prompt}"
            try:
                response = await self._client.post(
                    f"{self._route_prefix}images/generations",
                    json=payload,
                    headers=self._headers(),
                )
            except httpx.TransportError as exc:
                raise CliproxyImageUnavailable(str(exc)) from exc
            if response.status_code >= 400:
                last_error = f"CLIProxy image ({candidate_model}) HTTP {response.status_code}: {response.text[:300]}"
                continue
            try:
                data = response.json()
                encoded = data["data"][0]["b64_json"]
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, KeyError, IndexError, TypeError, binascii.Error) as exc:
                last_error = f"response missing valid data[0].b64_json from {candidate_model}"
                continue

            path = Path(request.output_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            width, height = _dimensions(raw)
            return ImageGenerationResult(
                path=str(path),
                provider="cliproxy_image",
                width=width,
                height=height,
                prompt_hash=hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:16],
                sha256=hashlib.sha256(raw).hexdigest(),
            )

        raise CliproxyImageValidationError(f"All candidate models failed: {last_error}")

    async def health(self) -> ProviderHealth:
        try:
            response = await self._client.get(f"{self._route_prefix}models", headers=self._headers())
        except httpx.TransportError as exc:
            return ProviderHealth("unavailable", {"error": str(exc), "base_url": self.base_url})
        if response.status_code != 200:
            return ProviderHealth("error", {"http_code": response.status_code, "base_url": self.base_url})
        try:
            models = [item.get("id") for item in response.json().get("data", [])]
        except (ValueError, AttributeError):
            return ProviderHealth("error", {"error": "invalid models response"})
        return ProviderHealth("ok", {"base_url": self.base_url, "model": self.model, "models": models, "image_model_present": self.model in models})

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_text_to_image=True,
            supports_image_to_image=False,
            supports_reference_image=False,
            supports_alpha=False,
            aspect_ratios=["1:1", "16:9", "9:16"],
            max_concurrency=1,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}


def _dimensions(raw: bytes) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as image:
            return int(image.width), int(image.height)
    except Exception:  # noqa: BLE001
        return 0, 0
