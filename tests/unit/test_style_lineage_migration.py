from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (  # noqa: F401
    Asset,
    Project,
    ProviderJob,
    RenderAttempt,
    Scene,
    StateEvent,
    VoiceProfile,
)
from app.services.image_generation import ImageGenerationService, RoleImageResult
from app.storage import database
from app.storage.database import Base
from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo
from app.storage.schema_migrations import LATEST_SCHEMA_VERSION, run_schema_migrations


def _legacy_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE projects (project_id VARCHAR(64) PRIMARY KEY, title VARCHAR(255), status VARCHAR(32));
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id VARCHAR(64) NOT NULL,
            scene_id VARCHAR(64) NOT NULL,
            asset_id VARCHAR(64) NOT NULL,
            role VARCHAR(32), path VARCHAR(512), alpha BOOLEAN NOT NULL DEFAULT 0,
            provider VARCHAR(32), provider_task_id VARCHAR(128) NOT NULL DEFAULT '',
            prompt_hash VARCHAR(64), sha256 VARCHAR(64), width INTEGER, height INTEGER,
            version INTEGER, selected BOOLEAN, created_at DATETIME
        );
        INSERT INTO projects(project_id, title, status) VALUES ('p1', 'Legacy', 'INGESTED');
        INSERT INTO assets(project_id, scene_id, asset_id, role, path, provider, prompt_hash, sha256, version, selected)
        VALUES ('p1', 's1', 's1_composite_v001', 'composite', 'old.jpg', 'legacy', 'old', 'abc', 1, 1);
        """
    )
    connection.commit()
    connection.close()


def test_migration_upgrades_legacy_database_and_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _legacy_db(db)
    first = run_schema_migrations(db)
    second = run_schema_migrations(db)

    connection = sqlite3.connect(db)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(assets)")}
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    quick = connection.execute("PRAGMA quick_check").fetchone()[0]
    row = connection.execute(
        "SELECT visual_style_hash, model, cache_identity FROM assets WHERE asset_id='s1_composite_v001'"
    ).fetchone()
    connection.close()

    assert {"visual_style_hash", "model", "cache_identity"} <= columns
    assert version == LATEST_SCHEMA_VERSION
    assert quick == "ok"
    assert row == (None, "", "")
    assert first.changed is True
    assert second.changed is False


def test_bootstrap_runs_migration_before_orm_queries(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _legacy_db(db)
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            row = session.query(Asset).filter_by(asset_id="s1_composite_v001").one()
            assert row.visual_style_hash is None
            assert row.model == ""
            assert row.cache_identity == ""
    finally:
        database.reset_engine()


def test_failed_migration_restores_original_database(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _legacy_db(db)
    before = db.read_bytes()

    import app.storage.schema_migrations as migrations

    original_add_column = migrations._add_column
    calls = {"count": 0}

    def fail_after_first(connection, table, column, declaration):
        original_add_column(connection, table, column, declaration)
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("injected migration failure")

    monkeypatch.setattr(migrations, "_add_column", fail_after_first)
    with pytest.raises(RuntimeError, match="injected migration failure"):
        migrations.run_schema_migrations(db)
    assert db.read_bytes() == before


def test_recovery_copy_can_restore_pre_migration_database(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    backup = tmp_path / "legacy.backup.db"
    _legacy_db(db)
    shutil.copy2(db, backup)
    run_schema_migrations(db)
    shutil.copy2(backup, db)
    connection = sqlite3.connect(db)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert "cache_identity" not in {
            row[1] for row in connection.execute("PRAGMA table_info(assets)")
        }
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_image_persistence_uses_full_cache_identity(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1")
        SceneRepo.add(session, "p1", scene_id="s1", order=1)
        service = ImageGenerationService(object(), project_root=tmp_path)
        first = RoleImageResult(
            project_id="p1",
            scene_id="s1",
            role="composite",
            path="a.jpg",
            provider="cliproxy_image",
            prompt_hash="cache-A",
            sha256="a",
            width=8,
            height=8,
            version=1,
            cached=False,
            visual_style_hash="style-A",
            model="m1",
            cache_identity="identity-A",
        )
        second = RoleImageResult(
            project_id="p1",
            scene_id="s1",
            role="composite",
            path="b.jpg",
            provider="cliproxy_image",
            prompt_hash="cache-B",
            sha256="b",
            width=8,
            height=8,
            version=2,
            cached=False,
            visual_style_hash="style-B",
            model="m1",
            cache_identity="identity-B",
        )
        service._persist_asset(session, first)  # noqa: SLF001
        service._persist_asset(session, second)  # noqa: SLF001
        session.commit()
        assets = AssetRepo.list(session, "p1", "s1")
    assert len(assets) == 2
    assert {asset.cache_identity for asset in assets} == {"identity-A", "identity-B"}
    assert {asset.visual_style_hash for asset in assets} == {"style-A", "style-B"}


def test_same_cache_identity_upserts_without_duplicate(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ProjectRepo.create(session, project_id="p1")
        SceneRepo.add(session, "p1", scene_id="s1", order=1)
        service = ImageGenerationService(object(), project_root=tmp_path)
        result = RoleImageResult(
            project_id="p1",
            scene_id="s1",
            role="composite",
            path="a.jpg",
            provider="cliproxy_image",
            prompt_hash="cache-A",
            sha256="a",
            width=8,
            height=8,
            version=1,
            cached=True,
            visual_style_hash="style-A",
            model="m1",
            cache_identity="identity-A",
        )
        service._persist_asset(session, result)  # noqa: SLF001
        service._persist_asset(session, result)  # noqa: SLF001
        session.commit()
        assets = AssetRepo.list(session, "p1", "s1")
    assert len(assets) == 1
    assert assets[0].cache_identity == "identity-A"
