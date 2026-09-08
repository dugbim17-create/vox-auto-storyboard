import pytest
from PIL import Image, ImageDraw
from app.services.quiz_engine_v2 import QuizVideoEngineV2, QuizRenderOptions


@pytest.mark.parametrize('aspect', ['16:9', '9:16'])
def test_badges_never_overlap_photo_and_portrait_uses_two_rows(tmp_path, aspect):
    source = tmp_path / 'image.png'
    Image.new('RGB', (400, 400), 'cyan').save(source)
    engine = QuizVideoEngineV2(QuizRenderOptions(aspect_ratio=aspect))
    canvas = Image.new('RGBA', (engine.width, engine.height))
    draw = ImageDraw.Draw(canvas)
    photos, badges = [], []
    paste, ellipse = canvas.paste, draw.ellipse
    def record_paste(image, box, *args):
        photos.append((box[0], box[1], box[0]+image.width, box[1]+image.height))
        return paste(image, box, *args)
    def record_ellipse(box, **kwargs):
        if kwargs.get('width') == 4 and box[2]-box[0] == 76:
            badges.append(box)
        return ellipse(box, **kwargs)
    canvas.paste = record_paste
    draw.ellipse = record_ellipse
    q = {'question': 'Đếm hình', 'cards': [{'id':str(i),'label':str(i),'image_path':str(source)} for i in range(1,5)], 'correct_option':'1'}
    ev = {'idx':1,'data':q,'cd_start':2,'cd_dur':5,'rev_start':7}
    engine._render_riddle_mystra(canvas,draw,1,ev,0,False,False)
    assert len(photos)==len(badges)==4
    for photo, badge in zip(photos,badges):
        assert badge[3] < photo[1], 'Badge must sit above the image, never over a clue'
    if aspect=='9:16':
        assert photos[2][1] > photos[0][3], 'Portrait cards need two rows'
