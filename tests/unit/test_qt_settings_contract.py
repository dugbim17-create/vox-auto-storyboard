from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_settings_dialog_exposes_persisted_provider_fields() -> None:
    _app()
    from app.runtime_settings import RuntimeSettings
    from app.ui_qt.settings_dialog import SettingsDialog

    dialog = SettingsDialog(RuntimeSettings())
    try:
        for name in (
            "CliproxyBaseUrl",
            "CliproxyModel",
            "CliproxyApiKey",
            "ImageProvider",
            "FlowkitEnabled",
            "FlowkitBaseUrl",
            "OmnivoiceHost",
            "OmnivoicePort",
            "ProjectRoot",
            "SaveSettingsButton",
            "ResetSettingsButton",
            "TestProvidersButton",
        ):
            assert dialog.findChild(object, name) is not None, name
        assert dialog.cliproxy_api_key.echoMode().name == "Password"
    finally:
        dialog.close()


def test_qt_settings_save_reset_test_are_wired() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        "SettingsDialog",
        "save_runtime_settings",
        "def _open_settings",
        "def _settings_saved",
        "def _check_all_providers",
        "CliproxyImageProvider",
        "FlowKitImageProvider",
        "OmniVoiceProvider",
    ):
        assert marker in source


def test_assets_templates_controls_are_not_dead_buttons() -> None:
    source = Path("app/ui_qt/main_window.py").read_text(encoding="utf-8-sig")
    assert "AssetsButton" in source
    assert "TemplatesButton" in source
    controller = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "assets_button.clicked.connect" in controller
    assert "templates_button.clicked.connect" in controller
    assert "Chưa sẵn sàng" in controller
