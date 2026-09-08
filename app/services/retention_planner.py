"""Deterministic retention cadence planning and validation.

This service does not decide creative content. It creates a measurable ledger
that an AI storyboard planner must fill, preventing long editorial scenes from
passing without hook, reveal, micro changes, and major pattern interrupts.
"""

from __future__ import annotations

from dataclasses import dataclass


class RetentionPlanError(ValueError):
    """Raised when retention inputs cannot produce a valid measurable ledger."""


@dataclass(frozen=True)
class BeatWindow:
    beat_id: str
    start_ms: int
    end_ms: int
    purpose: str

    def __post_init__(self) -> None:
        if not self.beat_id.strip() or not self.purpose.strip():
            raise RetentionPlanError("beat id and purpose are required")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise RetentionPlanError("beat window must have a positive duration")


@dataclass(frozen=True)
class RetentionEvent:
    event_id: str
    kind: str
    start_ms: int
    format: str
    beat_id: str
    reason: str


@dataclass(frozen=True)
class RetentionLedger:
    scene_duration_ms: int
    events: tuple[RetentionEvent, ...]

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        hooks = [event for event in self.events if event.kind == "hook"]
        reveals = [event for event in self.events if event.kind == "reveal"]
        micros = sorted(event.start_ms for event in self.events if event.kind == "micro_change")
        interrupts = sorted(
            event.start_ms for event in self.events if event.kind == "pattern_interrupt"
        )
        if not hooks or not 0 <= hooks[0].start_ms <= 3_000:
            errors.append("hook must start within 0-3s")
        if not reveals or not 3_000 <= reveals[0].start_ms <= 8_000:
            errors.append("reveal must start within 3-8s")
        if not _cadence_is_bounded(micros, self.scene_duration_ms, 2_000, 5_000):
            errors.append("micro-change cadence must stay within 2-5s")
        if self.scene_duration_ms > 15_000 and not _cadence_is_bounded(
            interrupts, self.scene_duration_ms, 8_000, 15_000
        ):
            errors.append("pattern-interrupt cadence must stay within 8-15s")
        return tuple(errors)


class RetentionPlanner:
    MICRO_INTERVAL_MS = 3_000
    INTERRUPT_INTERVAL_MS = 10_000
    FORMATS = (
        "kinetic_typography",
        "diagram",
        "stacked_cards",
        "split_screen",
        "evidence_card",
    )

    def plan(
        self,
        *,
        scene_duration_ms: int,
        beats: tuple[BeatWindow, ...],
    ) -> RetentionLedger:
        if scene_duration_ms <= 0:
            raise RetentionPlanError("scene duration must be positive")
        if not beats:
            raise RetentionPlanError("retention planning requires semantic beats")
        if any(beat.end_ms > scene_duration_ms for beat in beats):
            raise RetentionPlanError("beat exceeds scene duration")

        hook_beat = next((beat for beat in beats if beat.purpose == "hook"), beats[0])
        reveal_beat = next(
            (beat for beat in beats if beat.purpose == "reveal"),
            beats[min(1, len(beats) - 1)],
        )
        events: list[RetentionEvent] = [
            RetentionEvent(
                "retention_hook",
                "hook",
                min(hook_beat.start_ms, 3_000),
                "full_screen_typography",
                hook_beat.beat_id,
                "establish a visible promise before the viewer can leave",
            ),
            RetentionEvent(
                "retention_reveal",
                "reveal",
                max(3_000, min(reveal_beat.start_ms, 8_000)),
                "evidence_card",
                reveal_beat.beat_id,
                "pay off or sharpen the hook",
            ),
        ]

        for index, start_ms in enumerate(
            range(2_000, scene_duration_ms, self.MICRO_INTERVAL_MS)
        ):
            beat = _beat_at(beats, start_ms)
            events.append(
                RetentionEvent(
                    f"micro_{index:03d}",
                    "micro_change",
                    start_ms,
                    self.FORMATS[index % len(self.FORMATS)],
                    beat.beat_id,
                    "refresh visual information without breaking narration",
                )
            )

        for index, start_ms in enumerate(
            range(self.INTERRUPT_INTERVAL_MS, scene_duration_ms, self.INTERRUPT_INTERVAL_MS)
        ):
            beat = _beat_at(beats, start_ms)
            events.append(
                RetentionEvent(
                    f"interrupt_{index:03d}",
                    "pattern_interrupt",
                    start_ms,
                    "comment_takeover" if beat.purpose == "social" else "split_screen",
                    beat.beat_id,
                    "major composition change resets viewer attention",
                )
            )

        ledger = RetentionLedger(
            scene_duration_ms=scene_duration_ms,
            events=tuple(sorted(events, key=lambda event: (event.start_ms, event.event_id))),
        )
        errors = ledger.validate()
        if errors:
            raise RetentionPlanError("; ".join(errors))
        return ledger


def _beat_at(beats: tuple[BeatWindow, ...], time_ms: int) -> BeatWindow:
    for beat in beats:
        if beat.start_ms <= time_ms < beat.end_ms:
            return beat
    return beats[-1]


def _cadence_is_bounded(
    times: list[int],
    duration_ms: int,
    minimum_ms: int,
    maximum_ms: int,
) -> bool:
    if not times:
        return duration_ms <= maximum_ms
    boundaries = [0, *times, duration_ms]
    gaps = [right - left for left, right in zip(boundaries, boundaries[1:], strict=False)]
    interior = [right - left for left, right in zip(times, times[1:], strict=False)]
    return max(gaps) <= maximum_ms and all(gap >= minimum_ms for gap in interior)
