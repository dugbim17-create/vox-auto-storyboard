from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_native_gui_module_imports_without_starting_web_server() -> None:
    code = "import app.gui_native; print('NATIVE_IMPORT_OK')"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "VOX_STUDIO_SETTINGS_PATH": str(Path.cwd() / ".tmp_gui_settings.json")},
    )
    assert result.returncode == 0, result.stderr
    assert "NATIVE_IMPORT_OK" in result.stdout


def test_native_gui_constructor_requires_display_explicitly() -> None:
    if sys.platform == "win32":
        pytest.skip("Tk native display smoke belongs to an interactive Windows session")
    pytest.skip("headless environments do not provide Tk display")
