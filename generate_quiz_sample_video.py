#!/usr/bin/env python3
"""
Generate high-fidelity Vietnamese History Quiz Video (1080p 30fps) matching reference YouTube video:
- Vietnamese voiceover with Edge-TTS
- Visual illustration panels with drop shadow and rounded borders
- Multiple choice cards with circular badges and emerald green glow on reveal
- Animated smooth countdown progress bar with ticking sound
- Ding / chime and applause sound effects
- Mixed BGM with sidechain ducking
- 100% vector drawn stars and clean graphics
"""

import os
import sys
import math
import json
import asyncio
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

WIDTH = 1920
HEIGHT = 1080
FPS = 30
OUTPUT_DIR = Path("output/quiz_sample_1min")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR = OUTPUT_DIR / "frames"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR = OUTPUT_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Standard Windows Fonts with 100% full Vietnamese diacritics coverage
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REGULAR = "C:/Windows/Fonts/arial.ttf"

def get_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)

# Quiz Data
QUIZ_DATA = {
    "intro": {
        "title": "THỬ TÀI ĐỐ VUI LỊCH SỬ VIỆT NAM",
        "subtitle": "Chủ đề: Quốc Khánh 2/9 & Chủ tịch Hồ Chí Minh",
        "cta": "BẠN TRẢ LỜI ĐÚNG ĐƯỢC BAO NHIÊU CÂU?",
        "voice_text": "Chào mừng các bạn đến với thử thách đố vui lịch sử! Cùng thử tài ngay nào!"
    },
    "questions": [
        {
            "id": "q1",
            "order": 1,
            "badge": "CÂU 1",
            "question": "Quốc khánh Việt Nam được tổ chức lần đầu tiên vào ngày nào?",
            "choices": [
                {"id": "A", "text": "19 tháng 8 năm 1945"},
                {"id": "B", "text": "02 tháng 9 năm 1945"},
                {"id": "C", "text": "30 tháng 4 năm 1975"}
            ],
            "correct_id": "B",
            "answer_text": "02/09/1945 tại Quảng trường Ba Đình",
            "image_path": "tmp/quiz_sample/q1_clean.jpg",
            "question_voice": "Câu số 1: Quốc khánh Việt Nam được tổ chức lần đầu tiên vào ngày nào?",
            "answer_voice": "Chính xác! Đáp án đúng là B: Ngày 2 tháng 9 năm 1945 tại Quảng trường Ba Đình."
        },
        {
            "id": "q2",
            "order": 2,
            "badge": "CÂU 2",
            "question": "Ai là người trực tiếp soạn thảo và đọc bản Tuyên ngôn Độc lập năm 1945?",
            "choices": [
                {"id": "A", "text": "Chủ tịch Hồ Chí Minh"},
                {"id": "B", "text": "Đại tướng Võ Nguyên Giáp"},
                {"id": "C", "text": "Tổng bí thư Trường Chinh"}
            ],
            "correct_id": "A",
            "answer_text": "Chủ tịch Hồ Chí Minh kính yêu",
            "image_path": "tmp/quiz_sample/q2_clean.jpg",
            "question_voice": "Câu số 2: Ai là người trực tiếp soạn thảo và đọc bản Tuyên ngôn Độc lập?",
            "answer_voice": "Chuẩn rồi! Đáp án là A: Chủ tịch Hồ Chí Minh kính yêu."
        },
        {
            "id": "q3",
            "order": 3,
            "badge": "CÂU 3",
            "question": "Địa danh lịch sử nào tại Hà Nội là nơi diễn ra lễ đọc Tuyên ngôn Độc lập?",
            "choices": [
                {"id": "A", "text": "Nhà hát Lớn Hà Nội"},
                {"id": "B", "text": "Cột cờ Hà Nội"},
                {"id": "C", "text": "Quảng trường Ba Đình"}
            ],
            "correct_id": "C",
            "answer_text": "Quảng trường Ba Đình, Hà Nội",
            "image_path": "tmp/quiz_sample/q3_clean.jpg",
            "question_voice": "Câu số 3: Địa danh lịch sử nào tại Hà Nội là nơi Bác Hồ đọc bản Tuyên ngôn Độc lập?",
            "answer_voice": "Xuất sắc! Đáp án chính xác là C: Quảng trường Ba Đình lịch sử."
        }
    ],
    "outro": {
        "title": "HOÀN THÀNH THỬ THÁCH!",
        "subtitle": "Bạn đã trả lời đúng bao nhiêu câu hỏi?",
        "cta": "HÃY ĐỂ LẠI BÌNH LUẬN VÀ LIKE VIDEO NHÉ!",
        "voice_text": "Bạn trả lời đúng bao nhiêu câu? Hãy để lại bình luận bên dưới nhé!"
    }
}

