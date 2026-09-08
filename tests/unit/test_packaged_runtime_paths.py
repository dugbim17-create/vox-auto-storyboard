from __future__ import annotations

from pathlib import Path

from app import runtime_settings
from app.tooling import doctor


def test_packaged_data_root_uses_localappdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime_settings.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert runtime_settings.default_data_root() == tmp_path / "VoxStudio"
    assert runtime_settings.default_settings_path() == tmp_path / "VoxStudio" / "config" / "settings.json"


def test_packaged_gpu_check_is_not_required_when_torch_is_not_bundled(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "frozen", True, raising=False)
    monkeypatch.setattr(doctor, "_torch_runtime_info", lambda: None)
    result = doctor.check_gpu()
    assert result.status == "not_required"
    assert "not bundled" in result.message.lower()
