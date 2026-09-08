import json
import pytest
from PIL import Image
from app.ui_qt.quiz_json_dialog import SAMPLE_RIDDLE_JSON
from app.services.quiz_v2_contract import validate_questions


def test_invalid_riddle_answer():
    q = json.loads(SAMPLE_RIDDLE_JSON)
    q[0]['correct_option'] = '99'
    with pytest.raises(ValueError, match='riddle'):
        validate_questions(q)


def test_real_image_acceptance_and_corruption(tmp_path):
    q = json.loads(SAMPLE_RIDDLE_JSON)
    image = tmp_path / 'scene.png'
    Image.new('RGB', (1920, 1080), 'white').save(image)
    q[0]['scene_image'] = str(image)
    validate_questions(q, require_assets=True)
    image.write_bytes(b'corrupt image')
    with pytest.raises(ValueError, match='asset'):
        validate_questions(q, require_assets=True)
