from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from test_quiz_phase1_contract import quiz_fixture

from app.schemas.quiz import QuizValidationError, approve_quiz_project
from app.storage import database
from app.storage.repositories import QuizProjectRepo


@pytest.fixture()
def session(tmp_path: Path):
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/quiz.db")
    database.init_schema(engine)
    factory = database.get_session_factory(engine)
    with factory() as value:
        yield value
    database.reset_engine()


def test_quiz_table_is_additive_to_existing_schema(tmp_path: Path) -> None:
    database.reset_engine()
    engine = database.get_engine(f"sqlite:///{tmp_path}/schema.db")
    database.init_schema(engine)

    tables = set(inspect(engine).get_table_names())

    assert "quiz_projects" in tables
    assert "projects" in tables
    database.reset_engine()


def test_validated_quiz_round_trips_with_ledger_and_approval(session) -> None:
    approved = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")

    QuizProjectRepo.upsert(session, approved)
    session.commit()
    reloaded = QuizProjectRepo.get_document(session, approved["project_id"])

    assert reloaded == approved
    assert reloaded["questions"][0]["ledger"]["approval_status"] == "approved"


def test_upsert_replaces_same_quiz_without_duplicate_row(session) -> None:
    document = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")
    QuizProjectRepo.upsert(session, document)
    document["questions"][0]["ledger"]["status"] = "asset_ready"
    QuizProjectRepo.upsert(session, document)
    session.commit()

    from app.models.quiz_project import QuizProject

    rows = list(session.scalars(select(QuizProject)))
    assert len(rows) == 1
    assert QuizProjectRepo.get_document(session, document["project_id"])["questions"][0]["ledger"]["status"] == "asset_ready"


def test_invalid_quiz_is_rejected_before_database_write(session) -> None:
    document = quiz_fixture()
    document["questions"][0]["correct_choice_id"] = "Z"

    with pytest.raises(QuizValidationError):
        QuizProjectRepo.upsert(session, document)

    assert QuizProjectRepo.get_document(session, document["project_id"]) is None


def test_quiz_write_does_not_create_generic_project(session) -> None:
    document = approve_quiz_project(quiz_fixture(), approved_at="2026-08-10T00:00:00Z")
    QuizProjectRepo.upsert(session, document)
    session.commit()

    from app.models import Project

    assert session.get(Project, document["project_id"]) is None