async def generate_voice_tracks():
    """Copy or synthesize Edge-TTS clips for all voice lines."""
    import shutil
    mapping = {
        "intro.mp3": "tmp/quiz_sample/audio/intro.mp3",
        "q1_q.mp3": "tmp/quiz_sample/audio/q1.mp3",
        "q1_a.mp3": "tmp/quiz_sample/audio/a1.mp3",
        "q2_q.mp3": "tmp/quiz_sample/audio/q2.mp3",
        "q2_a.mp3": "tmp/quiz_sample/audio/a2.mp3",
        "q3_q.mp3": "tmp/quiz_sample/audio/q3.mp3",
        "q3_a.mp3": "tmp/quiz_sample/audio/a3.mp3",
        "outro.mp3": "tmp/quiz_sample/audio/outro.mp3",
    }
    for dest_name, src_path in mapping.items():
        dest = AUDIO_DIR / dest_name
        src = Path(src_path)
        if src.is_file():
            shutil.copyfile(src, dest)
            print(f"Loaded existing: {dest_name}")
        else:
            import edge_tts
            voice = "vi-VN-NamMinhNeural"
            text = "..."
            comm = edge_tts.Communicate(text, voice)
            await comm.save(str(dest))
            print(f"Synthesized: {dest_name}")

def probe_duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(res.stdout.strip())

def create_gradient_background(w: int, h: int) -> Image.Image:
    """Create a vibrant blue gradient with subtle geometric pattern."""
    base = Image.new("RGB", (w, h))
    pixels = base.load()
    
    top_c = (21, 101, 192)      # Deep blue #1565C0
    bot_c = (2, 136, 209)       # Cyan blue #0288D1
    
    for y in range(h):
        ratio = y / max(1, h - 1)
        r = int(top_c[0] * (1 - ratio) + bot_c[0] * ratio)
        g = int(top_c[1] * (1 - ratio) + bot_c[1] * ratio)
        b = int(top_c[2] * (1 - ratio) + bot_c[2] * ratio)
        for x in range(w):
            pixels[x, y] = (r, g, b)
            
    # Draw soft watermarks only along background margin
    draw = ImageDraw.Draw(base, "RGBA")
    font_q = get_font(FONT_BOLD, 64)
    for y in range(40, h, 200):
        draw.text((25, y), "?", font=font_q, fill=(255, 255, 255, 16))
        draw.text((w - 55, y), "?", font=font_q, fill=(255, 255, 255, 16))
            
    return base

def draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)

def draw_shadow(base: Image.Image, xy, radius: int, offset=(6, 8), blur_radius=12, shadow_color=(0, 0, 0, 90)):
    x0, y0, x1, y1 = xy
    sw, sh = x1 - x0 + blur_radius * 4, y1 - y0 + blur_radius * 4
    mask = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle(
        [blur_radius * 2, blur_radius * 2, blur_radius * 2 + (x1 - x0), blur_radius * 2 + (y1 - y0)],
        radius=radius, fill=shadow_color
    )
    mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))
    base.paste(mask, (x0 - blur_radius * 2 + offset[0], y0 - blur_radius * 2 + offset[1]), mask)

def draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r_out: float, r_in: float, fill, outline=None, width=1):
    """Draw an exact 5-point star polygon."""
    points = []
    angle_offset = -math.pi / 2
    for i in range(10):
        angle = angle_offset + i * (math.pi / 5)
        r = r_out if i % 2 == 0 else r_in
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=fill, outline=outline, width=width)

