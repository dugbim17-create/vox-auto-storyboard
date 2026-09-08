"""Pydantic-Settings configuration system (P1-T01).

Loads configuration from the environment and a local ``.env`` file, with
sensible defaults mirroring ``.env.example``. Secrets are redacted from
``.env``/``__str__`` so they never reach logs. Discovery results from Phase 0
(CLIProxy key, OmniVoice venv) are used as fallbacks so the pipeline works
without editing ``.env``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import config as _discovery


class Settings(BaseSettings):
    """Application configuration.

    All values are read from environment variables or ``.env``. Nothing is
    hard-coded in provider code; the defaults below mirror ``.env.example``.
    """

    model_config = SettingsConfigDict(
        env_file=str(
            Path(getattr(sys, "_MEIPASS", _discovery.REPO_ROOT)) / ".env"
            if getattr(sys, "frozen", False)
            else _discovery.REPO_ROOT / ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- core ---
    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8787
    database_url: str = "sqlite:///./data/app.db"
    project_root: str = "./projects"
    log_level: str = "INFO"

    # --- media ---
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    # --- LLM (CLIProxy) ---
    cliproxy_base_url: str = "http://127.0.0.1:8317/v1"
    cliproxy_api_key: str = "local-placeholder"
    cliproxy_model: str = "gemini-3.6-flash-high"
    cliproxy_timeout_seconds: int = 180

    # --- image providers ---
    flowkit_base_url: str = "http://127.0.0.1:8000"
    flowkit_ws_url: str = "ws://127.0.0.1:8000/ws"
    flowkit_timeout_seconds: int = 900
    flowkit_enabled: bool = False  # NOT installed (P0-T04); CLIProxy is primary

    antigravity_image_base_url: str = "http://127.0.0.1:8317"
    antigravity_image_model: str = "gemini-3.1-flash-image"
    antigravity_image_enabled: bool = True

    # --- TTS (OmniVoice) ---
    omnivoice_venv_python: str = "C:/PATH/TO/OMNIVOICE/venv/Scripts/python.exe"
    omnivoice_worker_host: str = "127.0.0.1"
    omnivoice_worker_port: int = 8791
    omnivoice_model_path: str = "C:/PATH/TO/OMNIVOICE/MODEL"
    omnivoice_default_language: str = "vi"
    omnivoice_timeout_seconds: int = 600

    # --- render defaults ---
    default_aspect_ratio: str = "16:9"
    default_fps: int = 30
    default_width: int = 1920
    default_height: int = 1080
    # Canonical provider id for the live discovered image route. ``cliproxy``
    # remains a legacy alias resolved at the provider boundary.
    default_image_provider: str = "antigravity_image"
    default_motion_tier: str = "local"
    default_style_preset: str = "editorial_collage"

    # --- secrets mask ---
    _SECRET_FIELDS = frozenset({"cliproxy_api_key"})

    @field_validator("cliproxy_api_key", mode="after")
    @classmethod
    def _apply_discovered_cliproxy_key(cls, value: str) -> str:
        """Fall back to the running server's key when the default sentinel is set."""
        if not value or value == "local-placeholder" or _discovery.is_placeholder(value):
            discovered = _discovery._discover_cliproxy_api_key()
            if discovered:
                return discovered
        return value

    @field_validator("omnivoice_venv_python", mode="after")
    @classmethod
    def _apply_discovered_omnivoice_python(cls, value: str) -> str:
        """Fall back to the discovered venv python when the path is a placeholder."""
        if not value or _discovery.is_placeholder(value):
            for candidate in _discovery._OMNIVOICE_VENV_PYTHON_CANDIDATES:
                if candidate.is_file():
                    return str(candidate)
        return value

    @field_validator("project_root", mode="after")
    @classmethod
    def _validate_project_root(cls, value: str) -> str:
        """Resolve the project root to an absolute Windows path and ensure it exists."""
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = _discovery.REPO_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @model_validator(mode="after")
    def _resolve_media_paths(self) -> Settings:
        """Turn bare ffmpeg/ffprobe names into absolute paths when available."""
        import shutil

        for attr in ("ffmpeg_bin", "ffprobe_bin"):
            value = getattr(self, attr)
            if value and not Path(value).is_file():
                found = shutil.which(str(value))
                if found:
                    setattr(self, attr, found)
        return self

    def redacted_dict(self) -> dict[str, Any]:
        """Return config as a dict with secrets masked for safe logging."""
        out: dict[str, Any] = {}
        for key, value in self.model_dump().items():
            if key in self._SECRET_FIELDS:
                out[key] = "<redacted>" if value else ""
            else:
                out[key] = value
        return out

    def __str__(self) -> str:  # pragma: no cover - safety net
        return f"Settings(redacted={sorted(self.redacted_dict().keys())})"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton accessor."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
