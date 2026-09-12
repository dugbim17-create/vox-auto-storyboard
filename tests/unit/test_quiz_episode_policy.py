import hashlib
import pytest
from PIL import Image
from app.services.quiz_asset_policy import valid_record
from app.services.quiz_generation_budget import GenerationBudget


def test_json_reviewed_flag_is_not_proof(tmp_path):
    image = tmp_path / 'photo.png'
    Image.new('RGB', (32, 32), 'red').save(image)
    record = dict(kind='licensed', license='CC-BY-4.0', reviewed=True, author='invented', source_url='https://example.com', license_url='https://example.com', evidence_url='https://example.com', changes='none', sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    assert not valid_record(image, record)


def test_episode_budget_more_than_six_and_isolated(tmp_path):
    first = GenerationBudget(tmp_path / 'episode-a', limit=12)
    for i in range(12):
        ticket = first.reserve(str(i))
        first.complete(ticket)
    with pytest.raises(RuntimeError, match='budget'):
        GenerationBudget(tmp_path / 'episode-a', limit=12).reserve('overflow')
    second = GenerationBudget(tmp_path / 'episode-b', limit=12)
    assert second.reserve('new').exists()
