from __future__ import annotations

from pathlib import Path

from app.storage import database


def test_default_database_engine_is_test_isolated(tmp_path: Path) -> None:
    engine_path = Path(database.get_engine().url.database or "").resolve()

    assert tmp_path.resolve() in engine_path.parents
    assert engine_path.name == "test-session.db"