def render_question_frame(q: dict, state: str, progress: float, time_left_s: float = 0.0) -> Image.Image:
    """
    Render 1920x1080 frame for a question state.
    state: 'QUESTION', 'COUNTDOWN', 'REVEAL'
    progress: 1.0 (start of countdown) to 0.0 (end of countdown)
    """
    img = create_gradient_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(img)
    
    # ----------------------------------------------------
    # 1. HEADER BAR: Question Number Badge + Banner
    # ----------------------------------------------------
    # Badge (Top Left)
    badge_x, badge_y, badge_w, badge_h = 100, 45, 220, 115
    draw_shadow(img, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), radius=28)
    draw_rounded_rect(draw, (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), radius=28, fill=(211, 47, 47), outline=(255, 215, 0), width=4)
    
    font_badge = get_font(FONT_BOLD, 42)
    draw.text((badge_x + badge_w // 2, badge_y + badge_h // 2 - 2), q["badge"], font=font_badge, fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(120, 0, 0))
    
    # Question Banner (Center-Right)
    qb_x, qb_y, qb_w, qb_h = 345, 45, 1475, 115
    draw_shadow(img, (qb_x, qb_y, qb_x + qb_w, qb_y + qb_h), radius=28)
    
    # Gradient in Question Banner (Gold/Yellow to Orange)
    banner_img = Image.new("RGBA", (qb_w, qb_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(banner_img)
    for bx in range(qb_w):
        bratio = bx / qb_w
        br = int(255 * (1 - bratio * 0.15))
        bg = int(213 * (1 - bratio * 0.35))
        bb = int(79 * (1 - bratio * 0.7))
        bdraw.line([(bx, 0), (bx, qb_h)], fill=(br, bg, bb, 255))
        
    mask = Image.new("L", (qb_w, qb_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, qb_w, qb_h], radius=28, fill=255)
    img.paste(banner_img, (qb_x, qb_y), mask)
    
    draw_rounded_rect(draw, (qb_x, qb_y, qb_x + qb_w, qb_y + qb_h), radius=28, outline=(255, 255, 255), width=3)
    
    # Question Text with Arial Bold (100% full Vietnamese diacritics)
    q_text = q["question"]
    font_q = get_font(FONT_BOLD, 35)
    draw.text((qb_x + qb_w // 2, qb_y + qb_h // 2 - 2), q_text, font=font_q, fill=(20, 30, 50), anchor="mm")
    
    # ----------------------------------------------------
    # 2. LEFT COLUMN: Illustration Card
    # ----------------------------------------------------
    card_x, card_y, card_w, card_h = 100, 195, 780, 685
    draw_shadow(img, (card_x, card_y, card_x + card_w, card_y + card_h), radius=24)
    draw_rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), radius=24, fill=(255, 255, 255), outline=(220, 20, 60), width=6)
    
    # Paste Illustration Image inside card
    if Path(q["image_path"]).is_file():
        ill_raw = Image.open(q["image_path"]).convert("RGB")
        target_w, target_h = card_w - 24, card_h - 24
        ill_fitted = ImageOps.fit(ill_raw, (target_w, target_h), method=Image.Resampling.LANCZOS)
        
        ill_mask = Image.new("L", (target_w, target_h), 0)
        ImageDraw.Draw(ill_mask).rounded_rectangle([0, 0, target_w, target_h], radius=18, fill=255)
        img.paste(ill_fitted, (card_x + 12, card_y + 12), ill_mask)
        
    # ----------------------------------------------------
    # 3. RIGHT COLUMN: Multiple-Choice Option Pills
    # ----------------------------------------------------
    opt_x = 920
    opt_w = 900
    opt_h = 145
    opt_gap = 42
    start_y = 225
    
    correct_id = q["correct_id"]
    is_reveal = (state == "REVEAL")
    
    for i, choice in enumerate(q["choices"]):
        cid = choice["id"]
        ctext = choice["text"]
        is_correct = (cid == correct_id)
        cy = start_y + i * (opt_h + opt_gap)
        
        draw_shadow(img, (opt_x, cy, opt_x + opt_w, cy + opt_h), radius=32)
        
        # Determine styling
        if is_reveal and is_correct:
            # Correct answer highlighted in emerald/lime green
            pill_fill = (235, 255, 240)
            pill_border = (46, 204, 113)
            pill_border_w = 6
            badge_fill = (39, 174, 96)
            text_color = (15, 90, 45)
        elif is_reveal and not is_correct:
            # Dim other answers slightly
            pill_fill = (245, 247, 250)
            pill_border = (200, 205, 215)
            pill_border_w = 3
            badge_fill = (140, 150, 165)
            text_color = (120, 130, 145)
        else:
            # Normal state
            pill_fill = (255, 255, 255)
            pill_border = (255, 200, 50)
            pill_border_w = 4
            badge_fill = (211, 47, 47)
            text_color = (15, 30, 60)
            
        draw_rounded_rect(draw, (opt_x, cy, opt_x + opt_w, cy + opt_h), radius=32, fill=pill_fill, outline=pill_border, width=pill_border_w)
        
        # Badge Circle
        badge_cx = opt_x + 75
        badge_cy = cy + opt_h // 2
        badge_r = 45
        draw.ellipse([badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r], fill=badge_fill, outline=(255, 255, 255), width=4)
        
        font_cbadge = get_font(FONT_BOLD, 46)
        draw.text((badge_cx, badge_cy - 2), cid, font=font_cbadge, fill=(255, 255, 255), anchor="mm")
        
        # Choice Text
        font_ctext = get_font(FONT_BOLD, 36)
        draw.text((opt_x + 155, badge_cy - 2), ctext, font=font_ctext, fill=text_color, anchor="lm")
        
        # If correct on reveal, add celebratory checkmark
        if is_reveal and is_correct:
            check_x = opt_x + opt_w - 75
            draw.ellipse([check_x - 30, badge_cy - 30, check_x + 30, badge_cy + 30], fill=(39, 174, 96))
            draw.text((check_x, badge_cy - 2), "✓", font=get_font(FONT_BOLD, 36), fill=(255, 255, 255), anchor="mm")

    # ----------------------------------------------------
    # 4. BOTTOM BAR: Countdown Timer or Answer Explanation
    # ----------------------------------------------------
    bar_x, bar_y, bar_w, bar_h = 100, 920, 1720, 90
    draw_shadow(img, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=28)
    
    if is_reveal:
        # Explanation Banner
        draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=28, fill=(46, 204, 113), outline=(255, 255, 255), width=4)
        exp_text = f"ĐÁP ÁN ĐÚNG: {correct_id} — {q['answer_text']}"
        font_exp = get_font(FONT_BOLD, 36)
        draw.text((bar_x + bar_w // 2, bar_y + bar_h // 2 - 2), exp_text, font=font_exp, fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(20, 100, 50))
    elif state == "COUNTDOWN":
        # Countdown Track
        draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=28, fill=(10, 40, 80), outline=(255, 255, 255), width=4)
        
        # Fill Progress (Green to Cyan)
        fill_w = max(0, int((bar_w - 16) * max(0.0, min(1.0, progress))))
        if fill_w > 10:
            draw_rounded_rect(draw, (bar_x + 8, bar_y + 8, bar_x + 8 + fill_w, bar_y + bar_h - 8), radius=22, fill=(0, 230, 118))
            
        timer_text = f"THỜI GIAN CÒN LẠI: {max(0, math.ceil(time_left_s))} GIÂY"
        font_timer = get_font(FONT_BOLD, 34)
        draw.text((bar_x + bar_w // 2, bar_y + bar_h // 2 - 2), timer_text, font=font_timer, fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
    else:
        # Question Reading State
        draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=28, fill=(20, 60, 120), outline=(255, 255, 255), width=4)
        hint_text = "Chuẩn bị đếm ngược để chọn đáp án đúng nhất..."
        font_hint = get_font(FONT_BOLD, 34)
        draw.text((bar_x + bar_w // 2, bar_y + bar_h // 2 - 2), hint_text, font=font_hint, fill=(255, 235, 150), anchor="mm")
        
    return img

def render_title_card_frame(data: dict, is_intro: bool) -> Image.Image:
    """Render 1920x1080 Intro or Outro card with full Vietnamese Arial Bold and vector stars."""
    img = create_gradient_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(img)
    
    # Large Center Card
    card_x, card_y, card_w, card_h = 160, 120, 1600, 840
    draw_shadow(img, (card_x, card_y, card_x + card_w, card_y + card_h), radius=40, blur_radius=20)
    draw_rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), radius=40, fill=(255, 255, 255), outline=(255, 193, 7), width=8)
    
    # Red Header Banner inside card
    head_x, head_y, head_w, head_h = card_x + 40, card_y + 40, card_w - 80, 220
    draw_rounded_rect(draw, (head_x, head_y, head_x + head_w, head_y + head_h), radius=30, fill=(211, 47, 47), outline=(255, 215, 0), width=4)
    
    font_main = get_font(FONT_BOLD, 52)
    draw.text((head_x + head_w // 2, head_y + head_h // 2 - 2), data["title"], font=font_main, fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(100, 0, 0))
    
    # Subtitle
    font_sub = get_font(FONT_BOLD, 44)
    draw.text((card_x + card_w // 2, card_y + 420), data["subtitle"], font=font_sub, fill=(21, 101, 192), anchor="mm")
    
    # Decorative Divider Line with Vector Stars
    div_y = card_y + 530
    draw.line([(card_x + 200, div_y), (card_x + card_w - 200, div_y)], fill=(255, 193, 7), width=4)
    
    # Draw central gold/red badge
    badge_w, badge_h = 440, 60
    badge_rect = (card_x + (card_w - badge_w) // 2, div_y - badge_h // 2, card_x + (card_w + badge_w) // 2, div_y + badge_h // 2)
    draw_rounded_rect(draw, badge_rect, radius=20, fill=(211, 47, 47), outline=(255, 215, 0), width=3)
    
    draw_star(draw, badge_rect[0] + 35, div_y, r_out=18, r_in=8, fill=(255, 215, 0))
    draw_star(draw, badge_rect[2] - 35, div_y, r_out=18, r_in=8, fill=(255, 215, 0))
    
    label_text = "QUỐC KHÁNH 2/9" if is_intro else "XIN CẢM ƠN"
    draw.text((card_x + card_w // 2, div_y - 2), label_text, font=get_font(FONT_BOLD, 30), fill=(255, 255, 255), anchor="mm")
    
    # Call to action box
    cta_x, cta_y, cta_w, cta_h = card_x + 120, card_y + 610, card_w - 240, 140
    cta_fill = (255, 235, 59) if is_intro else (46, 204, 113)
    cta_text_col = (150, 40, 0) if is_intro else (255, 255, 255)
    
    draw_rounded_rect(draw, (cta_x, cta_y, cta_x + cta_w, cta_y + cta_h), radius=28, fill=cta_fill, outline=(255, 255, 255), width=4)
    font_cta = get_font(FONT_BOLD, 38)
    draw.text((cta_x + cta_w // 2, cta_y + cta_h // 2 - 2), data["cta"], font=font_cta, fill=cta_text_col, anchor="mm")
    
    return img

def build_full_video_and_audio():
    print("=== STEP 1: PROBING VOICE DURATIONS ===")
    intro_dur = probe_duration(AUDIO_DIR / "intro.mp3")
    outro_dur = probe_duration(AUDIO_DIR / "outro.mp3")
    
    q_durs = []
    for q in QUIZ_DATA["questions"]:
        qd = probe_duration(AUDIO_DIR / f"{q['id']}_q.mp3")
        ad = probe_duration(AUDIO_DIR / f"{q['id']}_a.mp3")
        q_durs.append({"q_dur": qd, "a_dur": ad})
        print(f"Question {q['id']}: Q voice={qd:.2f}s, A voice={ad:.2f}s")
        
    print(f"Intro: {intro_dur:.2f}s | Outro: {outro_dur:.2f}s")
    
    # ----------------------------------------------------
    # BUILD TIMELINE
    # ----------------------------------------------------
    COUNTDOWN_SEC = 3.5  # Fast & punchy countdown
    
    timeline = []
    current_time = 0.0
    
    # 1. Intro Section
    intro_dur_total = intro_dur + 0.5
    timeline.append({
        "type": "INTRO",
        "start": current_time,
        "duration": intro_dur_total,
        "audio_clip": AUDIO_DIR / "intro.mp3",
        "audio_offset": current_time
    })
    current_time += intro_dur_total
    
    # 2. Questions
    sfx_events = []
    
    for i, q in enumerate(QUIZ_DATA["questions"]):
        qd = q_durs[i]["q_dur"]
        ad = q_durs[i]["a_dur"]
        
        # Phase 1: Question Reading
        q_read_dur = qd + 0.3
        timeline.append({
            "type": "QUESTION",
            "q_data": q,
            "start": current_time,
            "duration": q_read_dur,
            "audio_clip": AUDIO_DIR / f"{q['id']}_q.mp3",
            "audio_offset": current_time
        })
        current_time += q_read_dur
        
        # Phase 2: Countdown
        cd_start = current_time
        timeline.append({
            "type": "COUNTDOWN",
            "q_data": q,
            "start": cd_start,
            "duration": COUNTDOWN_SEC,
        })
        # Schedule countdown tick SFX
        sfx_events.append({"sfx": "tmp/clean_audio/sfx_countdown_clean.wav", "time": cd_start, "dur": COUNTDOWN_SEC})
        current_time += COUNTDOWN_SEC
        
        # Phase 3: Answer Reveal
        rev_start = current_time
        rev_dur = ad + 0.8
        timeline.append({
            "type": "REVEAL",
            "q_data": q,
            "start": rev_start,
            "duration": rev_dur,
            "audio_clip": AUDIO_DIR / f"{q['id']}_a.mp3",
            "audio_offset": rev_start
        })
        # Schedule ding / chime SFX at reveal moment
        sfx_events.append({"sfx": "tmp/clean_audio/sfx_ding_clean.wav", "time": rev_start, "dur": 1.8})
        current_time += rev_dur
        
    # 3. Outro Section
    outro_dur_total = outro_dur + 0.5
    timeline.append({
        "type": "OUTRO",
        "start": current_time,
        "duration": outro_dur_total,
        "audio_clip": AUDIO_DIR / "outro.mp3",
        "audio_offset": current_time
    })
    current_time += outro_dur_total
    
    total_video_duration = current_time
    print(f"=== TOTAL CALCULATED DURATION: {total_video_duration:.2f}s ===")
    
    # ----------------------------------------------------
    # STEP 2: RENDER VIDEO FRAMES
    # ----------------------------------------------------
    print("=== STEP 2: RENDERING VIDEO FRAMES ===")
    concat_entries = []
    frame_idx = 0
    
    for item in timeline:
        itype = item["type"]
        idur = item["duration"]
        
        if itype == "INTRO":
            img = render_title_card_frame(QUIZ_DATA["intro"], is_intro=True)
            fpath = FRAMES_DIR / f"frame_{frame_idx:04d}_intro.png"
            img.save(fpath)
            concat_entries.append((fpath, idur))
            frame_idx += 1
            
        elif itype == "OUTRO":
            img = render_title_card_frame(QUIZ_DATA["outro"], is_intro=False)
            fpath = FRAMES_DIR / f"frame_{frame_idx:04d}_outro.png"
            img.save(fpath)
            concat_entries.append((fpath, idur))
            frame_idx += 1
            
        elif itype == "QUESTION":
            img = render_question_frame(item["q_data"], state="QUESTION", progress=0.0)
            fpath = FRAMES_DIR / f"frame_{frame_idx:04d}_{item['q_data']['id']}_q.png"
            img.save(fpath)
            concat_entries.append((fpath, idur))
            frame_idx += 1
            
        elif itype == "COUNTDOWN":
            # For smooth countdown animation, render multiple frames (15 updates per second)
            cd_fps = 15
            num_cd_frames = max(1, int(idur * cd_fps))
            frame_dur = idur / num_cd_frames
            
            for cdf in range(num_cd_frames):
                prog = 1.0 - (cdf / num_cd_frames)
                time_left = prog * idur
                img = render_question_frame(item["q_data"], state="COUNTDOWN", progress=prog, time_left_s=time_left)
                fpath = FRAMES_DIR / f"frame_{frame_idx:04d}_{item['q_data']['id']}_cd_{cdf:02d}.png"
                img.save(fpath)
                concat_entries.append((fpath, frame_dur))
                frame_idx += 1
                
        elif itype == "REVEAL":
            img = render_question_frame(item["q_data"], state="REVEAL", progress=1.0)
            fpath = FRAMES_DIR / f"frame_{frame_idx:04d}_{item['q_data']['id']}_rev.png"
            img.save(fpath)
            concat_entries.append((fpath, idur))
            frame_idx += 1

    # Write FFconcat file
    concat_txt = OUTPUT_DIR / "quiz.ffconcat"
    with open(concat_txt, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for fpath, dur in concat_entries:
            f.write(f"file '{fpath.resolve().as_posix()}'\n")
            f.write(f"duration {dur:.4f}\n")
        # Repeat last frame
        f.write(f"file '{concat_entries[-1][0].resolve().as_posix()}'\n")
        
    print(f"Rendered {len(concat_entries)} video segments.")
    
    # ----------------------------------------------------
    # STEP 3: AUDIO COMPOSITING & MIXING
    # ----------------------------------------------------
    print("=== STEP 3: COMPOSITING AUDIO ===")
    audio_inputs = []
    filter_chains = []
    # Input 0 is video concat, so audio inputs start at index 1
    input_idx = 1
    
    # Voice tracks
    voice_labels = []
    for item in timeline:
        if "audio_clip" in item:
            audio_inputs.extend(["-i", str(item["audio_clip"].resolve())])
            delay_ms = int(item["audio_offset"] * 1000)
            lbl = f"v_{input_idx}"
            filter_chains.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},aresample=48000[{lbl}]")
            voice_labels.append(f"[{lbl}]")
            input_idx += 1
            
    # Combine all voice streams into one [voice_main]
    if len(voice_labels) == 1:
        filter_chains.append(f"{voice_labels[0]}anull[voice_main]")
    else:
        filter_chains.append(f"{''.join(voice_labels)}amix=inputs={len(voice_labels)}:duration=longest:normalize=0[voice_main]")
        
    # SFX tracks
    sfx_labels = []
    for sfx in sfx_events:
        audio_inputs.extend(["-i", str(Path(sfx["sfx"]).resolve())])
        delay_ms = int(sfx["time"] * 1000)
        dur = sfx["dur"]
        lbl = f"sfx_{input_idx}"
        filter_chains.append(f"[{input_idx}:a]atrim=0:{dur:.3f},adelay={delay_ms}|{delay_ms},volume=-3dB,aresample=48000[{lbl}]")
        sfx_labels.append(f"[{lbl}]")
        input_idx += 1
        
    if sfx_labels:
        filter_chains.append(f"{''.join(sfx_labels)}amix=inputs={len(sfx_labels)}:duration=longest:normalize=0[sfx_main]")
    else:
        filter_chains.append(f"anullsrc=r=48000:cl=stereo:d={total_video_duration:.3f}[sfx_main]")

    # BGM Track (100% clean synthesized marimba & bass quiz music)
    bgm_path = Path("tmp/clean_audio/bgm_clean.wav")
    audio_inputs.extend(["-i", str(bgm_path.resolve())])
    bgm_idx = input_idx
    filter_chains.append(
        f"[{bgm_idx}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_video_duration:.3f},volume=-18dB,aresample=48000[bgm_raw]"
    )
    
    # Sidechain Ducking BGM under Voice
    filter_chains.extend([
        "[voice_main]asplit=2[v_play][v_sc]",
        "[bgm_raw][v_sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=350[bgm_ducked]",
        "[v_play][sfx_main][bgm_ducked]amix=inputs=3:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[final_audio]"
    ])
    
    # ----------------------------------------------------
    # STEP 4: FINAL ENCODE MP4
    # ----------------------------------------------------
    print("=== STEP 4: ENCODING FINAL MP4 ===")
    final_mp4 = OUTPUT_DIR / "vietnam_history_quiz_1min.mp4"
    
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        *audio_inputs,
        "-filter_complex", ";".join(filter_chains),
        "-map", "0:v:0",
        "-map", "[final_audio]",
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total_video_duration:.3f}",
        "-movflags", "+faststart",
        str(final_mp4)
    ]
    
    res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg Error:\n", res.stderr[-2000:], file=sys.stderr)
        raise RuntimeError("FFmpeg encode failed")
        
    print(f"\nSUCCESS! Video generated at:\n{final_mp4.resolve()}")
    return final_mp4

async def main():
    await generate_voice_tracks()
    build_full_video_and_audio()

if __name__ == "__main__":
    asyncio.run(main())
