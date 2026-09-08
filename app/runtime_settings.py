"""User-editable runtime settings for the native Vox Studio desktop app.

This layer is intentionally separate from ``.env`` discovery: the desktop
product needs a visible, persisted configuration surface while the CLI and
existing web compatibility mode continue to use their current settings.
Secrets are stored only when the user explicitly saves them and are masked in
all diagnostic representations.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

_ALLOWED_IMAGE_PROVIDERS = {"auto", "flowkit", "cliproxy_image", "antigravity_image"}


@dataclass
class RuntimeSettings:
    # LLM / planner
    cliproxy_base_url: str = "http://127.0.0.1:8317/v1"
    cliproxy_model: str = "gemini-3.6-flash-high"
    cliproxy_api_key: str = ""
    cliproxy_timeout_seconds: int = 180

    # Image providers
    image_provider: str = "auto"
    flowkit_enabled: bool = False
    flowkit_base_url: str = "http://127.0.0.1:8000"
    flowkit_health_path: str = "/health"
    flowkit_submit_path: str = "/generate"
    flowkit_status_path_template: str = "/jobs/{job_id}"
    flowkit_result_path_template: str = ""
    flowkit_token: str = ""
    flowkit_timeout_seconds: int = 900
    flowkit_poll_interval_seconds: float = 1.0

    antigravity_image_enabled: bool = True
    antigravity_image_base_url: str = "http://127.0.0.1:8317"
    antigravity_image_model: str = "gemini-3.1-flash-image"

    # TTS worker
    omnivoice_worker_host: str = "127.0.0.1"
    omnivoice_worker_port: int = 8791
    omnivoice_timeout_seconds: int = 600
    voice_profile_id: str = "voice_vi_01"

    # Workspace / render defaults
    project_root: str = ""
    default_aspect_ratio: str = "16:9"
    default_fps: int = 30

    def __post_init__(self) -> None:
        if self.image_provider not in _ALLOWED_IMAGE_PROVIDERS:
            self.image_provider = "auto"
        self.cliproxy_timeout_seconds = max(1, int(self.cliproxy_timeout_seconds))
        self.flowkit_timeout_seconds = max(1, int(self.flowkit_timeout_seconds))
        self.flowkit_poll_interval_seconds = max(0.0, float(self.flowkit_poll_interval_seconds))
        self.omnivoice_timeout_seconds = max(1, int(self.omnivoice_timeout_seconds))
        self.omnivoice_worker_port = max(1, min(65535, int(self.omnivoice_worker_port)))
        self.default_fps = max(1, int(self.default_fps))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeSettings:
        allowed = {item.name for item in fields(cls)}
        values = {key: value for key, value in data.items() if key in allowed}
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def redacted_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        for key in ("cliproxy_api_key", "flowkit_token"):
            if data.get(key):
                data[key] = "<redacted>"
        return data


def default_data_root() -> Path:
    override = os.environ.get("VOX_STUDIO_DATA_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    if getattr(sys, "frozen", False):
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        if local_appdata:
            return Path(local_appdata) / "VoxStudio"
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "VoxStudio"
    return Path.home() / ".voxstudio"


def default_settings_path() -> Path:
    override = os.environ.get("VOX_STUDIO_SETTINGS_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return default_data_root() / "config" / "settings.json"


def load_runtime_settings(path: str | Path | None = None) -> RuntimeSettings:
    target = Path(path) if path is not None else default_settings_path()
    if not target.is_file():
        return RuntimeSettings()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RuntimeSettings()
    return RuntimeSettings.from_dict(payload) if isinstance(payload, dict) else RuntimeSettings()


def save_runtime_settings(settings: RuntimeSettings, path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else default_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(settings.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, target)
    except BaseException:
        with suppress(OSError):
            os.unlink(temp_name)
        raise
    return target


def resolve_effective_image_provider(
    settings: RuntimeSettings,
    statuses: dict[str, str],
) -> str | None:
    """Resolve the first generation-capable image provider truthfully."""
    healthy = {name for name, status in statuses.items() if status == "ok"}
    requested = settings.image_provider
    if requested != "auto" and requested in healthy:
        return requested
    for candidate in ("cliproxy_image", "antigravity_image", "flowkit"):
        if candidate == "flowkit" and not settings.flowkit_enabled:
            continue
        if candidate in healthy:
            return candidate
    return None


__all__ = [
    "RuntimeSettings",
    "default_data_root",
    "default_settings_path",
    "load_runtime_settings",
    "resolve_effective_image_provider",
    "save_runtime_settings",
]
