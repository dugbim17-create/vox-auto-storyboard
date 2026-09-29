"""OmniVoice TTS worker (P3-T01).

A standalone FastAPI worker that runs under the OmniVoice venv (which has torch
+ CUDA). The main application never imports torch/omnivoice (its venv torch is
broken); instead it calls this worker over HTTP.

Endpoints:
- ``GET /health``      -> ``{status: "ok"}`` when the app is up
- ``POST /warmup``     -> loads the model once, ``{status: "loaded"}``
- ``POST /synthesize`` -> synthesize Vietnamese WAV via ``synth.synthesize``

The model is loaded exactly once and kept alive between requests (P3-T02: model
chỉ load một lần, request thứ hai không reload model).

Run from the tool root so ``import synth`` resolves::

    cd <tool_root>
    <tool_root>/.venv/Scripts/python.exe -m uvicorn workers.omnivoice_worker.main:app \\
        --host 127.0.0.1 --port 8791

(Start with the project root on sys.path, or copy this package under the tool
root. The launcher script handles this.)
"""

from __future__ import annotations

raise RuntimeError("OmniVoice retired. This worker is disabled; use VieNeu CPU/GPU or Piper.")

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# The worker runs with the tool root as cwd so ``import synth`` resolves.
# Guard so type-checkers/imports elsewhere don't crash.
try:
    import synth  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - only when cwd is wrong
    synth = None  # type: ignore[assignment]

app = FastAPI(title="OmniVoice TTS Worker")

# Model is loaded lazily once via synth._get_model()'s singleton; we track the
# loaded flag for the /health + /warmup contract.
_MODEL_LOADED = False


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    ref_wav: str = ""
    language: str = "vi"
    speed: float = 1.0
    out_wav: str = "output.wav"
    instruct: str | None = None
    voice_profile_id: str = "voice_vi_01"
    seed: int = 42
    provider_params: dict[str, Any] = Field(default_factory=dict)


class SynthesizeResponse(BaseModel):
    status: str = "ok"
    wav_path: str = ""
    duration_ms: int = 0
    sample_rate: int = 24000
    channels: int = 1
    provider: str = "omnivoice"
    error: str = ""


def _load_model() -> None:
    """Trigger OmniVoice model load. synth caches the model (singleton), so the
    second+ calls are cheap and do not reload."""
    global _MODEL_LOADED
    if synth is None:
        return
    model = synth._get_model()  # type: ignore[union-attr]
    _MODEL_LOADED = model is not None


def _resolve_reference_for_profile(profile_id: str, explicit_ref: str) -> str:
    """Resolve a catalog voice id to a reference WAV when supplied."""
    if explicit_ref:
        return explicit_ref
    if not profile_id:
        return _resolve_first_ref()
    candidate = _tool_root() / "out" / "export" / "samples" / f"{profile_id}.wav"
    return str(candidate) if candidate.is_file() else _resolve_first_ref()


@app.get("/health")
async def health() -> dict[str, Any]:
    if synth is None:
        return {"status": "error", "detail": "synth module not importable (wrong cwd)"}
    return {"status": "ok", "model_loaded": _MODEL_LOADED}


@app.get("/voices")
async def voices() -> dict[str, Any]:
    """Expose discovered voice profiles without loading model weights."""
    samples = []
    samples_dir = _tool_root() / "out" / "export" / "samples"
    if samples_dir.is_dir():
        samples = [
            {"voice_profile_id": path.stem, "reference_audio_path": str(path)}
            for path in sorted(samples_dir.glob("*.wav"))
        ]
    return {"status": "ok", "voices": samples}


@app.post("/warmup")
async def warmup() -> dict[str, Any]:
    if synth is None:
        raise HTTPException(status_code=500, detail="synth module not importable")
    try:
        _load_model()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"model failed to load: {exc}") from exc
    if not _MODEL_LOADED:
        raise HTTPException(status_code=500, detail="model failed to load")
    return {"status": "loaded", "model_loaded": True}


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest) -> SynthesizeResponse:
    if synth is None:
        raise HTTPException(status_code=500, detail="synth module not importable")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is empty")

    ref = _resolve_reference_for_profile(req.voice_profile_id, req.ref_wav)
    try:
        _load_model()
    except Exception as exc:  # noqa: BLE001
        return SynthesizeResponse(wav_path="", provider="omnivoice", error=f"model load failed: {exc}")

    out = Path(req.out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    synth_kwargs: dict[str, Any] = {
        "text": req.text,
        "out_wav": str(out),
        "language": req.language,
        "instruct": req.instruct,
        "speed": req.speed,
    }
    if ref:
        synth_kwargs["ref_wav"] = ref
    try:
        path, _ = synth.synthesize(**synth_kwargs)
    except Exception as exc:  # noqa: BLE001
        return SynthesizeResponse(wav_path="", provider="omnivoice", error=str(exc))

    duration_ms = _probe_duration(Path(path))
    return SynthesizeResponse(
        wav_path=str(path),
        duration_ms=duration_ms,
        sample_rate=24000,
        channels=1,
        provider="omnivoice",
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _resolve_first_ref() -> str:
    """Pick the first available reference sample from the discovered samples dir."""
    candidates = [
        _tool_root() / "out" / "export" / "samples",
    ]
    for directory in candidates:
        if not directory.is_dir():
            continue
        files = sorted(directory.glob("*.wav"))
        if files:
            return str(files[0])
    return ""


def _tool_root() -> Path:
    return Path(os.environ.get("OMNIVOICE_TOOL_ROOT", str(Path.cwd())))


def _probe_duration(path: Path) -> int:
    """Best-effort WAV duration in ms from the header size (24kHz mono pcm)."""
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    # RIFF fmt: compute from data chunk length / bytes-per-second.
    if len(data) < 44 or data[0:4] != b"RIFF":
        return 0
    try:
        sample_rate = int.from_bytes(data[24:28], "little")
        channels = int.from_bytes(data[22:24], "little")
        bits = int.from_bytes(data[34:36], "little")
        data_size = int.from_bytes(data[40:44], "little")
    except Exception:  # noqa: BLE001
        return 0
    bytes_per_sec = sample_rate * channels * (bits // 8)
    if bytes_per_sec <= 0:
        return 0
    return int(data_size / bytes_per_sec * 1000)


# --------------------------------------------------------------------------- #
# Launch helper
# --------------------------------------------------------------------------- #
def main() -> None:  # pragma: no cover - manual entry
    import uvicorn

    port = int(os.environ.get("OMNIVOICE_WORKER_PORT", "8791"))
    host = os.environ.get("OMNIVOICE_WORKER_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
