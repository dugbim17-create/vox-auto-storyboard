from __future__ import annotations

from app.services.retention_planner import BeatWindow, RetentionPlanner


def test_retention_ledger_enforces_hook_reveal_and_change_cadence() -> None:
    beats = (
        BeatWindow("beat_hook", 0, 2_500, "hook"),
        BeatWindow("beat_reveal", 2_500, 7_000, "reveal"),
        BeatWindow("beat_evidence", 7_000, 20_000, "evidence"),
    )

    ledger = RetentionPlanner().plan(scene_duration_ms=20_000, beats=beats)

    hook = next(event for event in ledger.events if event.kind == "hook")
    reveal = next(event for event in ledger.events if event.kind == "reveal")
    micro_times = [event.start_ms for event in ledger.events if event.kind == "micro_change"]
    interrupt_times = [
        event.start_ms for event in ledger.events if event.kind == "pattern_interrupt"
    ]

    assert 0 <= hook.start_ms <= 3_000
    assert 3_000 <= reveal.start_ms <= 8_000
    assert max(b - a for a, b in zip(micro_times, micro_times[1:], strict=False)) <= 5_000
    assert all(2_000 <= b - a <= 5_000 for a, b in zip(micro_times, micro_times[1:], strict=False))
    assert interrupt_times == [10_000]
    assert ledger.validate() == ()
