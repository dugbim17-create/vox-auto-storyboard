"""Native PySide6 runtime settings dialog for Vox Studio."""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.runtime_settings import RuntimeSettings


class SettingsDialog(QDialog):
    """Edit persisted provider/workspace settings without exposing secrets."""

    saved = Signal(object)
    test_requested = Signal(object)

    def __init__(self, settings: RuntimeSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt Vox Studio")
        self.setObjectName("SettingsDialog")
        self.resize(720, 560)
        self._settings = settings
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_ai_tab(), "AI / Hình ảnh")
        tabs.addTab(self._build_voice_tab(), "Voice")
        tabs.addTab(self._build_workspace_tab(), "Workspace")
        root.addWidget(tabs, 1)
        buttons = QHBoxLayout()
        self.test_providers_button = QPushButton("Kiểm tra providers")
        self.test_providers_button.setObjectName("TestProvidersButton")
        self.reset_settings_button = QPushButton("Khôi phục mặc định")
        self.reset_settings_button.setObjectName("ResetSettingsButton")
        self.save_settings_button = QPushButton("Lưu cài đặt")
        self.save_settings_button.setObjectName("SaveSettingsButton")
        self.save_settings_button.setProperty("kind", "primary")
        buttons.addWidget(self.test_providers_button)
        buttons.addStretch(1)
        buttons.addWidget(self.reset_settings_button)
        buttons.addWidget(self.save_settings_button)
        root.addLayout(buttons)
        self.reset_settings_button.clicked.connect(self._reset)
        self.save_settings_button.clicked.connect(self._save)
        self.test_providers_button.clicked.connect(self._test)
        self._load(settings)

    def _build_ai_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.cliproxy_base_url = QLineEdit()
        self.cliproxy_base_url.setObjectName("CliproxyBaseUrl")
        form.addRow("CLIProxy Base URL", self.cliproxy_base_url)
        self.cliproxy_model = QLineEdit()
        self.cliproxy_model.setObjectName("CliproxyModel")
        form.addRow("CLIProxy model", self.cliproxy_model)
        self.cliproxy_api_key = QLineEdit()
        self.cliproxy_api_key.setObjectName("CliproxyApiKey")
        self.cliproxy_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("CLIProxy API key", self.cliproxy_api_key)
        self.image_provider = QComboBox()
        self.image_provider.setObjectName("ImageProvider")
        self.image_provider.addItems(
            ["auto", "cliproxy_image", "flowkit", "antigravity_image"]
        )
        form.addRow("Image provider", self.image_provider)
        self.flowkit_enabled = QCheckBox("Bật FlowKit")
        self.flowkit_enabled.setObjectName("FlowkitEnabled")
        form.addRow("", self.flowkit_enabled)
        self.flowkit_base_url = QLineEdit()
        self.flowkit_base_url.setObjectName("FlowkitBaseUrl")
        form.addRow("FlowKit Base URL", self.flowkit_base_url)
        return page

    def _build_voice_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.omnivoice_host = QLineEdit()
        self.omnivoice_host.setObjectName("OmnivoiceHost")
        form.addRow("OmniVoice host", self.omnivoice_host)
        self.omnivoice_port = QSpinBox()
        self.omnivoice_port.setObjectName("OmnivoicePort")
        self.omnivoice_port.setRange(1, 65535)
        form.addRow("OmniVoice port", self.omnivoice_port)
        self.voice_profile = QLineEdit()
        self.voice_profile.setObjectName("DefaultVoiceProfile")
        form.addRow("Voice profile mặc định", self.voice_profile)
        return page

    def _build_workspace_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.project_root = QLineEdit()
        self.project_root.setObjectName("ProjectRoot")
        form.addRow("Project root", self.project_root)
        self.default_aspect_ratio = QComboBox()
        self.default_aspect_ratio.setObjectName("DefaultAspectRatio")
        self.default_aspect_ratio.addItems(["16:9", "9:16"])
        form.addRow("Tỷ lệ mặc định", self.default_aspect_ratio)
        self.default_fps = QSpinBox()
        self.default_fps.setObjectName("DefaultFps")
        self.default_fps.setRange(1, 120)
        form.addRow("FPS mặc định", self.default_fps)
        return page

    def _load(self, settings: RuntimeSettings) -> None:
        self._settings = settings
        self.cliproxy_base_url.setText(settings.cliproxy_base_url)
        self.cliproxy_model.setText(settings.cliproxy_model)
        self.cliproxy_api_key.setText(settings.cliproxy_api_key)
        self.image_provider.setCurrentText(settings.image_provider)
        self.flowkit_enabled.setChecked(settings.flowkit_enabled)
        self.flowkit_base_url.setText(settings.flowkit_base_url)
        self.omnivoice_host.setText(settings.omnivoice_worker_host)
        self.omnivoice_port.setValue(settings.omnivoice_worker_port)
        self.voice_profile.setText(settings.voice_profile_id)
        self.project_root.setText(settings.project_root)
        self.default_aspect_ratio.setCurrentText(settings.default_aspect_ratio)
        self.default_fps.setValue(settings.default_fps)

    def values(self) -> RuntimeSettings:
        data = self._settings.to_dict()
        data.update(
            {
                "cliproxy_base_url": self.cliproxy_base_url.text().strip(),
                "cliproxy_model": self.cliproxy_model.text().strip(),
                "cliproxy_api_key": self.cliproxy_api_key.text(),
                "image_provider": self.image_provider.currentText(),
                "flowkit_enabled": self.flowkit_enabled.isChecked(),
                "flowkit_base_url": self.flowkit_base_url.text().strip(),
                "omnivoice_worker_host": self.omnivoice_host.text().strip(),
                "omnivoice_worker_port": self.omnivoice_port.value(),
                "voice_profile_id": self.voice_profile.text().strip(),
                "project_root": self.project_root.text().strip(),
                "default_aspect_ratio": self.default_aspect_ratio.currentText(),
                "default_fps": self.default_fps.value(),
            }
        )
        allowed = {item.name for item in fields(RuntimeSettings)}
        return RuntimeSettings.from_dict({key: value for key, value in data.items() if key in allowed})

    def _reset(self) -> None:
        self._load(RuntimeSettings())

    def _save(self) -> None:
        settings = self.values()
        self.saved.emit(settings)
        self.accept()

    def _test(self) -> None:
        self.test_providers_button.setEnabled(False)
        self.test_requested.emit(self.values())

    def set_test_complete(self) -> None:
        self.test_providers_button.setEnabled(True)


__all__ = ["SettingsDialog"]
