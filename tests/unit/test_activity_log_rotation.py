from __future__ import annotations

from app.ui_qt.activity_log import ActivityLog, redact_log_text


def test_activity_log_rotates_and_caps_message(tmp_path) -> None:
    target = tmp_path / "vox.log"
    log = ActivityLog(target, max_bytes=180, backup_count=2, max_message_chars=80)
    for index in range(10):
        log.write("INFO", "plan", f"{index}:" + "x" * 200)

    assert target.is_file()
    assert (tmp_path / "vox.log.1").is_file()
    assert len(target.read_text(encoding="utf-8").splitlines()[-1]) < 180
    assert "[TRUNCATED]" in (target.read_text(encoding="utf-8") + (tmp_path / "vox.log.1").read_text(encoding="utf-8"))


def test_redaction_covers_bearer_and_connection_strings() -> None:
    text = "Authorization: Bearer abc123 postgresql://user:pass@host/db token=xyz"
    safe = redact_log_text(text)
    assert "abc123" not in safe
    assert "user:pass" not in safe
    assert "xyz" not in safe
    assert safe.count("[REDACTED]") >= 3
