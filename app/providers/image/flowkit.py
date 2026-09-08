"""Configurable FlowKit image adapter.

FlowKit was not found during discovery, so the exact local API is configured
through the native Settings dialog instead of being guessed in code. The
adapter implements the documented health -> submit -> poll -> result contract
and fails with actionable errors when the service is absent.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import time
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


class FlowKitError(Exception):
    """Base FlowKit adapter error."""


class FlowKitUnavailable(FlowKitError):
    """FlowKit is not reachable or is not enabled."""


class FlowKitTimeout(FlowKitError):
    """A FlowKit job did not finish before timeout."""


class FlowKitValidationError(FlowKitError):
    """FlowKit returned an invalid job/result payload."""


class FlowKitImageProvider:
    """Submit and poll one FlowKit image job at a time."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        health_path: str | None = None,
        submit_path: str | None = None,
        status_path_template: str | None = None,
        result_path_template: str | None = None,
        token: str | None = None,
        timeout_seconds: float | None = None,
        poll_interval_seconds: float | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = load_runtime_settings()
        self.base_url = (base_url or settings.flowkit_base_url).rstrip("/")
        self.provider_name = "flowkit"
        self.health_path = health_path or settings.flowkit_health_path
        self.submit_path = submit_path or settings.flowkit_submit_path
        self.status_path_template = status_path_template or settings.flowkit_status_path_template
        self.result_path_template = result_path_template or settings.flowkit_result_path_template
        self.token = token if token is not None else settings.flowkit_token
        self.timeout_seconds = timeout_seconds or settings.flowkit_timeout_seconds
        self.poll_interval_seconds = settings.flowkit_poll_interval_seconds if poll_interval_seconds is None else poll_interval_seconds
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
        )

    async def health(self) -> ProviderHealth:
        try:
            response = await self._client.get(self.health_path, headers=self._headers())
        except httpx.TransportError as exc:
            return ProviderHealth("unavailable", {"base_url": self.base_url, "error": str(exc)})
        if response.status_code >= 400:
            return ProviderHealth("error", {"base_url": self.base_url, "http_code": response.status_code, "body": response.text[:300]})
        return ProviderHealth("ok", {"base_url": self.base_url, "path": self.health_path, "http_code": response.status_code})

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not request.output_path:
            raise FlowKitValidationError("request.output_path is required")
        payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "role": request.role,
            "reference_images": request.reference_images,
            "aspect_ratio": request.aspect_ratio,
            "seed": request.seed,
            "candidate_count": request.candidate_count,
            "provider_params": request.provider_params,
        }
        try:
            submitted = await self._client.post(self.submit_path, json=payload, headers=self._headers())
        except httpx.TransportError as exc:
            raise FlowKitUnavailable(f"FlowKit submit unreachable: {exc}") from exc
        if submitted.status_code >= 400:
            raise FlowKitUnavailable(f"FlowKit submit HTTP {submitted.status_code}: {submitted.text[:300]}")
        body = _json_or_error(submitted, "submit")
        if body.get("status") in {"completed", "succeeded", "success"}:
            return await self._materialize(body, request)
        job_id = body.get("job_id") or body.get("task_id") or body.get("id")
        if not job_id:
            raise FlowKitValidationError("FlowKit submit response has no job_id/task_id/id")
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            await _sleep(self.poll_interval_seconds)
            status = await self._poll(str(job_id))
            state = str(status.get("status") or status.get("state") or "").lower()
            if state in {"completed", "succeeded", "success", "done"}:
                return await self._materialize(status, request)
            if state in {"failed", "error", "cancelled", "canceled"}:
                raise FlowKitError(str(status.get("error") or f"FlowKit job {job_id} ended {state}"))
        raise FlowKitTimeout(f"FlowKit job {job_id} timed out after {self.timeout_seconds}s")

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_text_to_image=True,
            supports_image_to_image=True,
            supports_reference_image=True,
            supports_alpha=False,
            aspect_ratios=["1:1", "16:9", "9:16"],
            max_concurrency=1,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _poll(self, job_id: str) -> dict[str, Any]:
        path = self.status_path_template.format(job_id=job_id)
        try:
            response = await self._client.get(path, headers=self._headers())
        except httpx.TransportError as exc:
            raise FlowKitUnavailable(f"FlowKit poll unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise FlowKitUnavailable(f"FlowKit poll HTTP {response.status_code}: {response.text[:300]}")
        return _json_or_error(response, "poll")

    async def _materialize(self, body: dict[str, Any], request: ImageGenerationRequest) -> ImageGenerationResult:
        raw = _extract_image_bytes(body)
        if raw is None:
            result_path = body.get("result_path") or body.get("output_path") or body.get("file_path")
            if result_path:
                source = Path(str(result_path))
                if source.is_file():
                    raw = source.read_bytes()
        if raw is None and body.get("result_url"):
            response = await self._client.get(str(body["result_url"]), headers=self._headers())
            if response.status_code < 400:
                raw = response.content
        if not raw:
            raise FlowKitValidationError("FlowKit completed without image data/path/url")
        output = Path(request.output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw)
        width, height = _dimensions(raw)
        return ImageGenerationResult(
            path=str(output),
            provider="flowkit",
            provider_task_id=str(body.get("job_id") or body.get("task_id") or body.get("id") or ""),
            width=width,
            height=height,
            prompt_hash=hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:16],
            sha256=hashlib.sha256(raw).hexdigest(),
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}


def _json_or_error(response: httpx.Response, stage: str) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise FlowKitValidationError(f"FlowKit {stage} returned non-JSON") from exc
    if not isinstance(body, dict):
        raise FlowKitValidationError(f"FlowKit {stage} returned a non-object JSON payload")
    return body


def _extract_image_bytes(body: dict[str, Any]) -> bytes | None:
    candidates = [body.get("image_base64"), body.get("b64_json"), body.get("data")]
    data = next((item for item in candidates if isinstance(item, str) and item), None)
    if data:
        try:
            return base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise FlowKitValidationError("FlowKit image_base64 is invalid") from exc
    return None


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def _dimensions(raw: bytes) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as image:
            return int(image.width), int(image.height)
    except Exception:  # noqa: BLE001
        return 0, 0


def export_google_flow_batch_prompts(
    prompts: list[str],
    output_file: str | Path,
    *,
    universal_video_prompt: str = (
        "Cinematic documentary slow push-in, layered paper cutout collage, pushpin attaches "
        "photograph to board, translucent tape holds edges, realistic parallax camera drift, "
        "12fps tactile stop-motion cadence, subtle paper texture vibration, dramatic studio spotlight, ultra-realistic"
    ),
) -> Path:
    """Export formatted batch prompts ready for Google Flow Agent Mode and Zappy Flow."""
    out = Path(output_file).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# === GOOGLE FLOW BATCH PROMPTS ===",
        "# Instructions: In Google Flow Agent Mode, paste these prompts to generate all images.",
        f"# Universal Video Prompt: {universal_video_prompt}",
        "",
    ]
    for idx, p in enumerate(prompts, start=1):
        lines.append(f"Prompt {idx:02d}: {p.strip()}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
