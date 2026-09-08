"""Pytest configuration.

Ensures the repository root is importable so that `import app` / `import workers`
work even when the project is not installed in editable mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _isolate_default_database(tmp_path: Path, monkeypatch):
    """Prevent CLI/GUI contract tests from bootstrapping the live local DB."""
    from app.storage import database

    database.reset_engine()
    database_url = f"sqlite:///{tmp_path / 'test-session.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    database.get_engine(database_url)
    yield
    database.reset_engine()
