"""SQLAlchemy engine, session factory, and schema bootstrap (P1-T02).

SQLite is the local MVP store. The schema is created idempotently on first
use. All models live in ``app.models`` and are registered here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config as _discovery


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _resolve_sqlite_path(database_url: str) -> str:
    """Expand a ``sqlite:///./data/app.db`` URL to an absolute path.

    Windows-safe: creates the parent directory and converts to an absolute
    file path so the engine never writes relative to an unexpected cwd.
    """
    if not database_url.startswith("sqlite:///"):
        return database_url
    raw = database_url[len("sqlite:///") :]
    path = Path(raw)
    if not path.is_absolute():
        path = _discovery.REPO_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_engine(database_url: str | None = None) -> Engine:
    global _engine
    if _engine is None:
        url = database_url or _discovery.get("DATABASE_URL")
        resolved = _resolve_sqlite_path(url)
        if resolved.startswith("sqlite:///"):
            from app.storage.schema_migrations import run_schema_migrations

            run_schema_migrations(resolved[len("sqlite:///") :])
        engine = create_engine(
            resolved,
            connect_args={"check_same_thread": False},
            future=True,
        )
        # SQLite does not enforce foreign keys by default; turn them on per
        # connection so referential integrity (and rollback tests) hold.
        if engine.dialect.name == "sqlite":

            @event.listens_for(engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _engine = engine

    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=engine or get_engine(),
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


def init_schema(engine: Engine | None = None) -> None:
    """Create all tables idempotently."""
    from app.models import (  # noqa: F401  (register models)
        asset,
        project,
        quiz_project,
        scene,
        state,
    )

    Base.metadata.create_all(bind=engine or get_engine())


def create_session() -> Any:
    """Open a session bound to the configured engine."""
    from sqlalchemy.orm import Session

    factory = get_session_factory()
    session: Session = factory()
    return session


def reset_engine() -> None:
    """Drop engine/session cache (used in tests)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
