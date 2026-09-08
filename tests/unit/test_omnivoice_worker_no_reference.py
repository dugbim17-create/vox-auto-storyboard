from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from workers.omnivoice_worker import main as worker
from workers.omnivoice_worker.main import app


def test_worker_omits_ref_wav_when_no_reference_exists(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class Synth:
        @staticmethod
        def _get_model() -> object:
            return object()

        @staticmethod
        def synthesize(**kwargs: Any):
            captured.update(kwargs)
            out = Path(kwargs["out_wav"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(
                b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "
                + (16).to_bytes(4, "little")
                + (1).to_bytes(2, "little")
                + (1).to_bytes(2, "little")
                + (24000).to_bytes(4, "little")
                + (48000).to_bytes(4, "little")
                + (2).to_bytes(2, "little")
                + (16).to_bytes(2, "little")
                + b"data" + (0).to_bytes(4, "little")
            )
            return out, "omnivoice"

    monkeypatch.setattr(worker, "synth", Synth())
    monkeypatch.setenv("OMNIVOICE_TOOL_ROOT", str(tmp_path))
    out = tmp_path / "out.wav"

    response = TestClient(app).post(
        "/synthesize",
        json={"text": "Xin chào", "out_wav": str(out)},
    )

    assert response.status_code == 200
    assert response.json()["error"] == ""
    assert "ref_wav" not in captured
