import pytest
from app.services.quiz_engine_v2 import get_difficulty_badge


@pytest.mark.parametrize('locale', ['de', 'de-DE'])
def test_final_boss_label_does_not_require_emoji_font(locale):
    label, color = get_difficulty_badge(30, 30, locale)
    assert label == 'FINAL BOSS'
    assert color == (231, 76, 60)
