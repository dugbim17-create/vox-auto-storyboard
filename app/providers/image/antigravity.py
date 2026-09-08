"""Antigravity image adapter (P4-T03).

Implements the ``ImageProvider`` protocol against the CLIProxy Antigravity
text-to-image route discovered in P0-T05
(``config/discovered/antigravity.json``):

    POST {base}/v1beta/models/{model}:generateContent
    body   {"contents":[{"parts":[{"text": prompt}]}],
            "generationConfig":{"responseModalities":["IMAGE"]}}
    ->     candidates[0].content.parts[].inlineData.{data(base64), mimeType}

The model returns a fixed landscape JPEG (1408x768); aspect is NOT controllable
at the translator level, so it must be cropped/fitted later at the layer/render
stage (P5/P6). The adapter:

- sends the prompt and optional negative prompt;
- decodes the base64 payload into the request's ``output_path`` (an absolute
  path resolved against the repo root so the file always lands where expected);
- normalizes the result into ``ImageGenerationResult`` with real dimensions and
  a sha256 of the written file;
- reports health/capabilities against the live route;
- never logs credentials; the API key reaches only the ``Authorization`` header.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ProviderCapabilities,
    ProviderHealth,
)
from app.settings import get_settings

logger = logging.getLogger(__name__)

# _RETRYABLE_STATUS — keep aligned with the LLM adapter: transient overloads.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class AntigravityImageError(Exception):
    """Base error for the Antigravity image adapter."""


class AntigravityImageAuthError(AntigravityImageError):
    """401 — API key missing/wrong/over-quoted."""


class AntigravityImageNotFoundError(AntigravityImageError):
    """404 — the image model route does not exist on this server."""


class AntigravityImageValidationError(AntigravityImageError):
    """Non-retryable: bad request shape or unusable payload from the model."""


class AntigravityImageRetryableError(AntigravityImageError):
    """Transient failure (timeout / 429 / 5xx) — safe to retry."""


class AntigravityImageProvider:
    """Image provider backed by the CLIProxy Antigravity generateContent route."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 3,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.antigravity_image_base_url).rstrip("/")
        self.model = model or settings.antigravity_image_model
        self.provider_name = "antigravity_image"
        self.api_key = api_key or settings.cliproxy_api_key
        self.timeout_seconds = timeout_seconds or settings.cliproxy_timeout_seconds
        self.max_retries = max_retries
        # Ownership: caller-provided clients are not closed by this adapter.
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    # ------------------------------------------------------------------ #
    # Protocol
    # ------------------------------------------------------------------ #
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate one image and write it to ``request.output_path``.

        ``output_path`` is required: the decoded payload needs a destination.
        Raises ``AntigravityImageValidationError`` when the output path is
        missing or the model returns no usable image payload.
        """
        output_path = _resolve_output_path(request.output_path)
        if not output_path:
            raise AntigravityImageValidationError("request.output_path is required")

        payload = self._build_payload(request)
        image_bytes, _ = await self._generate_with_retries(
            payload, request=request
        )
        await self._write_image(
            output_path=output_path,
            data=image_bytes,
            request=request,
        )
        width, height = _image_dimensions(image_bytes)
        prompt_hash = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:16]
        return ImageGenerationResult(
            path=output_path,
            provider="antigravity_image",
            width=width,
            height=height,
            prompt_hash=prompt_hash,
            sha256=hashlib.sha256(image_bytes).hexdigest(),
        )

    async def health(self) -> ProviderHealth:
        """Probe the image route's /models endpoint to report availability.

        Antigravity does not expose a dedicated image health route, so we use
        the OpenAI-compatible model catalog to verify the service is up.
        """
        headers = self._auth_headers()
        try:
            resp = await self._client.get("/v1/models", headers=headers)
        except httpx.HTTPError as exc:
            return ProviderHealth(status="unavailable", detail={"error": str(exc)})
        if resp.status_code == 401:
            return ProviderHealth(status="error", detail={"error": "auth failed (401)"})
        if resp.status_code != 200:
            return ProviderHealth(
                status="error", detail={"error": f"http {resp.status_code}"}
            )
        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(status="error", detail={"error": f"bad json: {exc}"})
        models = [m.get("id") for m in data.get("data", [])]
        return ProviderHealth(
            status="ok",
            detail={
                "base_url": self.base_url,
                "model": self.model,
                "image_models": [m for m in models if "image" in str(m)],
            },
        )

    async def capabilities(self) -> ProviderCapabilities:
        """Report what this provider supports.

        Antigravity is text-to-image only: it returns a fixed landscape image,
        so it does NOT support reference images, aspect control, or alpha.
        """
        return ProviderCapabilities(
            supports_text_to_image=True,
            supports_image_to_image=False,
            supports_reference_image=False,
            supports_alpha=False,
            aspect_ratios=["16:9"],
            max_concurrency=1,
        )

    # ------------------------------------------------------------------ #
    # Request/response handling
    # ------------------------------------------------------------------ #
    def _build_payload(self, request: ImageGenerationRequest) -> dict[str, Any]:
        """Build the generateContent body (negative prompt folded into text)."""
        prompt = request.prompt
        if request.negative_prompt:
            prompt = f"{prompt}\n\nAvoid: {request.negative_prompt}"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        # Respect the fixed output size only if a provider_param asks for it;
        # the model otherwise returns its default 1408x768 landscape.
        size = (request.provider_params or {}).get("size")
        if size:
            payload["generationConfig"]["imageConfig"] = {"size": size}
        return payload

    async def _generate_with_retries(
        self,
        payload: dict[str, Any],
        *,
        request: ImageGenerationRequest,
    ) -> tuple[bytes, str]:
        """One generateContent round-trip with exponential backoff on retryable errors."""
        from tenacity import (
            AsyncRetrying,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        result: tuple[bytes, str] | None = None
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(AntigravityImageRetryableError),
        ):
            with attempt:
                if attempt.retry_state.attempt_number > 1:
                    logger.info(
                        "antigravity_image_retry model=%s role=%s attempt=%d",
                        self.model,
                        request.role,
                        attempt.retry_state.attempt_number,
                    )
                result = await self._generate_once(payload)
        assert result is not None
        return result

    async def _generate_once(
        self, payload: dict[str, Any]
    ) -> tuple[bytes, str]:
        """One POST to the generateContent route; raises typed errors."""
        import time

        headers = self._auth_headers()
        route = f"/v1beta/models/{self.model}:generateContent"
        start = time.monotonic()
        try:
            resp = await self._client.post(route, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AntigravityImageRetryableError(
                f"timeout after {self.timeout_seconds}s"
            ) from exc
        except httpx.TransportError as exc:
            raise AntigravityImageRetryableError(f"transport error: {exc}") from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code in _RETRYABLE_STATUS:
            raise AntigravityImageRetryableError(f"http {resp.status_code}")
        if resp.status_code == 401:
            raise AntigravityImageAuthError("antigravity auth failed (401)")
        if resp.status_code == 404:
            raise AntigravityImageNotFoundError(
                f"antigravity image route not found: {self.model}"
            )
        if resp.status_code >= 400:
            raise AntigravityImageValidationError(f"antigravity http {resp.status_code}")

        logger.info("antigravity_image_ok model=%s elapsed_ms=%d", self.model, elapsed_ms)

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise AntigravityImageValidationError(
                f"non-JSON response: {exc}"
            ) from exc
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AntigravityImageValidationError(
                "response missing candidates[0].content.parts"
            ) from exc
        for part in parts:
            inline = part.get("inlineData")
            if not inline:
                continue
            b64 = inline.get("data")
            mime = inline.get("mimeType", "image/jpeg")
            if b64:
                try:
                    return base64.b64decode(b64), mime
                except binascii.Error as exc:
                    raise AntigravityImageValidationError(
                        f"invalid base64 image payload: {exc}"
                    ) from exc
        raise AntigravityImageValidationError(
            "response contained no inlineData image payload"
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _write_image(
        self,
        *,
        output_path: str,
        data: bytes,
        request: ImageGenerationRequest,
    ) -> None:
        path = Path(output_path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info(
            "antigravity_image_written role=%s bytes=%d path=%s",
            request.role,
            len(data),
            output_path,
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AntigravityImageProvider:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


def _resolve_output_path(output_path: str) -> str:
    """Return an absolute path for the image output.

    Relative paths are resolved against the repository root so the result does
    not depend on the caller's cwd.
    """
    if not output_path:
        return output_path
    path = Path(output_path).expanduser()
    if not path.is_absolute():
        from app import config as _discovery

        path = _discovery.REPO_ROOT / path
    return str(path)


def _image_dimensions(data: bytes) -> tuple[int, int]:
    """Best-effort width/height from the raw image bytes.

    Only PNG/JPEG headers are inspected; anything else returns (0, 0) rather
    than raising, so a valid-but-unrecognized payload still works.
    """
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            return int(img.width), int(img.height)
    except Exception:  # noqa: BLE001
        return 0, 0
