"""Durable, rotating, secret-safe activity log for the native Qt app."""

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://)([^\s/@:]+):([^\s/@]+)@"),
)


def redact_log_text(value: object) -> str:
    text = str(value)
    text = _SECRET_PATTERNS[0].sub(r"\1[REDACTED]", text)
    text = _SECRET_PATTERNS[1].sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _SECRET_PATTERNS[2].sub(r"\1[REDACTED]@", text)
    return text


class ActivityLog:
    """Append timestamped lines with bounded size and retained backups."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 3,
        max_message_chars: int = 4_000,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max(128, int(max_bytes))
        self.backup_count = max(0, int(backup_count))
        self.max_message_chars = max(64, int(max_message_chars))
        self._lock = threading.Lock()

    def write(self, level: str, action: str, message: object) -> str:
        safe_action = redact_log_text(action).strip() or "unknown"
        safe_message = redact_log_text(message).replace("\r", " ").replace("\n", " ")
        if len(safe_message) > self.max_message_chars:
            safe_message = safe_message[: self.max_message_chars] + " … [TRUNCATED]"
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        line = f"{timestamp} [{level.upper()}] [{safe_action}] {safe_message}"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            incoming = len((line + "\n").encode("utf-8"))
            if self.path.is_file() and self.path.stat().st_size + incoming > self.max_bytes:
                self._rotate()
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
        return line

    def read(self, *, max_chars: int = 200_000) -> str:
        if not self.path.is_file():
            return ""
        text = self.path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]

    def _rotate(self) -> None:
        if self.backup_count <= 0:
            self.path.unlink(missing_ok=True)
            return
        oldest = self.path.with_name(f"{self.path.name}.{self.backup_count}")
        oldest.unlink(missing_ok=True)
        for index in range(self.backup_count - 1, 0, -1):
            src = self.path.with_name(f"{self.path.name}.{index}")
            dst = self.path.with_name(f"{self.path.name}.{index + 1}")
            if src.exists():
                src.replace(dst)
        if self.path.exists():
            self.path.replace(self.path.with_name(f"{self.path.name}.1"))


__all__ = ["ActivityLog", "redact_log_text"]
