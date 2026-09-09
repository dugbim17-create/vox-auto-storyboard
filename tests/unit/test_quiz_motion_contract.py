from __future__ import annotations

import pytest

from app.services.quiz_layout_spec import resolve_layout
from app.services.quiz_motion import (
    bounded_displacement,
    motion_amplitude,
    motion_state,
    safe_motion_rect,
)


def _layout():
    return resolve_layout(
        {
            "question": "Question?",
            "choices": [{"id": "A", "text": "One"}, {"id": "B", "text": "Two"}],
        },
        "16:9",
        {"id": "clear-knowledge", "snapshot": {"spacing": {"safe_margin": 56}}},
    )


def test_motion_levels_have_ordered_reduced_amplitude() -> None:
    assert motion_amplitude("low") < motion_amplitude("medium") < motion_amplitude("high")
    assert bounded_displacement("low", 0.25)[0] < bounded_displacement("high", 0.25)[0]


def test_motion_state_is_deterministic_and_keeps_rects_safe() -> None:
    layout = _layout()
    rects = {"question": layout.question.as_tuple(), "choice_a": layout.choices[0].as_tuple()}
    first = motion_state(motion="high", time_s=0.25, layout=layout, rects=rects)
    second = motion_state(motion="high", time_s=0.25, layout=layout, rects=rects)
    assert first == second
    assert all(layout.canvas.x + layout.safe_margin <= value for value in first["rects"]["question"][:2])
    assert first["rects"]["question"][2] <= layout.canvas.right
    assert first["rects"]["question"][3] <= layout.canvas.bottom


def test_safe_motion_rect_fails_closed_when_displacement_leaves_bounds() -> None:
    layout = _layout()
    with pytest.raises(ValueError, match="safe bounds"):
        safe_motion_rect((56, 56, 1900, 1000), (100, 100), layout)


def test_invalid_motion_level_fails_closed() -> None:
    with pytest.raises(ValueError, match="invalid motion"):
        motion_amplitude("strobe")
