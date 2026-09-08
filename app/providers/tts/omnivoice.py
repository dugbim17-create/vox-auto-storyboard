"""OmniVoice TTS adapter (P3-T02).

Implements the ``TTSProvider`` protocol by calling the OmniVoice worker
(``workers/omnivoice_worker.main``) over HTTP. The app never imports
torch/omnivoice — the worker holds the loaded model, so :

- it synthesizes Vietnamese WAV via ``POST /synthesize``;
- the model is loaded once in the worker (singleton) and reused across
  requests (request thứ hai không reload model);
- input errors surface as clear JSON from the HTTP response / body.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ProviderHealth, TTSRequest, TTSResult, TTSWordTiming
from app.settings import get_settings

logger = logging.getLogger(__name__)


class OmniVoiceError(Exception):
    """Base error for the OmniVoice adapter."""


class OmniVoiceUnavailable(OmniVoiceError):
    """Worker unreachable or unhealthy."""


class OmniVoiceInputError(OmniVoiceError):
    """Input rejected by the worker (clear JSON error in message)."""


class OmniVoiceProvider:
    """TTS provider backed by the OmniVoice HTTP worker."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or _worker_base_url()).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.omnivoice_timeout_seconds
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds)
        )

    # ------------------------------------------------------------------ #
    # Protocol
    # ------------------------------------------------------------------ #
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize Vietnamese WAV via the worker.

        ``output_path`` is sent as an absolute path so the WAV lands where the
        orchestrator expects regardless of the worker's cwd.
        """
        out_wav = _resolve_output_path(request.output_path)
        payload = {
            "text": request.text,
            "language": request.language,
            "speed": request.speed,
            "out_wav": out_wav,
            "instruct": None,
        }
        if request.reference_audio_path:
            payload["ref_wav"] = request.reference_audio_path
        if request.provider_params:
            payload["provider_params"] = dict(request.provider_params)
        payload["voice_profile_id"] = request.voice_profile_id
        payload["seed"] = request.seed

        try:
            resp = await self._client.post(
                f"{self.base_url}/synthesize", json=payload
            )
        except httpx.TransportError as exc:
            raise OmniVoiceUnavailable(f"worker unreachable: {exc}") from exc

        if resp.status_code >= 400:
            detail = _extract_detail(resp)
            raise OmniVoiceInputError(
                f"worker rejected input (http {resp.status_code}): {detail}"
            )

        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OmniVoiceError(f"worker returned non-JSON: {exc}") from exc

        if body.get("status") != "ok" or body.get("error"):
            raise OmniVoiceError(
                body.get("error") or f"worker error: {body.get('status')}"
            )

        wav_path = body.get("wav_path") or request.output_path
        duration_ms = int(body.get("duration_ms") or 0)
        if duration_ms <= 0:
            raise OmniVoiceError("worker returned non-positive WAV duration")
        try:
            word_timings = tuple(
                TTSWordTiming(
                    text=str(item["text"]),
                    start_ms=int(item["start_ms"]),
                    end_ms=int(item["end_ms"]),
                )
                for item in (body.get("word_timings") or [])
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OmniVoiceError(f"worker returned invalid word timings: {exc}") from exc
        return TTSResult(
            wav_path=str(wav_path),
            duration_ms=duration_ms,
            sample_rate=int(body.get("sample_rate") or 24000),
            channels=int(body.get("channels") or 1),
            provider="omnivoice",
            word_timings=word_timings,
        )

    async def health(self) -> ProviderHealth:
        """Check worker health."""
        try:
            resp = await self._client.get(f"{self.base_url}/health")
        except httpx.TransportError as exc:
            return ProviderHealth(status="unavailable", detail={"error": str(exc)})
        if resp.status_code != 200:
            return ProviderHealth(status="error", detail={"error": f"http {resp.status_code}"})
        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(status="error", detail={"error": str(exc)})
        return ProviderHealth(status=body.get("status"), detail=body)

    async def warmup(self) -> None:
        """Preload the worker model (one-time)."""
        await self._client.post(f"{self.base_url}/warmup")

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> OmniVoiceProvider:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


def _worker_base_url() -> str:
    settings = get_settings()
    return f"http://{settings.omnivoice_worker_host}:{settings.omnivoice_worker_port}"


def _resolve_output_path(output_path: str) -> str:
    """Return an absolute path for the WAV output.

    Relative paths are resolved against the repository root so the result does
    not depend on the worker's current working directory (which is the tool
    root when launched via ``start_omnivoice_worker.ps1``).
    """
    if not output_path:
        return output_path
    path = Path(output_path).expanduser()
    if not path.is_absolute():
        from app import config as _discovery

        path = _discovery.REPO_ROOT / path
    return str(path)


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return str(body.get("detail") or body)
    except Exception:  # noqa: BLE001
        return resp.text[:300]
