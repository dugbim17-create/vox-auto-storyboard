from __future__ import annotations

import json
from pathlib import Path

from app.schemas.quiz import approve_quiz_project, validate_quiz_project
from app.services.quiz_research import verify_question_bank

BANK = Path("presets/quiz_30_vi_verified.json")


def test_verified_thirty_question_bank_is_source_backed_and_approvable() -> None:
    payload = json.loads(BANK.read_text(encoding="utf-8"))
    questions = payload["questions"]

    assert len(questions) == 30
    assert [q["question_id"] for q in questions] == [f"q{i:03d}" for i in range(1, 31)]
    assert [q["order"] for q in questions] == list(range(1, 31))
    assert all(isinstance(q["fact_sources"][0], dict) for q in questions)
    assert all(q["fact_sources"][0]["authority"] == "official" for q in questions)
    assert all("local_fixture:" not in json.dumps(q) for q in questions)

    verified = verify_question_bank(questions, target_count=30)
    assert len(verified.selected) == 30
    project = validate_quiz_project(
        {
            "schema_version": "quiz_project_v1",
            "project_id": "quiz_scale_30_001",
            "title": "Quiz kiến thức Việt Nam — 30 câu",
            "topic": "Kiến thức Việt Nam",
            "language": "vi",
            "target_question_count": 30,
            "question_count": 30,
            "seconds_per_question": 10,
            "theme_id": "vox_quiz_01",
            "questions": verified.selected,
            "intro": {"title": "THỬ THÁCH 30 CÂU", "subtitle": "Kiến thức Việt Nam"},
            "outro": {"title": "HOÀN THÀNH", "cta": "Bạn đúng bao nhiêu câu?"},
        }
    )
    approved = approve_quiz_project(project, approved_at="2026-08-10T00:00:00Z")
    assert approved["approval"]["status"] == "approved"
    assert len(approved["approval"]["content_fingerprint"]) == 64
    assert {q["content_fingerprint"] for q in approved["questions"]} == {
        approved["approval"]["content_fingerprint"]
    }
