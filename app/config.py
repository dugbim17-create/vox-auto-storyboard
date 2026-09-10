"""Minimal .env loader and settings access (Phase 0 bootstrap).

This dependency-free module backs the Phase 0 tooling (doctor, probes). It reads
``.env`` from the repository root and falls back to defaults that mirror
``.env.example`` (placeholders included). The full Pydantic-Settings config
system arrives in P1-T01; nothing here is hard-coded in provider logic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# When frozen by PyInstaller, resolve paths relative to the EXE directory,
# not the temporary _MEIPASS extraction folder.
if getattr(sys, "frozen", False):
    REPO_ROOT = Path(sys.executable).resolve().parent
else:
    REPO_ROOT = Path(__file__).resolve().parents[1]

# Defaults mirror .env.example. Real values must come from a local `.env`
# file or the process environment — never from provider code.
_DEFAULTS: dict[str, str] = {
    "APP_ENV": "local",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8787",
    "DATABASE_URL": "sqlite:///./data/app.db",
    "PROJECT_ROOT": "./projects",
    "LOG_LEVEL": "INFO",
    "FFMPEG_BIN": "ffmpeg",
    "FFPROBE_BIN": "ffprobe",
    "CLIPROXY_BASE_URL": "http://127.0.0.1:8317/v1",
    "CLIPROXY_API_KEY": "local-placeholder",
    "CLIPROXY_MODEL": "deepseek-v4-flash",
    "CLIPROXY_TIMEOUT_SECONDS": "180",
    "FLOWKIT_BASE_URL": "http://127.0.0.1:8000",
    "FLOWKIT_WS_URL": "ws://127.0.0.1:8000/ws",
    "FLOWKIT_TIMEOUT_SECONDS": "900",
    "FLOWKIT_ENABLED": "true",
    "ANTIGRAVITY_IMAGE_BASE_URL": "http://127.0.0.1:8317",
    "ANTIGRAVITY_IMAGE_MODEL": "gemini-3.1-flash-image",
    "ANTIGRAVITY_IMAGE_ENABLED": "true",
    "OMNIVOICE_VENV_PYTHON": "C:/PATH/TO/OMNIVOICE/venv/Scripts/python.exe",
    "OMNIVOICE_WORKER_HOST": "127.0.0.1",
    "OMNIVOICE_WORKER_PORT": "8791",
    "OMNIVOICE_MODEL_PATH": "C:/PATH/TO/OMNIVOICE/MODEL",
    "OMNIVOICE_DEFAULT_LANGUAGE": "vi",
    "OMNIVOICE_TIMEOUT_SECONDS": "600",
    "DEFAULT_ASPECT_RATIO": "16:9",
    "DEFAULT_FPS": "30",
    "DEFAULT_WIDTH": "1920",
    "DEFAULT_HEIGHT": "1080",
    "DEFAULT_IMAGE_PROVIDER": "antigravity_image",
    "DEFAULT_MOTION_TIER": "local",
    "DEFAULT_STYLE_PRESET": "editorial_collage",
}

# Sentinel marking an unconfigured placeholder path in .env.example.
PLACEHOLDER_TOKEN = "C:/PATH/TO/"

# Default sentinel value for CLIPROXY_API_KEY in .env.example — means "not
# configured yet" and must be replaced either from `.env` or via discovery.
_DEFAULT_CLIPROXY_API_KEY = "local-placeholder"

# Discovery-only locations, never used to modify the installed tool.
# Points at the running CLIProxyAPI install so the client api-key can be
# loaded when `.env` does not set CLIPROXY_API_KEY (P0-T03 discovery).
_CLIPROXY_CONFIG_CANDIDATES = [
    Path(r"D:\ALL AI\VScode\CLIProxyAPI\config.yaml"),
]

# OmniVoice venv discovered in P0-T06. Used when OMNIVOICE_VENV_PYTHON is not
# set in `.env`. The worker (P3) will run with this venv's python.
_OMNIVOICE_VENV_PYTHON_CANDIDATES = [
    Path(r"D:\ALL AI\VScode\voice-clone-tool\.venv\Scripts\python.exe"),
]

_loaded: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _loaded
    if _loaded is not None:
        return _loaded
    values = dict(_DEFAULTS)
    env_path = REPO_ROOT / ".env"
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    # Discovery fallback (P0-T03): if CLIPROXY_API_KEY is unset, a path
    # placeholder, or the default sentinel, borrow the running server's key.
    api_key = values.get("CLIPROXY_API_KEY", "")
    if not api_key or is_placeholder(api_key) or api_key == _DEFAULT_CLIPROXY_API_KEY:
        discovered = _discover_cliproxy_api_key()
        if discovered:
            values["CLIPROXY_API_KEY"] = discovered
    # Discovery fallback (P0-T06): OmniVoice venv python.
    ov_py = values.get("OMNIVOICE_VENV_PYTHON", "")
    if not ov_py or is_placeholder(ov_py):
        for candidate in _OMNIVOICE_VENV_PYTHON_CANDIDATES:
            if candidate.is_file():
                values["OMNIVOICE_VENV_PYTHON"] = str(candidate)
                break
    _loaded = values
    return _loaded


def get(key: str) -> str:
    """Return a setting, preferring the process environment over `.env`."""
    return os.environ.get(key, _load().get(key, ""))


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(get(key))
    except (TypeError, ValueError):
        return default


def get_bool(key: str, default: bool = False) -> bool:
    value = get(key).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def is_placeholder(value: str) -> bool:
    """True when a configured path still carries the .env.example sentinel."""
    return PLACEHOLDER_TOKEN in value


def _discover_cliproxy_api_key() -> str:
    """Read the CLIProxy client api-key from its config.yaml (discovery only).

    P0-T03 found the running server authenticates clients with the api-key
    declared in its own ``config.yaml``. We read it at init when ``.env`` does
    not override it. The key is never written to logs or this module's memory
    beyond the settings value.
    """
    for candidate in _CLIPROXY_CONFIG_CANDIDATES:
        if not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        in_api_keys = False
        for line in lines:
            stripped = line.strip()
            if stripped == "api-keys:":
                in_api_keys = True
                continue
            if in_api_keys and stripped.startswith("- "):
                raw = stripped[2:].strip()
                # Strip surrounding single/double quotes and trailing comments.
                if len(raw) >= 2 and raw[0] in ("'", '"') and raw[-1] == raw[0]:
                    raw = raw[1:-1]
                if raw:
                    return raw
            elif in_api_keys and line and not line[0].isspace():
                break
    return ""
