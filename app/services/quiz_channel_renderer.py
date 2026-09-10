"""Locale-safe opt-in compositor, using the existing engine's timeline and audio."""
import math
from pathlib import Path
from PIL import Image
from app.services.quiz_channel_profiles import get_profile, labels
from app.services.quiz_image_layout import fitted_size
from app.services.quiz_locales import font_factory as locale_font_factory, wrap_lines
from app.services.quiz_layout_spec import resolve_layout

PALETTES = {'de-football':((12,25,44),(36,180,240)), 'de-wissen':((25,29,32),(225,190,105)), 'fr-culture':((39,31,48),(211,174,205)), 'it-calcio':((16,36,29),(63,214,131))}


def text_box(draw, text, box, font_factory, size=42, fill: str | tuple[int, int, int] = 'white'):
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


def _scaled_layout_box(layout, rect, canvas):
    if rect is None:
        return None
    x0, y0, x1, y1 = rect.as_tuple()
    nominal_w, nominal_h = layout.canvas.width, layout.canvas.height
    return (
        round(x0 * canvas.width / nominal_w),
        round(y0 * canvas.height / nominal_h),
        round(x1 * canvas.width / nominal_w),
        round(y1 * canvas.height / nominal_h),
    )


def render(engine, canvas, draw, font_factory, *, event=None, time=0, outro=False):
    key = engine.opt.channel_profile
    if key:
        profile, local = get_profile(key), labels(key)
        locale = profile['locale']
    else:
        from app.services.quiz_locales import locale_labels
        locale = str(getattr(engine.opt, 'language', 'en-US') or 'en-US')
        try:
            local = locale_labels(locale)
        except KeyError:
            locale = 'en-US'
            local = locale_labels(locale)
        profile = {'locale': locale, 'hook': '', 'cta': ''}
    font_factory = locale_font_factory(locale, font_factory)
    visual_style = getattr(engine.opt, 'visual_style', None) or {}
    style_id = str(visual_style.get('id') or '') if isinstance(visual_style, dict) else ''
    snapshot = visual_style.get('snapshot') if isinstance(visual_style, dict) else {}
    palette = snapshot.get('palette') if isinstance(snapshot, dict) else {}
    shape_tokens = snapshot.get('shapes') if isinstance(snapshot, dict) else {}
    spacing_tokens = snapshot.get('spacing') if isinstance(snapshot, dict) else {}
    typography_tokens = snapshot.get('typography') if isinstance(snapshot, dict) else {}
    style_palette = {
        'sport-scoreboard': ((11, 25, 39), (255, 205, 62)),
        'editorial-culture': ((232, 224, 208), (163, 49, 42)),
        'clear-knowledge': ((235, 241, 237), (22, 104, 91)),
    }
    bg, accent = style_palette.get(style_id, PALETTES.get(key, ((18,29,43),(110,200,235))))
    color_tokens = {
        '#d7c3a4': '#d7c3a4', '#1f2b2a': '#1f2b2a', '#b5362b': '#b5362b',
    }
    if isinstance(palette, dict):
        bg_token = palette.get('background')
        text_token = palette.get('text')
        accent_token = palette.get('accent')
        if isinstance(bg_token, str) and bg_token.lower() in color_tokens:
            bg = bg_token
        if isinstance(accent_token, str) and accent_token.lower() in color_tokens:
            accent = accent_token
    w,h = canvas.size
    draw.rectangle((0,0,w,h), fill=bg)
    margin = max(24, int(spacing_tokens.get('gutter', 60)) if isinstance(spacing_tokens, dict) and isinstance(spacing_tokens.get('gutter', 60), int) else 60)
    panel_radius = 2 if shape_tokens.get('panels') == 'square-editorial' else 16
    if event is None:
        text_box(draw,local['score'] if outro else profile['hook'],(margin,h//4,w-margin,h//2),font_factory,64,accent)
        text_box(draw,profile['cta'] if outro else local['choose'],(margin,h//2,w-margin,h-180),font_factory,40)
        return canvas
    q = event['data']
    rev = time >= event['rev_start']
    motion_level = str(visual_style.get('motion') or 'medium') if isinstance(visual_style, dict) else 'medium'
    motion_amplitude = {'low': 0.35, 'medium': 0.7, 'high': 1.0}.get(motion_level, 0.7)
    idx,total = event['idx'],event.get('total_q',1)
    level_index = {'easy':0,'medium':1,'hard':2,'final':3}.get(q.get('difficulty'), min(3,int((idx-1)*4/max(1,total))))
    level = local['levels'][level_index]
    layout = None
    if isinstance(visual_style, dict) and style_id:
        aspect = '9:16' if h > w else '16:9'
        layout = resolve_layout(q, aspect, visual_style)
    question_box = _scaled_layout_box(layout, layout.question, canvas) if layout else (margin,125,w-margin,300)
    marker_x = margin + int(18 * motion_amplitude * math.sin(float(time) * 2.0))
    draw.line((marker_x, 118, marker_x + 72, 118), fill=accent, width=4)
    text_box(draw,f"{local['question']} {idx}/{total} · {level}",(margin,35,w-margin,110),font_factory,32,accent)
    if q.get('series'):
        series_box = ((question_box[0], max(132, question_box[1]-42), question_box[2], question_box[1]-8)
                      if layout is not None else (margin,295,w-margin,330))
        text_box(draw,str(q['series']),series_box,font_factory,22,accent)
    default_question_fill = (31, 43, 42) if style_id == 'clear-knowledge' else ('white' if style_id == 'sport-scoreboard' else (40, 39, 36))
    question_fill = default_question_fill
    if isinstance(palette, dict) and isinstance(palette.get('text'), str) and palette.get('text', '').lower() in color_tokens:
        question_fill = palette['text']
    question_size = 48
    if isinstance(typography_tokens, dict) and typography_tokens.get('display') == 'editorial-display':
        question_size = 44
    text_box(draw,q['question'],question_box,font_factory,question_size,question_fill)
    vertical = h>w
    visual = (_scaled_layout_box(layout, layout.visual, canvas)
              if layout is not None else ((margin,330,w-margin,900) if vertical else (margin,330,w//2-30,h-180)))
    choices_box = (margin,960,w-margin,h-230) if vertical else (w//2+30,330,w-margin,h-180)
    cards = q.get('cards',[])
    if cards:
        if visual is None:
            raise ValueError('Four-card layout requires a visual evidence rectangle')
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
        if visual is not None and path and Path(path).is_file():
            if not rev and q.get('progressive_unblur') and not q.get('scene_image'):
                text_box(draw,'?',visual,font_factory,120,accent)
            else:
                photo(canvas,path,visual)
        elif layout is None:
            clue_text = ' · '.join(str(c.get('word','')) for c in q.get('clues',[]))
            text_box(draw,clue_text or local['choose'],visual,font_factory,46,accent)
    choices = engine._normalize_choices(q)
    if not choices:
        choices = [(str(c.get('id')),str(c.get('label'))) for c in cards] or [(str(o),str(o)) for o in q.get('options',[])]
    correct = str(q.get('correct_id') or q.get('correct_option',''))
    styled_choices = ([box for box in (_scaled_layout_box(layout, rect, canvas) for rect in layout.choices) if box is not None]
                      if layout is not None else [])
    x0,y0,x1,y1=choices_box
    step=(y1-y0)//max(1,len(choices))
    for i,(cid,label) in enumerate(choices):
        if i < len(styled_choices):
            choice_rect = styled_choices[i]
        else:
            cy=y0+i*step
            choice_rect = (x0,cy,x1,cy+step-15)
        cx0,cy0,cx1,cy1 = choice_rect
        color=accent if rev and str(cid)==correct else (55,61,73)
        draw.rounded_rectangle(choice_rect,radius=panel_radius,fill=color)
        from PIL import ImageColor
        rgb = ImageColor.getrgb(color) if isinstance(color, str) else color
        ink = (18, 29, 43) if sum(rgb[:3]) > 450 else (255, 255, 255)
        text_box(draw,f'{cid}  {label}',(cx0+20,cy0+12,cx1-20,cy1-5),font_factory,38,ink)
    if rev:
        answer=q.get('explanation_text') or q.get('answer_text') or next((label for cid,label in choices if str(cid)==correct),correct)
        footer=f"{local['answer']}: {answer}"
    else:
        seconds=max(0,int(event['rev_start']-max(time,event['cd_start'])+0.99))
        footer=f"{seconds} s · {local['choose']}"
    text_box(draw,footer,(margin,h-160,w-margin,h-30),font_factory,38,accent)
    return canvas
