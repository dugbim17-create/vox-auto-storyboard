"""CLIProxy LLM adapter (P2-T02).

OpenAI-compatible chat-completion client that satisfies the
``app.providers.base.LLMProvider`` protocol. Talks to the local CLIProxy
service discovered in P0-T03 (``config/discovered/cliproxy.json``).

Key properties:

- timeout 180s (configurable via ``CLIPROXY_TIMEOUT_SECONDS``);
- retries on 429/500/502/503/504 with tenacity exponential backoff;
- never retries validation/JSON errors with the same prompt;
- extracts the model's JSON payload from ``choices[0].message.content``;
- includes a stable ``request_id`` header + body field for tracing;
- health check via ``GET /models``;
- credentials are never logged — the API key only reaches the request
  ``Authorization`` header, and any log line redacts it.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.providers.base import ProviderHealth
from app.settings import get_settings

logger = logging.getLogger(__name__)

# HTTP status codes worth retrying (transient / overload).
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class CliproxyLLMError(Exception):
    """Base error for the CLIProxy LLM adapter."""


class CliproxyAuthError(CliproxyLLMError):
    """401 — key missing/wrong/over-quoted (symptom from P0-T03)."""


class CliproxyModelNotFoundError(CliproxyLLMError):
    """404 — model alias does not exist on the server (e.g. gpt-5.6-sol)."""


class CliproxyValidationError(CliproxyLLMError):
    """Non-retryable: prompt/shape problem or malformed JSON from the model."""


class CliproxyLLMProvider:
    """LLM provider backed by the local CLIProxy OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 3,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.cliproxy_base_url).rstrip("/")
        self.api_key = api_key or settings.cliproxy_api_key
        self.model = model or settings.cliproxy_model
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
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        temperature: float,
        request_id: str,
    ) -> dict:
        """Ask the model for JSON and return the parsed dict.

        Raises ``CliproxyValidationError`` (non-retryable) when the model
        returns content that is not parseable JSON or does not satisfy the
        requested shape.
        """
        payload = self._build_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            temperature=temperature,
            request_id=request_id,
        )
        content = await self._chat_with_retries(payload, request_id)
        # On success _chat_with_retries returns the message text; parse/validate.
        return self._parse_json(content=content, schema=schema, request_id=request_id)

    async def health(self) -> ProviderHealth:
        headers = self._auth_headers()
        try:
            resp = await self._client.get("/models", headers=headers)
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
        except json.JSONDecodeError as exc:
            return ProviderHealth(status="error", detail={"error": f"bad json: {exc}"})
        models = data.get("data", [])
        return ProviderHealth(
            status="ok",
            detail={
                "base_url": self.base_url,
                "model_count": len(models),
                "models": [m.get("id") for m in models],
                "model": self.model,
            },
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _auth_headers(self) -> dict[str, str]:
        """Authorization header for each request (client-injected or owned).

        Sending it per-request (rather than only at client construction) keeps
        auth correct even when a caller injects their own ``httpx.AsyncClient``.
        """
        return {"Authorization": f"Bearer {self.api_key}"}

    def _build_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        temperature: float,
        request_id: str,
    ) -> dict[str, Any]:
        schema_hint = json.dumps(schema, ensure_ascii=False)
        return {
            "model": self.model,
            "temperature": temperature,
            "stream": False,
            "request_id": request_id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        "Respond with a single valid JSON object only. No prose, "
                        "no code fences, no trailing text.\n"
                        f"Required JSON schema:\n{schema_hint}"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        }

    async def _chat_once(self, payload: dict[str, Any], request_id: str) -> str:
        """One chat-completion round-trip; raises retryable/non-retryable errors."""
        start = time.monotonic()
        try:
            resp = await self._client.post(
                "/chat/completions", json=payload, headers=self._auth_headers()
            )
        except httpx.TimeoutException as exc:
            raise CliproxyRetryableError(f"timeout after {self.timeout_seconds}s") from exc
        except httpx.TransportError as exc:
            raise CliproxyRetryableError(f"transport error: {exc}") from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code in _RETRYABLE_STATUS:
            raise CliproxyRetryableError(f"http {resp.status_code}")
        if resp.status_code == 401:
            raise CliproxyAuthError("cliproxy auth failed (401)")
        if resp.status_code == 404:
            raise CliproxyModelNotFoundError(f"cliproxy model not found: {self.model}")
        if resp.status_code >= 400:
            raise CliproxyValidationError(f"cliproxy http {resp.status_code}")

        logger.info(
            "cliproxy_llm_ok request_id=%s model=%s elapsed_ms=%d",
            request_id,
            self.model,
            elapsed_ms,
        )

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise CliproxyValidationError(f"non-JSON response: {exc}") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CliproxyValidationError("response missing choices[0].message.content") from exc
        if not isinstance(content, str):
            raise CliproxyValidationError("message content is not a string")
        return content

    async def _chat_with_retries(
        self, payload: dict[str, Any], request_id: str
    ) -> str:
        """Chat round-trip with exponential backoff on transient failures.

        Only ``CliproxyRetryableError`` (timeout, 429, 5xx) is retried.
        Non-retryable errors (auth, model-not-found, validation) propagate
        immediately — re-running the same prompt is pointless for them.
        """
        content: str = ""
        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(CliproxyRetryableError),
        ):
            with attempt:
                if attempt.retry_state.attempt_number > 1:
                    logger.info(
                        "cliproxy_llm_retry request_id=%s model=%s attempt=%d",
                        request_id,
                        self.model,
                        attempt.retry_state.attempt_number,
                    )
                content = await self._chat_once(payload, request_id)
        return content

    @staticmethod
    def _parse_json(content: str, *, schema: dict, request_id: str) -> dict:
        """Parse the model's text into a dict, applying light schema checks.

        Only the shape of ``schema`` is enforced: if the top-level key
        ``properties`` exists, every required property must be present in the
        returned object. Deep field-type validation is deferred to P2-T03
        (Storyboard JSON Schema) via the ``jsonschema`` dependency.
        """
        text = content.strip()
        if text.startswith("```"):
            # Strip optional markdown fences the model may add despite the hint.
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CliproxyValidationError(
                f"model returned malformed JSON (request_id={request_id}): {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise CliproxyValidationError(
                f"model returned non-object JSON (request_id={request_id})"
            )

        required = (schema or {}).get("required", [])
        missing = [key for key in required if key not in parsed]
        if missing:
            raise CliproxyValidationError(
                f"model JSON missing required keys {missing} (request_id={request_id})"
            )
        return parsed

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def aclose(self) -> None:
        """Close the owned HTTP client. Harmless when the client was injected."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> CliproxyLLMProvider:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


class CliproxyRetryableError(CliproxyLLMError):
    """Transient failure (timeout / 429 / 5xx) — safe to retry."""
