"""Unit tests for the P0-T02 system doctor.

These test the doctor contract without requiring live services:
- every check returns a CheckResult without raising;
- one failing provider does not crash the report;
- core status controls ``core_ok`` and therefore the exit code;
- the report is persisted to config/discovered/doctor_report.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tooling import doctor

# Fast, environment-independent result used to keep run_all tests hermetic.
# Network/GPU probes are patched so run_all tests never touch live services.
_GPU_OK = doctor.CheckResult(name="gpu", status="missing", message="patched")


def _patch_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "check_gpu", lambda: _GPU_OK)


def _patch_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "check_cliproxy", lambda: doctor.CheckResult(name="cliproxy", status="missing", message="patched-offline"))
    monkeypatch.setattr(doctor, "check_flowkit", lambda: doctor.CheckResult(name="flowkit", status="missing", message="patched-offline"))


def test_run_all_returns_report_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gpu(monkeypatch)
    _patch_network(monkeypatch)
    report = doctor.run_all()
    assert isinstance(report, dict)
    assert report["report_version"] == 1
    assert "checks" in report
    assert isinstance(report["checks"], list)
    assert len(report["checks"]) >= 4  # core: python, ffmpeg, ffprobe, project_dir
    # Each check has the expected shape and a valid status.
    for check in report["checks"]:
        assert check["name"]
        assert check["status"] in {"ok", "missing", "error", "placeholder"}
        assert "message" in check
        assert "elapsed_ms" in check


def test_run_all_never_raises_with_missing_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gpu(monkeypatch)

    def _boom(name: str) -> doctor.CheckResult:
        return doctor.CheckResult(name=name, status="missing", message="simulated missing")

    monkeypatch.setattr(doctor, "check_executable", _boom)
    monkeypatch.setattr(doctor, "check_cliproxy", lambda: doctor.CheckResult(name="cliproxy", status="error", message="offline"))
    monkeypatch.setattr(doctor, "check_flowkit", lambda: doctor.CheckResult(name="flowkit", status="error", message="offline"))
    report = doctor.run_all()
    assert report["core_ok"] is False  # ffmpeg/ffprobe missing -> core not ok
    assert all(c["status"] in {"ok", "missing", "error", "placeholder"} for c in report["checks"])


def test_core_ok_true_when_core_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """With healthy core and dead optional providers, core_ok stays True."""
    _patch_gpu(monkeypatch)
    _patch_network(monkeypatch)
    report = doctor.run_all()
    core_names = {"python", "ffmpeg", "ffprobe", "project_dir"}
    core_states = {c["name"]: c["status"] for c in report["checks"] if c["name"] in core_names}
    assert all(v == "ok" for v in core_states.values())
    assert report["core_ok"] is True


def test_check_python_ok() -> None:
    result = doctor.check_python()
    assert result.name == "python"
    assert result.status == "ok"
    assert "3." in str(result.detail.get("version"))


def test_check_executable_missing() -> None:
    result = doctor.check_executable("definitely_not_a_real_tool_xyz")
    assert result.name == "definitely_not_a_real_tool_xyz"
    assert result.status == "missing"


def test_check_project_dir_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point PROJECT_ROOT resolution at a tmp dir by patching the repo root
    # used by check_project_dir.
    from app import config

    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    result = doctor.check_project_dir()
    assert result.status == "ok"
    assert (tmp_path / "projects").is_dir()


def test_check_omnivoice_placeholder_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    def _get(key: str, *args: object, **kwargs: object) -> str:
        if key == "OMNIVOICE_VENV_PYTHON":
            return "C:/PATH/TO/OMNIVOICE/venv/Scripts/python.exe"
        return "x"

    monkeypatch.setattr(doctor.config, "get", _get)
    result = doctor.check_omnivoice()
    assert result.status == "placeholder"
    assert "placeholder" in result.message.lower()


def test_check_gpu_isolates_native_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken torch native lib must surface as status='error', not crash run_all."""

    def _broken_torch(*args: object, **kwargs: object) -> None:
        raise OSError("WinError 127: The specified procedure could not be found")

    monkeypatch.setattr("builtins.__import__", _broken_torch)
    result = doctor.check_gpu()
    assert result.name == "gpu"
    assert result.status == "error"
    assert "failed to load" in result.message.lower()
    assert "WinError 127" in str(result.detail.get("load_error"))


def test_write_report_persists_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_gpu(monkeypatch)
    _patch_network(monkeypatch)
    report = doctor.run_all()
    target = tmp_path / "doctor_report.json"
    doctor.write_report(report, target)
    assert target.is_file()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["report_version"] == 1
