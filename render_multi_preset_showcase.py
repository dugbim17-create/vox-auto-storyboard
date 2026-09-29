"""Comprehensive Multi-Preset & Visual Effects Showcase Video Generator for Vox Studio.

Demonstrates:
- Preset 1: Editorial Collage (Torn Paper, Archival Photo Plates, Tape, Highlighter, Red Stamps)
- Preset 2: Cinematic Documentary (Deep Teal/Amber Color Grading, Widescreen Letterbox, Tactical Map & Animated Vector Arrows)
- Preset 3: Financial & Tech Minimal (Animated Financial Line Charts, Candlesticks, Rolling Odometer Metrics)
- Dynamic Transitions: Split-Screen Comparison, Photo Stack Shuffle, Live Highlighters, Impact Stamps, Subtitles & Auto-SFX
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
import time
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from piper.voice import PiperVoice

from app.services.document_highlighter import DocumentHighlighterService, HighlightOptions
from app.services.final_composer import FinalComposer
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vox_showcase")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_showcase_all_presets")
IMAGES_DIR = PROJECT_DIR / "ai_images"
PIPER_MODEL = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx")
PIPER_CONFIG = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx.json")

WIDTH = 1920
HEIGHT = 1080
FPS = 30


@lru_cache(maxsize=32)
def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for c in candidates:
        if Path(c).is_file():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


# Easing curves
def ease_out_back(t: float, s: float = 1.7) -> float:
    t = max(0.0, min(1.0, t)) - 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)


# --------------------------------------------------------------------------- #
# Cached Graphic Components
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=16)
def get_cached_photo_plate(img_path: str, w: int, h: int, caption: str = "", angle_deg: float = 0.0) -> Image.Image:
    im = Image.open(img_path).convert("RGB")
    pad_border = 14
    pad_bottom = 44 if caption else 14
    photo_w = max(10, w - pad_border * 2)
    photo_h = max(10, h - pad_border - pad_bottom)
    im_fitted = im.resize((photo_w, photo_h), Image.Resampling.BICUBIC)

    frame = Image.new("RGBA", (w, h), (248, 246, 238, 255))
    draw = ImageDraw.Draw(frame)
    draw.rectangle([(0, 0), (w - 1, h - 1)], outline=(200, 195, 180, 255), width=2)
    frame.paste(im_fitted, (pad_border, pad_border))

    if caption:
        font = get_font(16, bold=True)
        draw.text((w // 2, h - 24), caption.upper(), font=font, fill=(50, 50, 55, 255), anchor="mm")

    # Tape
    tape_w, tape_h = 80, 24
    tape_img = Image.new("RGBA", (tape_w, tape_h), (255, 250, 220, 160))
    tdraw = ImageDraw.Draw(tape_img)
    tdraw.rectangle([(0, 0), (tape_w, tape_h)], outline=(220, 210, 170, 120), width=1)
    tape_img = tape_img.rotate(2, resample=Image.Resampling.BICUBIC, expand=True)
    frame.paste(tape_img, ((w - tape_img.width) // 2, -8), mask=tape_img.split()[-1])

    cutout = PaperCraftService.create_torn_cutout(
        frame, PaperCutoutOptions(border_width=6, roughness=0.2, shadow=True, shadow_opacity=0.45)
    )
    if angle_deg != 0.0:
        cutout = cutout.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
    return cutout


@lru_cache(maxsize=16)
def get_cached_card_base(w: int, h: int, title: str, subtitle: str, lines_tuple: tuple[str, ...], accent_r: int, accent_g: int, accent_b: int, angle_deg: float) -> Image.Image:
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(card)
    cdraw.rectangle([(0, 0), (w, h)], fill=(245, 242, 234, 255), outline=(190, 185, 170, 255), width=2)

    banner_h = 42
    cdraw.rectangle([(0, 0), (w, banner_h)], fill=(accent_r, accent_g, accent_b, 255))
    font_sub = get_font(18, bold=True)
    cdraw.text((16, 10), subtitle.upper(), font=font_sub, fill=(255, 255, 255, 255))

    font_title = get_font(22, bold=True)
    cdraw.text((20, banner_h + 16), title, font=font_title, fill=(24, 24, 28, 255))

    font_body = get_font(17, bold=False)
    for i, line in enumerate(lines_tuple):
        ly = banner_h + 60 + i * 32
        cdraw.text((20, ly), line, font=font_body, fill=(60, 60, 65, 255))

    tape_w, tape_h = 90, 26
    tape = Image.new("RGBA", (tape_w, tape_h), (255, 250, 220, 160))
    tdraw = ImageDraw.Draw(tape)
    tdraw.rectangle([(0, 0), (tape_w, tape_h)], outline=(220, 210, 170, 120), width=1)
    tape = tape.rotate(3, resample=Image.Resampling.BICUBIC, expand=True)
    card.paste(tape, ((w - tape.width) // 2, -10), mask=tape.split()[-1])

    cutout = PaperCraftService.create_torn_cutout(
        card, PaperCutoutOptions(border_width=8, roughness=0.25, shadow=True, shadow_opacity=0.45)
    )
    if angle_deg != 0.0:
        cutout = cutout.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
    return cutout


@lru_cache(maxsize=8)
def get_cached_bg(theme: str) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    if theme == "editorial":
        bg_c1, bg_c2 = (24, 26, 30), (12, 14, 16)
    elif theme == "cinematic":
        bg_c1, bg_c2 = (14, 26, 32), (8, 12, 16)  # Deep teal
    elif theme == "finance_dark":
        bg_c1, bg_c2 = (12, 18, 28), (6, 9, 14)   # Modern dark navy
    else:
        bg_c1, bg_c2 = (20, 20, 22), (10, 10, 12)

    for y in range(0, HEIGHT, 4):
        rat = y / HEIGHT
        r = int(bg_c1[0] * (1 - rat) + bg_c2[0] * rat)
        g = int(bg_c1[1] * (1 - rat) + bg_c2[1] * rat)
        b = int(bg_c1[2] * (1 - rat) + bg_c2[2] * rat)
        draw.rectangle([(0, y), (WIDTH, y + 4)], fill=(r, g, b, 255))

    grain = PaperCraftService.generate_film_grain_texture(WIDTH, HEIGHT, intensity=0.035)
    return Image.alpha_composite(img, grain)


def make_canvas(theme: str, frame_num: int, total_frames: int, style_badge: str) -> Image.Image:
    bg = get_cached_bg(theme).copy()
    draw = ImageDraw.Draw(bg)
    t = frame_num / max(1, total_frames)

    # Grid lines
    pan_x = int(math.sin(t * math.pi) * 15)
    for x in range((pan_x % 120), WIDTH, 120):
        draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 12), width=1)
    for y in range(0, HEIGHT, 120):
        draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 12), width=1)

    # Top left style tag
    font_tag = get_font(15, bold=True)
    draw.text((70, 45), f"VOX STUDIO PRO // {style_badge.upper()}", font=font_tag, fill=(255, 220, 20, 230))
    # Frame counter
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 280, 45), f"FPS:30  FRAME:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 70))

    # Viewfinder border
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
    c_len = 20
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 200), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 200), width=3)

    return bg


def draw_headline_badge(canvas: Image.Image, headline: str, category: str, progress: float, bg_color: tuple[int, int, int] = (220, 32, 32)) -> None:
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    slide = ease_out_back(progress)
    x = int(-400 + (400 + 70) * slide)
    y = 70

    font_head = get_font(36, bold=True)
    bbox = draw.textbbox((x, y), headline, font=font_head)
    pad_x, pad_y = 20, 10
    draw.rectangle([(bbox[0] - pad_x, bbox[1] - pad_y), (bbox[2] + pad_x, bbox[3] + pad_y)], fill=(*bg_color, 245))
    draw.text((x, y), headline, font=font_head, fill=(255, 255, 255, 255))

    font_cat = get_font(16, bold=True)
    draw.text((x, y - 24), category.upper(), font=font_cat, fill=(255, 220, 20, 240))


def draw_fast_stamp(canvas: Image.Image, center: tuple[int, int], text: str, progress: float, color: tuple[int, int, int] = (210, 25, 25)) -> None:
    if progress <= 0:
        return
    stamp_scale = ease_out_back(progress)
    sw = int(220 * stamp_scale)
    sh = int(60 * stamp_scale)
    if sw < 10 or sh < 10:
        return

    simg = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(simg)
    sdraw.rectangle([(0, 0), (sw - 1, sh - 1)], outline=(*color, 230), width=4)
    sfont = get_font(int(22 * stamp_scale), bold=True)
    sdraw.text((sw // 2, sh // 2), text, font=sfont, fill=(*color, 230), anchor="mm")
    simg = simg.rotate(-8, resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(simg, (center[0] - simg.width // 2, center[1] - simg.height // 2), mask=simg.split()[-1])


def draw_animated_arrow(canvas: Image.Image, start: tuple[int, int], end: tuple[int, int], progress: float, color: tuple[int, int, int] = (225, 35, 35), label: str = "") -> None:
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = max(0.0, min(1.0, progress))
    cur_x = start[0] + (end[0] - start[0]) * p
    cur_y = start[1] + (end[1] - start[1]) * p
    draw.line([start, (int(cur_x), int(cur_y))], fill=(*color, 240), width=8)

    if p > 0.15:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        arrow_len = 22
        p1 = (int(cur_x), int(cur_y))
        p2 = (int(cur_x + math.cos(angle + math.pi * 0.8) * arrow_len), int(cur_y + math.sin(angle + math.pi * 0.8) * arrow_len))
        p3 = (int(cur_x + math.cos(angle - math.pi * 0.8) * arrow_len), int(cur_y + math.sin(angle - math.pi * 0.8) * arrow_len))
        draw.polygon([p1, p2, p3], fill=(*color, 255))

    if label and p > 0.5:
        font = get_font(18, bold=True)
        draw.text(((start[0] + cur_x) / 2, (start[1] + cur_y) / 2 - 20), label, font=font, fill=(255, 230, 20, 240), anchor="mm")


# --------------------------------------------------------------------------- #
# Scene-specific Frame Renderers (All 3 Presets & Effects Showcase)
# --------------------------------------------------------------------------- #
def render_showcase_scene_001(f: int, n: int) -> Image.Image:
    """Scene 1: Preset Editorial Collage — Paper Tape, Archival Photo, Torn Edges."""
    img = make_canvas("editorial", f, n, "PRESET 01: EDITORIAL COLLAGE")
    t = f / n
    draw_headline_badge(img, "PRESET 01: EDITORIAL COLLAGE", "PHONG CÁCH BÁO CHÍ & TƯ LIỆU", min(1.0, t * 4.0))

    # Left: Archival Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 500) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_001_collage.png"), 540, 440, "TƯ LIỆU: BÁO CHÍ LỊCH SỬ 1930s", -3.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Tactile Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    c_y = int(-300 + (300 + 560) * c_prog)
    if c_prog > 0:
        card = get_cached_card_base(
            620, 450,
            "CẮT DÁN & BĂNG DÍNH THỦ CÔNG", "TÍNH NĂNG ĐỒ HỌA VOX",
            (
                "• Tự động tách nền nhân vật qua rembg",
                "• Viền xé giấy thủ công (Torn Paper Cutout)",
                "• Băng dính trong suốt & bóng đổ nổi 3D",
                "• Lưới tọa độ quân sự & hạt phim vintage",
            ),
            210, 30, 30, 2.5
        )
        img.paste(card, (1340 - card.width // 2, c_y - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1480, c_y + 120), "VOX STYLE", stamp_p)

    return img


def render_showcase_scene_002(f: int, n: int) -> Image.Image:
    """Scene 2: Highlighter & Red Stamp — Live fluorescent highlighter sweep."""
    img = make_canvas("editorial", f, n, "HIỆU ỨNG DẠ QUANG & MỘC ĐỎ")
    t = f / n
    draw_headline_badge(img, "HIỆU ỨNG: DẠ QUANG & DẤU MỘC", "TRÍCH DẪN VĂN KIỆN LỊCH SỬ", min(1.0, t * 4.0))

    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_002_highlighter.png"), 520, 440, "TƯ LIỆU: VĂN KIỆN PHÁP LÝ", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    doc_prog = ease_out_back(min(1.0, max(0.0, (t - 0.15) * 3.0)))
    doc_y = int(1200 - 640 * doc_prog)
    if doc_prog > 0:
        card = get_cached_card_base(
            680, 480,
            "QUÉT DẠ QUANG THEO GIỌNG ĐỌC", "VĂN KIỆN & BẰNG CHỨNG",
            (
                "DÒNG 1: QUÉT DẠ QUANG VÀNG TỰ ĐỘNG THEO NỘI DUNG",
                "DÒNG 2: Nhấn mạnh các từ khóa đắt giá trong kịch bản",
                "DÒNG 3: Dấu mộc đỏ dập sập xuống màn hình tạo điểm nhấn",
                "DÒNG 4: Tự động căn chỉnh lề an toàn chống tràn chữ",
            ),
            190, 30, 30, 2.0
        )
        img.paste(card, (1320 - card.width // 2, doc_y - card.height // 2), mask=card.split()[-1])

        # Live highlighter sweep over line 1
        hl_prog = min(1.0, max(0.0, (t - 0.35) * 2.2))
        if hl_prog > 0:
            box = (1030, doc_y - 100, int(1030 + 580 * hl_prog), doc_y - 70)
            img = DocumentHighlighterService.apply_highlight_sweep(
                img, box, progress=1.0, options=HighlightOptions(color_name="yellow", opacity=0.55)
            )

        stamp_prog = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1480, doc_y + 140), "XÁC THỰC", stamp_prog)

    return img


def render_showcase_scene_003(f: int, n: int) -> Image.Image:
    """Scene 3: Preset Cinematic Documentary — Widescreen 2.35:1 letterbox, Deep Teal, Flare."""
    img = make_canvas("cinematic", f, n, "PRESET 02: CINEMATIC DOCUMENTARY")
    t = f / n
    draw_headline_badge(img, "PRESET 02: CINEMATIC DOCUMENTARY", "ĐIỆN ẢNH & CHIỀU SÂU THẤU KÍNH", min(1.0, t * 4.0), bg_color=(20, 120, 160))

    # Center cinematic photo plate
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_003_cinematic.png"), 780, 520, "BBC / NATGEO DOCUMENTARY STYLE", 0.0)
        img.paste(plate, (960 - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Left Callout Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            440, 360,
            "TÔNG MÀU DEEP TEAL", "ĐẶC TRƯNG ĐIỆN ẢNH",
            (
                "• Ánh sáng thấu kính góc rộng",
                "• Chiều sâu Parallax 2.5D",
                "• Khung hình tỷ lệ điện ảnh",
            ),
            18, 100, 130, -3.0
        )
        img.paste(card, (340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])

    # Widescreen cinematic letterbox bars (Top & Bottom black bars)
    draw = ImageDraw.Draw(img)
    bar_h = 75
    draw.rectangle([(0, 0), (WIDTH, bar_h)], fill=(0, 0, 0, 255))
    draw.rectangle([(0, HEIGHT - bar_h), (WIDTH, HEIGHT)], fill=(0, 0, 0, 255))

    return img


def render_showcase_scene_004(f: int, n: int) -> Image.Image:
    """Scene 4: Tactical Map & Strategic Radar — Growing vector arrows & radar blips."""
    img = make_canvas("cinematic", f, n, "BẢN ĐỒ TÁC CHIẾN CHIẾN LƯỢC")
    t = f / n
    draw_headline_badge(img, "HIỆU ỨNG: BẢN ĐỒ CHIẾN LƯỢC", "MŨI TÊN TÁC CHIẾN & RADAR", min(1.0, t * 4.0), bg_color=(20, 120, 160))

    # Left: AI Tactical map plate
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 480) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_004_tactical_map.png"), 520, 440, "TƯ LIỆU: BẢN ĐỒ TÁC CHIẾN", -2.5)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Dynamic Tactical Map Board
    draw = ImageDraw.Draw(img)
    map_x0, map_y0, map_x1, map_y1 = 780, 260, 1800, 860
    draw.rectangle([(map_x0, map_y0), (map_x1, map_y1)], fill=(16, 24, 30, 240), outline=(40, 140, 180, 220), width=2)
    font_map = get_font(20, bold=True)
    draw.text((map_x0 + 20, map_y0 + 20), "TRUNG TÂM CHỈ HUY CHIẾN LƯỢC TOÀN CẦU", font=font_map, fill=(120, 220, 240, 240))

    base_a = (940, 460)
    target_b = (1620, 460)
    base_c = (940, 720)
    target_d = (1620, 720)

    draw.ellipse([(base_a[0] - 10, base_a[1] - 10), (base_a[0] + 10, base_a[1] + 10)], fill=(255, 60, 60, 255))
    draw.text((base_a[0], base_a[1] - 25), "CĂN CỨ ALFA", font=font_map, fill=(255, 255, 255, 255), anchor="mm")

    draw.ellipse([(target_b[0] - 10, target_b[1] - 10), (target_b[0] + 10, target_b[1] + 10)], fill=(255, 220, 20, 255))
    draw.text((target_b[0], target_b[1] - 25), "MỤC TIÊU BRAVO", font=font_map, fill=(255, 220, 20, 255), anchor="mm")

    arrow_p = min(1.0, max(0.0, (t - 0.2) * 2.2))
    draw_animated_arrow(img, (base_a[0] + 15, base_a[1]), (target_b[0] - 15, target_b[1]), arrow_p, color=(255, 50, 50), label="TIẾN CÔNG")
    draw_animated_arrow(img, (base_c[0] + 15, base_c[1]), (target_d[0] - 15, target_d[1]), arrow_p, color=(40, 180, 240), label="PHẢN KÍCH")

    # Pulsing radar rings
    if arrow_p >= 0.8:
        ring_r = int(25 + math.sin(t * 20) * 15)
        draw.ellipse([(target_b[0] - ring_r, target_b[1] - ring_r), (target_b[0] + ring_r, target_b[1] + ring_r)], outline=(255, 50, 50, 200), width=3)

    return img


def render_showcase_scene_005(f: int, n: int) -> Image.Image:
    """Scene 5: Preset Financial & Tech Minimal — Animated Financial Line Charts & Candlestick."""
    img = make_canvas("finance_dark", f, n, "PRESET 03: FINANCIAL & TECH MINIMAL")
    t = f / n
    draw_headline_badge(img, "PRESET 03: FINANCIAL MINIMAL", "BIỂU ĐỒ NẾN & ĐỒ THỊ TÀI CHÍNH", min(1.0, t * 4.0), bg_color=(10, 140, 80))

    # Left: AI Trading Terminal Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 480) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_005_financial_chart.png"), 520, 440, "TRADING DESK & DATA TERMINAL", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Live Animated Financial Line Graph
    draw = ImageDraw.Draw(img)
    gx0, gy0, gx1, gy1 = 780, 260, 1800, 860
    draw.rectangle([(gx0, gy0), (gx1, gy1)], fill=(10, 16, 24, 245), outline=(20, 180, 100, 200), width=2)

    font_title = get_font(22, bold=True)
    draw.text((gx0 + 25, gy0 + 25), "TỶ SUẤT SINH LỜI & TĂNG TRƯỞNG DANH MỤC (+340%)", font=font_title, fill=(50, 255, 140, 255))

    # Grid inside chart
    for cy in range(gy0 + 80, gy1 - 40, 60):
        draw.line([(gx0 + 20, cy), (gx1 - 20, cy)], fill=(255, 255, 255, 20), width=1)

    # Animated green growth curve
    curve_p = min(1.0, max(0.0, (t - 0.15) * 1.8))
    chart_w = (gx1 - gx0) - 80
    chart_h = (gy1 - gy0) - 140

    num_pts = int(120 * curve_p)
    if num_pts > 2:
        points = []
        for i in range(num_pts):
            norm_x = i / 120.0
            # Upward exponential curve with organic market volatility
            norm_y = 0.2 + 0.65 * math.pow(norm_x, 1.4) + math.sin(norm_x * 16) * 0.04
            px = gx0 + 40 + int(norm_x * chart_w)
            py = gy1 - 50 - int(norm_y * chart_h)
            points.append((px, py))

        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=(50, 255, 140, 255), width=5)

        # Pulse circle at current point
        last_pt = points[-1]
        draw.ellipse([(last_pt[0] - 8, last_pt[1] - 8), (last_pt[0] + 8, last_pt[1] + 8)], fill=(255, 255, 255, 255))
        font_val = get_font(18, bold=True)
        draw.text((last_pt[0], last_pt[1] - 25), f"${int(curve_p * 340)}k", font=font_val, fill=(50, 255, 140, 255), anchor="mm")

    return img


def render_showcase_scene_006(f: int, n: int) -> Image.Image:
    """Scene 6: Rolling Metric Counters & Vault — $128,500,000+ rolling odometer."""
    img = make_canvas("finance_dark", f, n, "ĐỒNG HỒ SỐ LIỆU ODIMETER")
    t = f / n
    draw_headline_badge(img, "HIỆU ỨNG: ROLLING ODIMETER", "SỐ LIỆU TĂNG TRƯỞNG LIVE", min(1.0, t * 4.0), bg_color=(10, 140, 80))

    # Top: Rolling Odometer Counter
    count_p = ease_out_cubic(min(1.0, t * 2.5))
    cash = int(128500000 * count_p)
    cash_str = f"${cash:,}".replace(",", ".") + "+"

    draw = ImageDraw.Draw(img)
    font_cash = get_font(78, bold=True)
    draw.text((WIDTH // 2, 290), cash_str, font=font_cash, fill=(50, 255, 140, 255), anchor="mm")

    font_sub_cash = get_font(24, bold=True)
    draw.text((WIDTH // 2, 345), "TỔNG DÒNG TIỀN GIAO DỊCH TRONG KỲ", font=font_sub_cash, fill=(255, 255, 255, 240), anchor="mm")

    # Animated neon underline
    under_p = min(1.0, max(0.0, (t - 0.2) * 3.0))
    if under_p > 0:
        uw = int(720 * under_p)
        draw.line([(WIDTH // 2 - uw // 2, 375), (WIDTH // 2 + uw // 2, 375)], fill=(50, 255, 140, 240), width=5)

    # Bottom Left: AI Gold Vault Photo
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.3) * 3.0)))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_006_tech_vault.png"), 560, 380, "GOLD BULLION RESERVE VAULT", -2.0)
        img.paste(plate, (480 - plate.width // 2, 690 - plate.height // 2), mask=plate.split()[-1])

    # Bottom Right: Financial Stats Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            640, 380,
            "BÁO CÁO TĂNG TRƯỞNG KINH TẾ", "CHỈ SỐ TÀI CHÍNH",
            (
                "• Lợi nhuận ròng: +284.5% so với cùng kỳ",
                "• Tốc độ tăng trưởng doanh thu: 14.8x",
                "• Hiệu suất sử dụng vốn: Đạt đỉnh lịch sử",
            ),
            20, 140, 80, 2.0
        )
        img.paste(card, (1380 - card.width // 2, 690 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1540, 780), "LỢI NHUẬN", stamp_p, color=(20, 160, 80))

    return img


def render_showcase_scene_007(f: int, n: int) -> Image.Image:
    """Scene 7: Split-Screen Comparison & Album Shuffle — Before vs After."""
    img = make_canvas("editorial", f, n, "SO SÁNH & XÁO TRỘN ALBUM")
    t = f / n
    draw_headline_badge(img, "TÍNH NĂNG: SO SÁNH ĐỐI LẬP", "CHIA ĐÔI MÀN HÌNH & XÁO TRỘN", min(1.0, t * 4.0))

    # Center dividing line
    draw = ImageDraw.Draw(img)
    split_p = ease_out_cubic(min(1.0, t * 3.0))
    split_h = int(HEIGHT * split_p)
    draw.line([(WIDTH // 2, (HEIGHT - split_h) // 2), (WIDTH // 2, (HEIGHT + split_h) // 2)], fill=(220, 40, 40, 200), width=4)

    # Left: Vintage Industrial Photo
    p1_prog = ease_out_back(min(1.0, t * 3.0))
    if p1_prog > 0:
        plate1 = get_cached_photo_plate(str(IMAGES_DIR / "scene_007_split_album.png"), 580, 450, "GIAI ĐOẠN 1: CỔ ĐIỂN", -2.5)
        img.paste(plate1, (480 - plate1.width // 2, 560 - plate1.height // 2), mask=plate1.split()[-1])
        stamp_p1 = min(1.0, max(0.0, (t - 0.5) * 4.0))
        draw_fast_stamp(img, (600, 680), "QUÁ KHỨ", stamp_p1)

    # Right: High-tech Modern Card
    c2_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if c2_prog > 0:
        card2 = get_cached_card_base(
            620, 450,
            "GIAI ĐOẠN 2: TỰ ĐỘNG HÓA", "BƯỚC CHUYỂN MÌNH",
            (
                "• Ứng dụng trí tuệ nhân tạo toàn diện",
                "• Rút ngắn 90% thời gian sản xuất video",
                "• Kết hợp chuyển động đa lớp thông minh",
                "• Xuất bản tự động chất lượng phát sóng",
            ),
            40, 110, 190, 2.5
        )
        img.paste(card2, (1420 - card2.width // 2, 560 - card2.height // 2), mask=card2.split()[-1])
        stamp_p2 = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1560, 680), "HIỆN TẠI", stamp_p2, color=(30, 110, 190))

    return img


def render_showcase_scene_008(f: int, n: int) -> Image.Image:
    """Scene 8: Master Conclusion & Pipeline Overview."""
    img = make_canvas("cinematic", f, n, "VOX STUDIO PRODUCTION PIPELINE")
    t = f / n
    draw_headline_badge(img, "VOX STUDIO: PIPELINE HOÀN HẢO", "SẢN XUẤT VIDEO TỰ ĐỘNG", min(1.0, t * 4.0), bg_color=(190, 30, 30))

    # Top: Master Conclusion Card
    c_prog = ease_out_back(min(1.0, t * 3.0))
    if c_prog > 0:
        draw = ImageDraw.Draw(img)
        font_gold = get_font(52, bold=True)
        draw.text((WIDTH // 2, 280), "100% AUTOMATED VIDEO PIPELINE", font=font_gold, fill=(255, 220, 20, 255), anchor="mm")
        font_sub = get_font(22, bold=True)
        draw.text((WIDTH // 2, 335), "TỰ ĐỘNG HÓA TOÀN TRÌNH: STORYBOARD -> VOICE -> MOTION -> FINAL MP4", font=font_sub, fill=(255, 255, 255, 240), anchor="mm")

    # Bottom Left: Media Newsroom Plate
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_008_conclusion.png"), 580, 420, "VOX STUDIO BROADCAST ENGINE", -2.0)
        img.paste(plate, (480 - plate.width // 2, 680 - plate.height // 2), mask=plate.split()[-1])

    # Bottom Right: Acceptance Summary Card
    card_prog = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 3.0)))
    if card_prog > 0:
        card = get_cached_card_base(
            640, 420,
            "SẴN SÀNG SẢN XUẤT HÀNG LOẠT", "NGHIỆM THU TÍNH NĂNG",
            (
                "• 3 Style Presets: Editorial / Cinema / Finance",
                "• 12 Motion Templates chuyên sâu",
                "• Auto-SFX & Foley Design đồng bộ",
                "• Tách nền AI rembg & viền xé giấy thủ công",
            ),
            200, 30, 30, 2.0
        )
        img.paste(card, (1380 - card.width // 2, 680 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1540, 790), "HOÀN TẤT", stamp_p)

    return img


SCENE_RENDERERS = [
    render_showcase_scene_001,
    render_showcase_scene_002,
    render_showcase_scene_003,
    render_showcase_scene_004,
    render_showcase_scene_005,
    render_showcase_scene_006,
    render_showcase_scene_007,
    render_showcase_scene_008,
]


SCENES_METADATA = [
    {
        "id": "scene_001",
        "narration": "Chào mừng anh yêu đến với hệ thống Vox Studio. Đây là phong cách Editorial Collage với ảnh tư liệu dán băng dính và viền xé giấy thủ công.",
        "template": "01_subject_slide_headline_pop",
    },
    {
        "id": "scene_002",
        "narration": "Hệ thống hỗ trợ quét bút dạ quang vàng chạy theo thời gian thực trên các dòng văn kiện, kết hợp dấu mộc đỏ dập sập xuống màn hình.",
        "template": "07_document_highlight",
    },
    {
        "id": "scene_003",
        "narration": "Phong cách Cinematic Documentary mang chiều sâu điện ảnh, tông màu Deep Teal ấm áp, ống kính góc rộng và vệt sáng thấu kính chuyên nghiệp.",
        "template": "09_cutout_parallax",
    },
    {
        "id": "scene_004",
        "narration": "Bản đồ tác chiến quân sự và địa chính trị với các mũi tên chiến lược tự động vẽ đâm xuyên mục tiêu cùng vòng tròn radar nhấp nháy phát sáng.",
        "template": "03_map_pan_marker_pulse",
    },
    {
        "id": "scene_005",
        "narration": "Phong cách Minimal Tech và Tài chính hiện đại: đồ thị chứng khoán tăng trưởng, biểu đồ cột nhảy động và giao diện tối giản siêu sắc nét.",
        "template": "05_stat_number_count",
    },
    {
        "id": "scene_006",
        "narration": "Đồng hồ số liệu nhảy tự động tốc độ cao từ không lên hàng trăm triệu đô la, phục vụ tối ưu cho các video ngách tài chính và kiếm tiền.",
        "template": "05_stat_number_count",
    },
    {
        "id": "scene_007",
        "narration": "Chia đôi màn hình so sánh đối lập hoặc xáo trộn album ảnh đa lớp, cho phép phân tích sự kiện trước sau một cách trực quan và mạch lạc.",
        "template": "04_before_after_split",
    },
    {
        "id": "scene_008",
        "narration": "Tất cả các preset, hiệu ứng đồ họa, âm thanh và phụ đề đều được kết xuất tự động chỉ trong vài giây, sẵn sàng cho sản xuất video đỉnh cao!",
        "template": "12_conclusion_lockup",
    },
]


def main() -> None:
    logger.info("=== Starting Ultimate Multi-Preset Showcase Video Generation ===")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = PROJECT_DIR / "scenes"
    audio_dir = PROJECT_DIR / "audio"
    final_dir = PROJECT_DIR / "final"
    for d in (scenes_dir, audio_dir, final_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Load Piper Voice
    logger.info("1. Loading Piper TTS ('Ngọc Huyền')...")
    voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))

    scene_mp4s: list[Path] = []
    durations_ms: list[int] = []
    subtitle_entries: list[SubtitleEntry] = []
    current_time_ms = 0
    sfx_service = AutoSFXService()

    for idx, scene in enumerate(SCENES_METADATA):
        scene_id = scene["id"]
        narration = scene["narration"]
        logger.info(f"--- Rendering Showcase Scene: {scene_id} [{idx + 1}/8] ---")

        # Synthesize Voice
        voice_wav = audio_dir / f"{scene_id}_voice.wav"
        if not voice_wav.is_file():
            with wave.open(str(voice_wav), "wb") as wf:
                voice.synthesize_wav(narration, wf)

        with wave.open(str(voice_wav), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_ms = max(5200, int((frames / float(rate)) * 1000) + 600)

        durations_ms.append(duration_ms)
        total_scene_frames = int(round(duration_ms / 1000.0 * FPS))

        subtitle_entries.append(
            SubtitleEntry(
                index=idx + 1,
                start_ms=current_time_ms + 120,
                end_ms=current_time_ms + duration_ms - 200,
                text=narration,
            )
        )
        current_time_ms += duration_ms

        # Generate SFX Track
        sfx_events = AutoSFXService.derive_scene_sfx_events(
            scene["template"], duration_ms, transition_out="paper_tear" if idx == 7 else "wipe_left"
        )
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

        # Render Dynamic Frame-by-Frame Video
        silent_scene_mp4 = scenes_dir / f"{scene_id}_silent.mp4"
        scene_mp4 = scenes_dir / f"{scene_id}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "rgba",
            "-r", str(FPS),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "18",
            str(silent_scene_mp4),
        ]

        t0 = time.time()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        renderer_fn = SCENE_RENDERERS[idx]

        for f in range(total_scene_frames):
            frame_img = renderer_fn(f, total_scene_frames)
            proc.stdin.write(frame_img.tobytes())

        proc.stdin.close()
        proc.wait()
        t1 = time.time()

        # Mux audio onto silent scene MP4
        SceneAudioMuxer().mux(silent_scene_mp4, scene_audio_wav, scene_mp4, fps=30)
        logger.info(f"Rendered {total_scene_frames} frames in {t1 - t0:.2f}s -> {scene_mp4}")
        scene_mp4s.append(scene_mp4)

    # Full Subtitles
    srt_path = final_dir / "subtitles.srt"
    srt_content = entries_to_srt(subtitle_entries)
    srt_path.write_text(srt_content, encoding="utf-8")

    # Master Audio track
    audio_concat_list = audio_dir / "audio_concat.txt"
    concat_lines = [f"file '{Path(audio_dir / (s['id'] + '_audio.wav')).resolve().as_posix()}'" for s in SCENES_METADATA]
    audio_concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    full_voice_wav = audio_dir / "full_voice_sfx.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
        "-c:a", "pcm_s16le", str(full_voice_wav)
    ], check=True, capture_output=True)

    # Procedural Cinematic BGM
    total_dur_ms = sum(durations_ms)
    logger.info(f"Total video duration: {total_dur_ms / 1000.0:.2f}s")
    bgm_wav = audio_dir / "documentary_bgm.wav"
    dur_s = total_dur_ms / 1000.0 + 2.0
    bgm_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc=sin(2*PI*55*t)*0.15 + sin(2*PI*110*t)*0.08 + sin(2*PI*220*t)*0.03:d={dur_s:.3f}:s=48000",
        "-af", f"lowpass=f=400,volume=-18dB,afade=t=in:d=2.0,afade=t=out:st={dur_s - 2.5:.2f}:d=2.5",
        "-c:a", "pcm_s16le",
        str(bgm_wav),
    ]
    subprocess.run(bgm_cmd, check=True, capture_output=True)

    master_audio_wav = audio_dir / "master_audio.wav"
    mix_cmd = [
        "ffmpeg", "-y",
        "-i", str(full_voice_wav),
        "-i", str(bgm_wav),
        "-filter_complex", "[0:a]volume=1.0dB[v];[1:a]volume=-18dB[b];[v][b]amix=inputs=2:duration=first:normalize=0[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(master_audio_wav),
    ]
    subprocess.run(mix_cmd, check=True, capture_output=True)

    # Final Concat Composition
    final_mp4 = final_dir / "vox_studio_all_presets_showcase.mp4"
    composer = FinalComposer()
    output_path, probe = composer.compose(
        scenes=scene_mp4s,
        audio=master_audio_wav,
        output=final_mp4,
        fps=30,
        width=1920,
        height=1080,
        tolerance_frames=3,
    )

    logger.info(f"=== Video Successfully Composed: {output_path} ===")
    logger.info(f"Probe: {probe.width}x{probe.height} @ {probe.fps}fps, Duration: {probe.duration_ms}ms, PixFmt: {probe.pix_fmt}")
    print(f"\n[DONE] Video Tổng Hợp Tất Cả Preset & Hiệu Ứng hoàn tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
