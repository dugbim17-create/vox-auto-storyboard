from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_activity_log_persists_and_redacts_secrets(tmp_path: Path) -> None:
    from app.ui_qt.activity_log import ActivityLog

    target = tmp_path / "vox-studio.log"
    log = ActivityLog(target)
    line = log.write(
        "ERROR",
        "generate_images",
        "Authorization: Bearer super-secret-token api_key=abc123",
    )
    persisted = target.read_text(encoding="utf-8")
    assert "super-secret-token" not in line
    assert "abc123" not in line
    assert "[REDACTED]" in persisted
    assert "generate_images" in persisted


def test_qt_has_visible_logs_page_with_friendly_and_technical_views() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "LogsPage",
            "FriendlyLog",
            "TechnicalLog",
            "ClearLogsButton",
            "OpenLogFolderButton",
        ):
            assert window.findChild(object, name) is not None, name
        assert "logs" in window.nav_buttons
    finally:
        window.close()


def test_worker_bridge_has_start_heartbeat_done_and_error_logging() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        "activity = Signal",
        "heartbeat",
        "START",
        "DONE",
        "ERROR",
        "append_activity_log",
        'nav_buttons["logs"].clicked.connect',
    ):
        assert marker in source


def test_image_generation_logs_selected_asset_and_preview_path() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "validate_image_generation_readback" in source
    assert "selected_asset_id" in source
    assert "selected_path" in source
    assert "preview" in source.lower()
