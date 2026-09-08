import asyncio

import pytest
from PIL import Image

from app.services import quiz_asset_resolver as resolver


def test_reveal_request_carries_slot_size_and_rejects_wrong_result(tmp_path, monkeypatch):
    requests = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        async def generate(self, request):
            requests.append(request)
            Image.new('RGB', (200, 400), 'red').save(request.output_path)

        async def aclose(self):
            pass

    monkeypatch.setattr(resolver, 'CliproxyImageProvider', Provider)
    with pytest.raises(ValueError, match='ratio'):
        asyncio.run(resolver.generate_quiz_image('Eiffel tower', tmp_path / 'reveal.png'))
    assert requests[0].provider_params['size'] == '1536x1024'
    assert requests[0].aspect_ratio == '3:2'
    assert not (tmp_path / 'reveal.png').exists()


def test_shared_fit_preserves_portrait_and_bounds_ultrawide():
    from app.services.quiz_image_layout import image_slot, fitted_size
    slot = image_slot('reveal', '9:16')
    assert slot.box == (120, 500, 960, 980)
    assert fitted_size((1122, 1402), slot.size) == (384, 480)
    assert fitted_size((4000, 400), slot.size) == (840, 84)


def test_existing_reveal_gets_explicit_adaptive_contract(tmp_path):
    path = tmp_path / 'portrait.png'
    Image.new('RGB', (400, 500), 'red').save(path)
    question = {'id': 'q', 'question': 'City?', 'choices': [
        {'id': 'A', 'text': 'Paris'}, {'id': 'B', 'text': 'Rome'}],
        'correct_id': 'A', 'reveal_image_path': str(path)}
    result = asyncio.run(resolver.resolve_quiz_assets([question], tmp_path))[0]
    assert result['reveal_image_layout']['fit'] == 'contain-adaptive'
    assert result['reveal_image_layout']['source_size'] == [400, 500]
    assert 'reveal_image_layout' not in question
    assert result['reveal_image_path'] == str(path)


@pytest.mark.parametrize('aspect', ['16:9', '9:16'])
@pytest.mark.parametrize('size', [(400, 500), (3000, 300), (900, 600)])
def test_actual_reveal_pixels_stay_inside_slot(tmp_path, aspect, size):
    from PIL import ImageDraw
    import numpy as np
    from app.services.quiz_engine_v2 import QuizVideoEngineV2, QuizRenderOptions
    from app.services.quiz_image_layout import image_slot
    path = tmp_path / 'hero.png'
    Image.new('RGBA', size, (255, 0, 255, 255)).save(path)
    engine = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio=aspect))
    canvas = Image.new('RGBA', (engine.width, engine.height), 'black')
    engine._paste_reveal_slot(canvas, ImageDraw.Draw(canvas), path, aspect)
    pixels = np.asarray(canvas)
    ys, xs = np.where(np.all(pixels[:, :, :3] == (255, 0, 255), axis=2))
    x0, y0, x1, y1 = image_slot('reveal', aspect).box
    assert x0 <= xs.min() <= xs.max() < x1
    assert y0 <= ys.min() <= ys.max() < y1
    assert abs((xs.max()-xs.min()+1)/(ys.max()-ys.min()+1)-size[0]/size[1]) < .02
    if aspect == '9:16' and size == (400, 500):
        assert canvas.getpixel((110, 600))[:3] == (0, 0, 0), 'No oversized mat'
