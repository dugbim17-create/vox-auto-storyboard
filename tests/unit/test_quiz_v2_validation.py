import json
import pytest
from app.ui_qt.quiz_json_dialog import SAMPLE_MULTICHOICE_JSON


def test_invalid_countdown():
    from app.services.quiz_v2_contract import validate_questions
    questions = json.loads(SAMPLE_MULTICHOICE_JSON)
    questions[0]['countdown_seconds'] = -1
    with pytest.raises(ValueError, match='countdown'):
        validate_questions(questions)


@pytest.mark.parametrize('mutation', ['duplicate', 'empty_question', 'duplicate_choice', 'bad_card'])
def test_invalid_contract(mutation):
    from app.services.quiz_v2_contract import validate_questions
    q = json.loads(SAMPLE_MULTICHOICE_JSON)
    if mutation == 'duplicate':
        q.append(dict(q[0]))
    elif mutation == 'empty_question':
        q[0]['question'] = ''
    elif mutation == 'duplicate_choice':
        q[0]['choices'][1]['id'] = 'A'
    else:
        q[0]['cards'] = [{'id': '1'}]
    with pytest.raises(ValueError):
        validate_questions(q)


def test_required_image_blocks_render():
    from app.services.quiz_v2_contract import validate_questions
    q = json.loads(SAMPLE_MULTICHOICE_JSON)
    q[0]['reveal_image_path'] = 'definitely-missing-quiz-asset.jpg'
    with pytest.raises(ValueError, match='asset'):
        validate_questions(q, require_assets=True)
