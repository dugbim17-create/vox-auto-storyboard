"""Idempotent, restorable SQLite schema upgrades before ORM use."""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

LATEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MigrationResult:
    path: str
    from_version: int
    to_version: int
    changed: bool


def run_schema_migrations(path: str | Path) -> MigrationResult:
    target = Path(path)
    if not target.is_file():
        return MigrationResult(str(target), 0, 0, False)

    connection = sqlite3.connect(target)
    try:
        before = int(connection.execute("PRAGMA user_version").fetchone()[0])
        needs_v1 = _table_exists(connection, "assets") and (
            before < 1
            or not {"visual_style_hash", "model", "cache_identity"}
            <= _column_names(connection, "assets")
        )
    finally:
        connection.close()
    if not needs_v1:
        return MigrationResult(str(target), before, before, False)

    backup = target.with_name(f".{target.name}.migration-{uuid.uuid4().hex}.bak")
    shutil.copy2(target, backup)
    connection = sqlite3.connect(target, isolation_level=None)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        _add_column(connection, "assets", "visual_style_hash", "VARCHAR(64)")
        _add_column(connection, "assets", "model", "VARCHAR(128) NOT NULL DEFAULT ''")
        _add_column(connection, "assets", "cache_identity", "VARCHAR(64) NOT NULL DEFAULT ''")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_assets_cache_identity ON assets(cache_identity)"
        )
        connection.execute(f"PRAGMA user_version={LATEST_SCHEMA_VERSION}")
        check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"SQLite quick_check failed after migration: {check}")
        connection.execute("COMMIT")
    except BaseException:
        with suppress(sqlite3.Error):
            connection.execute("ROLLBACK")
        connection.close()
        shutil.copy2(backup, target)
        backup.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        backup.unlink(missing_ok=True)
    return MigrationResult(str(target), before, LATEST_SCHEMA_VERSION, True)


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _add_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    if column in _column_names(connection, table):
        return
    connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {declaration}')


__all__ = ["LATEST_SCHEMA_VERSION", "MigrationResult", "run_schema_migrations"]
