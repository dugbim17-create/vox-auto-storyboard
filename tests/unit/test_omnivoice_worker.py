"""Tests for P3-T01 OmniVoice worker skeleton.

The worker is a FastAPI app that runs under the OmniVoice venv (torch + CUDA).
The project venv cannot import ``torch``/``synth``, so in tests we monkeypatch
``workers.omnivoice_worker.main.synth`` with a fake that exposes
``synthesize`` and ``_get_model``. This verifies the HTTP contract
(/health, /warmup, /synthesize) without needing the real model.

The acceptance criteria are: ``GET /health = ok`` and ``POST /warmup = loaded``.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from workers.omnivoice_worker import main as worker
from workers.omnivoice_worker.main import app


class FakeSynth:
    """Duck-typed stand-in for the tool-root ``synth`` module."""

    def __init__(self) -> None:
        self.calls = 0
        self.model_loads = 0

    def _get_model(self, *args: Any, **kwargs: Any) -> object:
        self.model_loads += 1
        return object()  # non-None model

    def synthesize(self, text, ref_wav=None, out_wav="output.wav",
                   language=None, instruct=None, speed=1.0, duration=None):
        self.calls += 1
        path = Path(out_wav)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_minimal_wav(path)
        return path, "omnivoice"


def _write_minimal_wav(path: Path) -> None:
    """Write a tiny but structurally valid 24kHz mono 16-bit WAV."""
    sample_rate = 24000
    bits = 16
    channels = 1
    block_align = channels * bits // 8
    byte_rate = sample_rate * block_align
    data_size = 100 * block_align
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE" + b"fmt "
    header += struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
    header += b"data" + struct.pack("<I", data_size)
    path.write_bytes(header + b"\x00\x00" * 100)


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """TestClient with ``synth`` faked so the worker import doesn't crash."""
    fake = FakeSynth()
    monkeypatch.setattr(worker, "synth", fake)
    monkeypatch.setattr(worker, "_MODEL_LOADED", False)
    return TestClient(app)


def test_health_ok(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is False


def test_voices_endpoint(client, tmp_path: Path, monkeypatch) -> None:
    samples = tmp_path / "out" / "export" / "samples"
    samples.mkdir(parents=True)
    _write_minimal_wav(samples / "voice_a.wav")
    monkeypatch.setenv("OMNIVOICE_TOOL_ROOT", str(tmp_path))

    resp = client.get("/voices")

    assert resp.status_code == 200
    assert resp.json()["voices"][0]["voice_profile_id"] == "voice_a"


def test_warmup_loads_model(client) -> None:
    resp = client.post("/warmup")
    assert resp.status_code == 200
    assert resp.json()["status"] == "loaded"
    # After warmup, health reflects loaded.
    health = client.get("/health").json()
    assert health["model_loaded"] is True


def test_health_ok_after_warmup(client) -> None:
    client.post("/warmup")
    resp = client.get("/health")
    assert resp.json()["model_loaded"] is True


def test_synthesize_returns_wav(client, tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    resp = client.post("/synthesize", json={"text": "Xin chào Việt Nam", "out_wav": str(out)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert out.exists()
    assert body["wav_path"] == str(out)
    assert body["provider"] == "omnivoice"
    assert body["sample_rate"] == 24000


def test_synthesize_resolves_voice_profile_reference(client, tmp_path: Path, monkeypatch) -> None:
    samples = tmp_path / "out" / "export" / "samples"
    samples.mkdir(parents=True)
    ref = samples / "voice_custom.wav"
    _write_minimal_wav(ref)
    monkeypatch.setenv("OMNIVOICE_TOOL_ROOT", str(tmp_path))
    captured: dict[str, Any] = {}

    class CapturingSynth(FakeSynth):
        def synthesize(self, **kwargs: Any):
            captured.update(kwargs)
            return super().synthesize(**kwargs)

    monkeypatch.setattr(worker, "synth", CapturingSynth())
    response = TestClient(app).post(
        "/synthesize",
        json={
            "text": "Xin chào",
            "voice_profile_id": "voice_custom",
            "out_wav": str(tmp_path / "x.wav"),
        },
    )
    assert response.status_code == 200
    assert captured["ref_wav"] == str(ref)


def test_synthesize_empty_text_400(client) -> None:
    resp = client.post("/synthesize", json={"text": "   "})
    assert resp.status_code == 400


def test_synthesize_model_load_error_is_clean_json(client, monkeypatch) -> None:
    # Even when the model fails to load, the worker returns a JSON error body.
    def boom(*args: Any, **kwargs: Any):
        raise RuntimeError("cuda out of memory")

    fake = FakeSynth()
    fake._get_model = boom
    monkeypatch.setattr(worker, "synth", fake)
    c = TestClient(app)
    resp = c.post("/synthesize", json={"text": "Xin chào"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "cuda out of memory" in resp.json()["error"]
