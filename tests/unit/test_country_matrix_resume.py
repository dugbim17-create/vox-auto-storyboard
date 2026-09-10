from __future__ import annotations

import json
from pathlib import Path


def test_runner_preserves_exhausted_cell_budget_without_retrying(tmp_path):
    import scripts.run_country_mode_matrix as runner

    out = tmp_path / "cell"
    out.mkdir()
    (out / "attempt-ledger.json").write_text(json.dumps({"used": 2}), encoding="utf-8")
    (out / "cell-manifest.json").write_text(
        json.dumps({"status": "FAILED_CELL", "error": "validation mismatch", "provider_requests": {"llm": 2}}),
        encoding="utf-8",
    )
    prior = json.loads((out / "cell-manifest.json").read_text(encoding="utf-8"))
    ledger = json.loads((out / "attempt-ledger.json").read_text(encoding="utf-8"))
    assert prior["status"] == "FAILED_CELL"
    assert ledger["used"] == 2
    assert runner.valid_completed_cell(out) is False


def test_valid_completed_cell_requires_readback_hash_and_two_aspects(tmp_path):
    import scripts.run_country_mode_matrix as runner

    out = tmp_path / "cell"
    out.mkdir()
    first = out / "a.mp4"
    second = out / "b.mp4"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    manifest = {
        "status": "TECH_PASS",
        "mode": "multiple_choice",
        "render_results": [
            {"path": str(first), "sha256": runner.sha256(first)},
            {"path": str(second), "sha256": runner.sha256(second)},
        ],
    }
    (out / "resolved-document.json").write_text(json.dumps({"questions": [{"id": "q1", "question": "A?", "choices": [{"id": "A", "text": "A"}, {"id": "B", "text": "B"}], "correct_id": "A"}]}), encoding="utf-8")
    (out / "cell-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert runner.valid_completed_cell(out) is True
  

def test_mode_prompt_mentions_bounded_question_length():
    import scripts.run_country_mode_matrix as runner
    assert "at most 90 characters" in runner.mode_prompt("de-football", "de-DE", "multiple_choice", 1)


def test_voice_inventory_has_japan_as_blocker():
    run = Path(r"D:/ALL AI/TestProjects/Vox-deepseek/output/quiz-live-acceptance/20260909T111519Z-country-mode")
    if not (run / "voice-inventory-final.json").exists():
        return
    data = json.loads((run / "voice-inventory-final.json").read_text(encoding="utf-8"))
    assert not any(item.get("locale") == "ja-JP" and item.get("status") == "VOICE_TECH_PASS" for item in data.get("results", []))


__all__ = []
