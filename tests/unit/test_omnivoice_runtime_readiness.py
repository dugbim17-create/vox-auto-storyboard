from __future__ import annotations

from app.tooling import doctor


def test_doctor_prefers_live_worker_health_over_placeholder_python(monkeypatch) -> None:
    monkeypatch.setattr(
        doctor,
        "_http_get_json",
        lambda url, timeout, headers=None: (
            200,
            {"status": "ok", "model_loaded": True},
        ),
    )
    monkeypatch.setattr(
        doctor.config,
        "get",
        lambda key, *args, **kwargs: {
            "OMNIVOICE_WORKER_HOST": "127.0.0.1",
            "OMNIVOICE_WORKER_PORT": "8791",
            "OMNIVOICE_VENV_PYTHON": "C:/PATH/TO/OMNIVOICE/venv/Scripts/python.exe",
        }.get(key, ""),
    )

    result = doctor.check_omnivoice()

    assert result.status == "ok"
    assert result.detail["model_loaded"] is True
    assert "worker" in result.message.lower()


def test_doctor_reports_worker_unavailable_not_python_ok(monkeypatch, tmp_path) -> None:
    py = tmp_path / "python.exe"
    py.write_bytes(b"")
    monkeypatch.setattr(doctor, "_run_cmd", lambda cmd: (0, "Python 3.11.9"))
    monkeypatch.setattr(
        doctor,
        "_http_get_json",
        lambda url, timeout, headers=None: (-1, {"error": "connection refused"}),
    )
    monkeypatch.setattr(
        doctor.config,
        "get",
        lambda key, *args, **kwargs: {
            "OMNIVOICE_WORKER_HOST": "127.0.0.1",
            "OMNIVOICE_WORKER_PORT": "8791",
            "OMNIVOICE_VENV_PYTHON": str(py),
        }.get(key, ""),
    )

    result = doctor.check_omnivoice()

    assert result.status == "error"
    assert "worker" in result.message.lower()
    assert result.detail["health_url"].endswith("/health")
