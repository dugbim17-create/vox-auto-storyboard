from types import SimpleNamespace
from PIL import Image,ImageDraw
from app.services import quiz_channel_renderer as renderer


def test_explicit_difficulty_and_series_reach_header(monkeypatch):
    texts=[]
    monkeypatch.setattr(renderer,'text_box',lambda draw,text,*a,**kw: texts.append(text))
    engine=SimpleNamespace(opt=SimpleNamespace(channel_profile='fr-culture'),_normalize_choices=lambda q:[('A','Paris'),('B','Lyon')])
    im=Image.new('RGB',(1920,1080))
    event={'idx':1,'total_q':30,'rev_start':7,'cd_start':0,'data':{'question':'Quelle ville ?','difficulty':'hard','series':'Proverbes français','correct_id':'A'}}
    renderer.render(engine,im,ImageDraw.Draw(im),lambda *a,**k:None,event=event,time=1)
    assert 'EXPERT' in texts[0]
    assert any('Proverbes français' in t for t in texts)
