"""Locale-safe opt-in compositor, using the existing engine's timeline and audio."""
from pathlib import Path
from PIL import Image
from app.services.quiz_channel_profiles import get_profile, labels
from app.services.quiz_image_layout import fitted_size
from app.services.quiz_locales import font_factory as locale_font_factory, wrap_lines

PALETTES = {'de-football':((12,25,44),(36,180,240)), 'de-wissen':((25,29,32),(225,190,105)), 'fr-culture':((39,31,48),(211,174,205)), 'it-calcio':((16,36,29),(63,214,131))}


def text_box(draw, text, box, font_factory, size=42, fill='white'):
    x0,y0,x1,y1 = box
    for fs in range(size, 15, -2):
        font = font_factory(fs, bold=True)
        lines = wrap_lines(draw, text, font, x1-x0)
        if len(lines)*(fs+10) <= y1-y0 and all(draw.textlength(l,font=font)<=x1-x0 for l in lines):
            for i,l in enumerate(lines):
                draw.text((x0,y0+i*(fs+10)),l,font=font,fill=fill)
            return
    raise ValueError('Channel text does not fit; shorten before render')


def photo(canvas, path, box):
    with Image.open(path) as im:
        source = im.convert('RGBA')
    width,height = fitted_size(source.size,(box[2]-box[0],box[3]-box[1]))
    resized = source.resize((width,height),Image.Resampling.LANCZOS)
    canvas.paste(resized,((box[0]+box[2]-width)//2,(box[1]+box[3]-height)//2),resized)


def render(engine, canvas, draw, font_factory, *, event=None, time=0, outro=False):
    key = engine.opt.channel_profile
    profile, local = get_profile(key), labels(key)
    font_factory = locale_font_factory(profile['locale'], font_factory)
    bg, accent = PALETTES.get(key, ((18,29,43),(110,200,235)))
    w,h = canvas.size
    draw.rectangle((0,0,w,h), fill=bg)
    margin = 60
    if event is None:
        text_box(draw,local['score'] if outro else profile['hook'],(margin,h//4,w-margin,h//2),font_factory,64,accent)
        text_box(draw,profile['cta'] if outro else local['choose'],(margin,h//2,w-margin,h-180),font_factory,40)
        return canvas
    q = event['data']
    rev = time >= event['rev_start']
    idx,total = event['idx'],event.get('total_q',1)
    level_index = {'easy':0,'medium':1,'hard':2,'final':3}.get(q.get('difficulty'), min(3,int((idx-1)*4/max(1,total))))
    level = local['levels'][level_index]
    text_box(draw,f"{local['question']} {idx}/{total} · {level}",(margin,35,w-margin,110),font_factory,32,accent)
    if q.get('series'):
        text_box(draw,str(q['series']),(margin,295,w-margin,330),font_factory,22,accent)
    text_box(draw,q['question'],(margin,125,w-margin,300),font_factory,48)
    vertical = h>w
    visual = (margin,330,w-margin,900) if vertical else (margin,330,w//2-30,h-180)
    choices_box = (margin,960,w-margin,h-230) if vertical else (w//2+30,330,w-margin,h-180)
    cards = q.get('cards',[])
    if cards:
        for i,c in enumerate(cards[:4]):
            cw=(visual[2]-visual[0])//2
            ch=(visual[3]-visual[1])//2
            x=visual[0]+(i%2)*cw
            y=visual[1]+(i//2)*ch
            if c.get('image_path'):
                photo(canvas,c['image_path'],(x+10,y+45,x+cw-10,y+ch-15))
            text_box(draw,str(c.get('label',c.get('id',i+1))),(x+10,y,x+cw-10,y+42),font_factory,26,accent)
    else:
        path = q.get('scene_image') or (q.get('reveal_image_path') if rev or q.get('progressive_unblur') else None)
        if path and Path(path).is_file():
            if not rev and q.get('progressive_unblur') and not q.get('scene_image'):
                text_box(draw,'?',visual,font_factory,120,accent)
            else:
                photo(canvas,path,visual)
        else:
            clue_text = ' · '.join(str(c.get('word','')) for c in q.get('clues',[]))
            text_box(draw,clue_text or local['choose'],visual,font_factory,46,accent)
    choices = engine._normalize_choices(q)
    if not choices:
        choices = [(str(c.get('id')),str(c.get('label'))) for c in cards] or [(str(o),str(o)) for o in q.get('options',[])]
    correct = str(q.get('correct_id') or q.get('correct_option',''))
    x0,y0,x1,y1=choices_box
    step=(y1-y0)//max(1,len(choices))
    for i,(cid,label) in enumerate(choices):
        cy=y0+i*step
        color=accent if rev and str(cid)==correct else (55,61,73)
        draw.rounded_rectangle((x0,cy,x1,cy+step-15),radius=16,fill=color)
        text_box(draw,f'{cid}  {label}',(x0+20,cy+12,x1-20,cy+step-20),font_factory,38)
    if rev:
        answer=q.get('explanation_text') or q.get('answer_text') or next((label for cid,label in choices if str(cid)==correct),correct)
        footer=f"{local['answer']}: {answer}"
    else:
        seconds=max(0,int(event['rev_start']-max(time,event['cd_start'])+0.99))
        footer=f"{seconds} s · {local['choose']}"
    text_box(draw,footer,(margin,h-160,w-margin,h-30),font_factory,38,accent)
    return canvas
