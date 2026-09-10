import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_de_fussball_30_v2_spec():
    json_path = ROOT / "output" / "quiz" / "de_fussball_30_v2.json"
    assert json_path.is_file(), f"Missing dataset: {json_path}"

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["language"] == "de-DE"
    assert data["market"] == "DE"
    assert data["total_questions"] == 30

    # Test intermission
    intermission = data["intermission"]
    assert intermission["type"] == "fan_duell"
    assert "WIRTZ" in intermission["question"]
    assert "MUSIALA" in intermission["question"]
    assert intermission["countdown_seconds"] == 8.0

    # Test questions structure
    questions = data["questions"]
    assert len(questions) == 30

    levels = {q["level"] for q in questions}
    assert "LEVEL 1 · WARM-UP" in levels
    assert "LEVEL 2 · DEUTSCHLAND" in levels
    assert "LEVEL 3 · EXPERT MODE" in levels
    assert "LEVEL 4 · PRO ONLY" in levels
    assert "FINAL BOSS 👑" in levels

    # Final boss check
    boss = questions[-1]
    assert boss["id"] == 30
    assert boss["answer_text"] == "LOTHAR MATTHÄUS (150 LÄNDERSPIELE)"
    assert boss["correct_id"] == "C"
    assert len(boss["career_steps"]) == 5

    for q in questions:
        assert q["id"] >= 1
        assert len(q["choices"]) == 4
        assert q["correct_id"] in {"A", "B", "C", "D"}
        assert len(q["voice_q"]) > 10
        assert len(q["voice_a"]) > 5
        assert q["countdown_seconds"] >= 5.0
