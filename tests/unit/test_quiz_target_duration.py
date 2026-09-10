from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.services.quiz_engine_v2 import QuizVideoEngineV2


def engine(target):
    result = object.__new__(QuizVideoEngineV2)
    result.opt = SimpleNamespace(target_duration_minutes=target)
    return result


def timeline():
    return ([{"type": "intro", "start": 0, "dur": 2}] +
            [{"type": "question", "idx": i, "q_dur": 3, "rev_dur": 2,
              "cd_dur": 3.5, "total_dur": 8.5} for i in range(30)] +
            [{"type": "outro", "start": 257, "dur": 3}])


def test_thirty_questions_five_minutes_preserves_speech():
    events = timeline()
    assert engine(5)._fit_target_duration(events, 260) == pytest.approx(300)
    questions = events[1:-1]
    assert len(questions) == 30
    assert all(q['q_dur'] == 3 and q['rev_dur'] == 2 for q in questions)
    assert all(2 <= q['cd_dur'] <= 10 for q in questions)
    for left, right in zip(questions, questions[1:]):
        assert left['q_start'] + left['total_dur'] == pytest.approx(right['q_start'])
    assert events[-1]['start'] + events[-1]['dur'] == pytest.approx(300)


def test_natural_unchanged():
    events = timeline()
    before = deepcopy(events)
    assert engine(None)._fit_target_duration(events, 260) == 260
    assert events == before


@pytest.mark.parametrize('target', [0, -1, float('nan'), float('inf'), 1, 60])
def test_impossible_target_leaves_events_unchanged(target):
    events = timeline()
    before = deepcopy(events)
    with pytest.raises(ValueError):
        engine(target)._fit_target_duration(events, 260)
    assert events == before
