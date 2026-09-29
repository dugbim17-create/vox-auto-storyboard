"""Production script to generate a 60-second Vox documentary: 'Bác Hồ Ra Đi Tìm Đường Cứu Nước (1911 - 1941)'.

Applies all Vox Studio style presets and motion graphics:
- Preset 1: Editorial Collage (Torn Paper Cutout, Archival Photo Plates, Tape, Red Stamp, Film Grain)
- Preset 2: Document & Live Highlighter (Fluorescent Marker Sweep over archival records)
- Preset 3: Tactical World Navigation Map (Animated Maritime Sea Route from Saigon to Marseille)
- Preset 4: Cinematic Documentary (Deep Teal/Amber Grading, Widescreen 2.35:1 Letterbox, Parallax Depth)
- Preset 5: French Police Archive Dossier (Versailles 1919 8-Point Claim, Le Paria Newspaper, Hand-drawn Circle)
- Preset 6: Minimal Metric Rolling Counter (30 Năm Bôn Ba, 28 Quốc Gia, 4 Châu Lục)
- Preset 7: Split-Screen Comparison (1920 Lenin Theses & Tours Congress, "Chân Lý" Stamp)
- Preset 8: Master Conclusion Lockup (1941 Pac Bo Return, Milestone 108, "Độc Lập" Stamp)
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
logger = logging.getLogger("bac_ho_vox_doc")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_bac_ho_60s")
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
        bg_c1, bg_c2 = (26, 24, 20), (14, 12, 10)  # Archival warm dark sepia
    elif theme == "cinematic":
        bg_c1, bg_c2 = (14, 24, 30), (8, 12, 16)   # Deep Teal
    elif theme == "minimal":
        bg_c1, bg_c2 = (18, 20, 26), (10, 11, 15)  # Modern dark navy
    else:
        bg_c1, bg_c2 = (30, 20, 16), (14, 9, 8)    # Crimson red-tinted dark

    for y in range(0, HEIGHT, 4):
        rat = y / HEIGHT
        r = int(bg_c1[0] * (1 - rat) + bg_c2[0] * rat)
        g = int(bg_c1[1] * (1 - rat) + bg_c2[1] * rat)
        b = int(bg_c1[2] * (1 - rat) + bg_c2[2] * rat)
        draw.rectangle([(0, y), (WIDTH, y + 4)], fill=(r, g, b, 255))

    grain = PaperCraftService.generate_film_grain_texture(WIDTH, HEIGHT, intensity=0.04)
    return Image.alpha_composite(img, grain)


def make_canvas(theme: str, frame_num: int, total_frames: int, style_badge: str) -> Image.Image:
    bg = get_cached_bg(theme).copy()
    draw = ImageDraw.Draw(bg)
    t = frame_num / max(1, total_frames)

    pan_x = int(math.sin(t * math.pi) * 15)
    for x in range((pan_x % 120), WIDTH, 120):
        draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, 12), width=1)
    for y in range(0, HEIGHT, 120):
        draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, 12), width=1)

    # Top center style tag
    font_tag = get_font(15, bold=True)
    draw.text((WIDTH // 2, 52), f"LỊCH SỬ VIỆT NAM // {style_badge.upper()}", font=font_tag, fill=(255, 220, 20, 230), anchor="mm")
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 320, 52), f"TƯ LIỆU LƯU TRỮ // KHUNG:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 70))

    # Viewfinder border
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
    c_len = 20
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 200), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 200), width=3)

    return bg


def draw_headline_badge(canvas: Image.Image, headline: str, category: str, progress: float, bg_color: tuple[int, int, int] = (210, 35, 35)) -> None:
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


def draw_animated_circle(canvas: Image.Image, center: tuple[int, int], radius: int, progress: float, color: tuple[int, int, int] = (225, 35, 35), width: int = 4) -> None:
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = max(0.0, min(1.0, progress))
    cx, cy = center
    num_points = int(60 * p)
    if num_points < 2:
        return

    points = []
    for i in range(num_points):
        ang = (i / 60.0) * math.pi * 2.05 - math.pi / 2
        r_jitter = radius + math.sin(i * 0.6) * 3
        px = cx + math.cos(ang) * r_jitter
        py = cy + math.sin(ang) * (r_jitter * 0.75)
        points.append((px, py))

    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(*color, 230), width=width)


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
# Scene-specific Frame Renderers (Bác Hồ Ra Đi Tìm Đường Cứu Nước)
# --------------------------------------------------------------------------- #
def render_scene_001(f: int, n: int) -> Image.Image:
    """Scene 1: 05/06/1911 Bến Nhà Rồng — AI Photo of Nha Rong Harbor + Departure Card."""
    img = make_canvas("editorial", f, n, "BẾN NHÀ RỒNG 1911")
    t = f / n
    draw_headline_badge(img, "05/06/1911: BẾN NHÀ RỒNG", "KHỞI ĐẦU HÀNH TRÌNH CỨU NƯỚC", min(1.0, t * 4.0))

    # Left: AI Photo of Nha Rong Port & Latouche-Tréville Steamship
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 500) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_001_nha_rong.png"), 540, 440, "TƯ LIỆU: BẾN CẢNG SÀI GÒN 1911", -3.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Departure Note Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    c_y = int(-300 + (300 + 560) * c_prog)
    if c_prog > 0:
        card = get_cached_card_base(
            620, 450,
            "CON TÀU ĐÔ ĐỐC LATOUCHE-TRÉVILLE", "BƯỚC NGOẶT LỊCH SỬ",
            (
                "• Người thanh niên Nguyễn Tất Thành tròn 21 tuổi",
                "• Quyết tâm ra đi tìm con đường cứu dân, cứu nước",
                "• Rời Tổ quốc trên con tàu buôn của Pháp",
                "• Mở đầu hành trình 30 năm bôn ba vĩ đại",
            ),
            200, 35, 35, 2.5
        )
        img.paste(card, (1340 - card.width // 2, c_y - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1480, c_y + 120), "XUẤT PHÁT", stamp_p)

    return img


def render_scene_002(f: int, n: int) -> Image.Image:
    """Scene 2: Người phụ bếp Văn Ba — Maritime Registration Record + Live Highlighter."""
    img = make_canvas("editorial", f, n, "DANH XƯNG VĂN BA")
    t = f / n
    draw_headline_badge(img, "NGƯỜI PHỤ BẾP VĂN BA", "Ý CHÍ VƯỢT GIAN KHỔ", min(1.0, t * 4.0))

    # Left: AI Photo of maritime identity record
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_002_van_ba_doc.png"), 520, 440, "TƯ LIỆU: SỔ BỘ THUYỀN VIÊN", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Document with live highlighter sweep
    doc_prog = ease_out_back(min(1.0, max(0.0, (t - 0.15) * 3.0)))
    doc_y = int(1200 - 640 * doc_prog)
    if doc_prog > 0:
        card = get_cached_card_base(
            680, 480,
            "LAO ĐỘNG GIỮA ĐẠI DƯƠNG", "Ý CHÍ SẮT ĐÁ",
            (
                "DÒNG 1: CHẤP NHẬN LÀM PHỤ BẾP VỚI ĐÔI BÀN TAY TRẮNG",
                "DÒNG 2: Vượt qua sóng to gió lớn và công việc cực nhọc",
                "DÒNG 3: Luôn dành thời gian học ngoại ngữ và đọc sách",
                "DÒNG 4: Kiên định mục tiêu tối thượng: Tự do cho dân tộc",
            ),
            190, 30, 30, 2.0
        )
        img.paste(card, (1320 - card.width // 2, doc_y - card.height // 2), mask=card.split()[-1])

        # Live highlighter sweep over DÒNG 1
        hl_prog = min(1.0, max(0.0, (t - 0.35) * 2.2))
        if hl_prog > 0:
            box = (1030, doc_y - 100, int(1030 + 580 * hl_prog), doc_y - 70)
            img = DocumentHighlighterService.apply_highlight_sweep(
                img, box, progress=1.0, options=HighlightOptions(color_name="yellow", opacity=0.55)
            )

        stamp_prog = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1480, doc_y + 140), "DẤN THÂN", stamp_prog)

    return img


def render_scene_003(f: int, n: int) -> Image.Image:
    """Scene 3: Tactical World Sea Route Map — Dynamic Sea Route from Saigon to Marseille."""
    img = make_canvas("cinematic", f, n, "HẢI TRÌNH VẠN DẶM")
    t = f / n
    draw_headline_badge(img, "HẢI TRÌNH VẠN DẶM", "SAIGON -> MARSEILLE -> CHÂU ÂU", min(1.0, t * 4.0), bg_color=(20, 120, 160))

    # Left: AI Nautical Map Plate
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 480) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_003_sea_route_map.png"), 520, 440, "TƯ LIỆU: BẢN ĐỒ HẢI TRÌNH QUỐC TẾ", -2.5)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Dynamic Maritime Route Map Board
    draw = ImageDraw.Draw(img)
    map_x0, map_y0, map_x1, map_y1 = 780, 260, 1800, 860
    draw.rectangle([(map_x0, map_y0), (map_x1, map_y1)], fill=(16, 24, 30, 240), outline=(40, 140, 180, 220), width=2)
    font_map = get_font(20, bold=True)
    draw.text((map_x0 + 20, map_y0 + 20), "HẢI TRÌNH TÀU LATOUCHE-TRÉVILLE (1911)", font=font_map, fill=(120, 220, 240, 240))

    saigon = (1600, 680)
    singapore = (1420, 720)
    suez = (1180, 520)
    marseille = (920, 420)

    # Ports
    for pt, name in [(saigon, "SÀI GÒN"), (singapore, "SINGAPORE"), (suez, "KÊNH SUEZ"), (marseille, "MARSEILLE (PHÁP)")]:
        draw.ellipse([(pt[0] - 8, pt[1] - 8), (pt[0] + 8, pt[1] + 8)], fill=(255, 220, 20, 255))
        draw.text((pt[0], pt[1] - 22), name, font=font_map, fill=(255, 255, 255, 255), anchor="mm")

    # Animated Sea Route Arrow: Saigon -> Singapore -> Suez -> Marseille
    arrow_p = min(1.0, max(0.0, (t - 0.15) * 2.2))
    draw_animated_arrow(img, (saigon[0] - 15, saigon[1]), (marseille[0] + 15, marseille[1]), arrow_p, color=(40, 200, 240), label="HẢI TRÌNH VƯỢT BIỂN")

    # Pulsing beacon around Marseille
    if arrow_p >= 0.8:
        ring_r = int(25 + math.sin(t * 20) * 15)
        draw.ellipse([(marseille[0] - ring_r, marseille[1] - ring_r), (marseille[0] + ring_r, marseille[1] + ring_r)], outline=(255, 220, 20, 200), width=3)

    return img


def render_scene_004(f: int, n: int) -> Image.Image:
    """Scene 4: London & New York (1912 - 1917) — Cinematic Widescreen & Deep Teal Grading."""
    img = make_canvas("cinematic", f, n, "BÔN BA NĂM CHÂU")
    t = f / n
    draw_headline_badge(img, "LONDON & NEW YORK (1912-1917)", "THỰC TIỄN LAO ĐỘNG THẾ GIỚI", min(1.0, t * 4.0), bg_color=(20, 120, 160))

    # Center cinematic photo plate
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_004_london_paris.png"), 760, 520, "LONDON & PARIS NHỮNG NĂM 1910s", 0.0)
        img.paste(plate, (960 - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Left Callout Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            460, 380,
            "HÒA MÌNH VÀO ĐỜI SỐNG CÔNG NHÂN", "NGHIÊN CỨU THỰC TIỄN",
            (
                "• Làm thợ cào tuyết tại London",
                "• Làm thợ rửa ảnh tại Paris",
                "• Thấu hiểu bản chất chủ nghĩa tư bản",
                "• Nung nấu con đường giải phóng",
            ),
            18, 100, 130, -3.0
        )
        img.paste(card, (340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])

    # Widescreen cinematic letterbox bars
    draw = ImageDraw.Draw(img)
    bar_h = 75
    draw.rectangle([(0, 0), (WIDTH, bar_h)], fill=(0, 0, 0, 255))
    draw.rectangle([(0, HEIGHT - bar_h), (WIDTH, HEIGHT)], fill=(0, 0, 0, 255))

    return img


def render_scene_005(f: int, n: int) -> Image.Image:
    """Scene 5: 1919 Hội nghị Versailles & Báo Le Paria — French Archives & Red Stamp."""
    img = make_canvas("editorial", f, n, "HỘI NGHỊ VERSAILLES 1919")
    t = f / n
    draw_headline_badge(img, "1919: HỘI NGHỊ VERSAILLES", "BẢN YÊU SÁCH CỦA NHÂN DÂN AN NAM", min(1.0, t * 4.0))

    # Left: AI Photo of Le Paria Newspaper
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_005_le_paria_paper.png"), 520, 440, "TƯ LIỆU: BÁO NGƯỜI CÙNG KHỔ (LE PARIA)", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: 8-Point Claims Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            660, 470,
            "NGUYỄN ÁI QUỐC & TIẾNG VANG QUỐC TẾ", "ĐÒI QUYỀN BÌNH ĐẲNG",
            (
                "• Gửi Bản Yêu sách 8 điểm tới Hội nghị Versailles",
                "• Đòi quyền tự do, bình đẳng cho nhân dân Việt Nam",
                "• Sáng lập tờ báo 'Người Cùng Khổ' (Le Paria)",
                "• Thức tỉnh tinh thần đấu tranh của các dân tộc thuộc địa",
            ),
            200, 30, 30, 2.0
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1500, 680), "YÊU NƯỚC", stamp_p)

    # Red hand-drawn circle around 1919
    circle_p = min(1.0, max(0.0, (t - 0.7) * 3.5))
    if circle_p > 0:
        draw_animated_circle(img, (1340, 430), 105, circle_p, color=(255, 40, 40), width=5)

    return img


def render_scene_006(f: int, n: int) -> Image.Image:
    """Scene 6: Minimal Metric Odometer — 30 Năm Bôn Ba qua 28 Quốc Gia."""
    img = make_canvas("minimal", f, n, "THỐNG KÊ LỊCH SỬ 30 NĂM")
    t = f / n
    draw_headline_badge(img, "30 NĂM BÔN BA (1911-1941)", "HÀNH TRÌNH TÌM CHÂN LÝ", min(1.0, t * 4.0), bg_color=(20, 140, 90))

    # Top: Rolling Odometer Counter: 0 -> 30 Năm
    count_p = ease_out_cubic(min(1.0, t * 2.5))
    years = int(30 * count_p)
    year_str = f"{years} NĂM BÔN BA"

    draw = ImageDraw.Draw(img)
    font_big = get_font(78, bold=True)
    draw.text((WIDTH // 2, 290), year_str, font=font_big, fill=(255, 220, 20, 255), anchor="mm")

    font_sub_big = get_font(24, bold=True)
    draw.text((WIDTH // 2, 345), "ĐI QUA GẦN 30 QUỐC GIA • 4 CHÂU LỤC • 3 ĐẠI DƯƠNG", font=font_sub_big, fill=(255, 255, 255, 240), anchor="mm")

    # Animated neon underline
    under_p = min(1.0, max(0.0, (t - 0.2) * 3.0))
    if under_p > 0:
        uw = int(720 * under_p)
        draw.line([(WIDTH // 2 - uw // 2, 375), (WIDTH // 2 + uw // 2, 375)], fill=(50, 255, 140, 240), width=5)

    # Bottom Left: Study Desk & Books Plate
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.3) * 3.0)))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_006_study_books.png"), 560, 380, "TƯ LIỆU: BÀN NGHIÊN CỨU LÝ LUẬN", -2.0)
        img.paste(plate, (480 - plate.width // 2, 690 - plate.height // 2), mask=plate.split()[-1])

    # Bottom Right: Research Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            640, 380,
            "ĐÚC KẾT KINH NGHIỆM CÁCH MẠNG", "NGHIÊN CỨU LÝ LUẬN",
            (
                "• Nghiên cứu Cách mạng Mỹ 1776 & Pháp 1789",
                "• Tiếp thu Cách mạng Tháng Mười Nga 1917",
                "• Khẳng định con đường cứu nước của dân tộc",
            ),
            20, 140, 80, 2.0
        )
        img.paste(card, (1380 - card.width // 2, 690 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1540, 780), "ĐÚC KẾT", stamp_p, color=(20, 160, 80))

    return img


def render_scene_007(f: int, n: int) -> Image.Image:
    """Scene 7: 1920 Luận Cương Lênin & Đại Hội Tours — Split-Screen Comparison."""
    img = make_canvas("editorial", f, n, "BƯỚC NGOẶT 1920")
    t = f / n
    draw_headline_badge(img, "1920: TÌM THẤY CON ĐƯỜNG CỨU NƯỚC", "LUẬN CƯƠNG LÊNIN & ĐẠI HỘI TOURS", min(1.0, t * 4.0))

    # Center dividing line
    draw = ImageDraw.Draw(img)
    split_p = ease_out_cubic(min(1.0, t * 3.0))
    split_h = int(HEIGHT * split_p)
    draw.line([(WIDTH // 2, (HEIGHT - split_h) // 2), (WIDTH // 2, (HEIGHT + split_h) // 2)], fill=(220, 40, 40, 200), width=4)

    # Left: Tours Congress Photo
    p1_prog = ease_out_back(min(1.0, t * 3.0))
    if p1_prog > 0:
        plate1 = get_cached_photo_plate(str(IMAGES_DIR / "scene_007_tours_congress.png"), 580, 450, "TƯ LIỆU: ĐẠI HỘI TOURS THÁNG 12/1920", -2.5)
        img.paste(plate1, (480 - plate1.width // 2, 560 - plate1.height // 2), mask=plate1.split()[-1])
        stamp_p1 = min(1.0, max(0.0, (t - 0.5) * 4.0))
        draw_fast_stamp(img, (600, 680), "LỰA CHỌN", stamp_p1)

    # Right: Lenin Theses Card
    c2_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if c2_prog > 0:
        card2 = get_cached_card_base(
            640, 450,
            "LUẬN CƯƠNG VỀ VẤN ĐỀ DÂN TỘC", "CHÂN LÝ GIẢI PHÓNG",
            (
                "• 'Hỡi đồng bào bị đọa đày đau khổ! Đây là cái cần thiết cho chúng ta!'",
                "• Gắn cách mạng giải phóng dân tộc với vô sản",
                "• Đặt nền tảng thành lập Đảng Cộng sản Việt Nam",
                "• Xác định con đường độc lập dân tộc gắn với CNXH",
            ),
            200, 30, 30, 2.5
        )
        img.paste(card2, (1420 - card2.width // 2, 560 - card2.height // 2), mask=card2.split()[-1])
        stamp_p2 = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1560, 680), "CHÂN LÝ", stamp_p2, color=(210, 25, 25))

    return img


def render_scene_008(f: int, n: int) -> Image.Image:
    """Scene 8: 1941 Trở về Pác Bó — Master Conclusion Lockup."""
    img = make_canvas("crimson", f, n, "TRỞ VỀ TỔ QUỐC 1941")
    t = f / n
    draw_headline_badge(img, "MÙA XUÂN 1941: VỀ VỚI TỔ QUỐC", "PÁC BÓ - CAO BẰNG (CỘT MỐC 108)", min(1.0, t * 4.0), bg_color=(200, 30, 30))

    # Top: Master Banner
    c_prog = ease_out_back(min(1.0, t * 3.0))
    if c_prog > 0:
        draw = ImageDraw.Draw(img)
        font_gold = get_font(52, bold=True)
        draw.text((WIDTH // 2, 280), "ĐỘC LẬP - TỰ DO - HẠNH PHÚC", font=font_gold, fill=(255, 220, 20, 255), anchor="mm")
        font_sub = get_font(22, bold=True)
        draw.text((WIDTH // 2, 335), "30 NĂM BÔN BA VÌ SỰ NGHIỆP GIẢI PHÓNG DÂN TỘC VIỆT NAM", font=font_sub, fill=(255, 255, 255, 240), anchor="mm")

    # Bottom Left: Pac Bo Mountains Photo
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_008_pac_bo_return.png"), 580, 420, "TƯ LIỆU: NON NƯỚC PÁC BÓ CAO BẰNG", -2.0)
        img.paste(plate, (480 - plate.width // 2, 680 - plate.height // 2), mask=plate.split()[-1])

    # Bottom Right: Final Conclusion Card
    card_prog = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 3.0)))
    if card_prog > 0:
        card = get_cached_card_base(
            640, 420,
            "KHAI SINH NƯỚC VIỆT NAM ĐỘC LẬP", "THẮNG LỢI VẺ VANG",
            (
                "• 28/01/1941: Bác Hồ trở về tại Cột mốc 108",
                "• Trực tiếp lãnh đạo Tổng khởi nghĩa Cách mạng Tháng Tám",
                "• Khai sinh nước Việt Nam Dân chủ Cộng hòa 1945",
                "• Bản hùng ca vĩ đại của tinh thần yêu nước Việt Nam",
            ),
            200, 30, 30, 2.0
        )
        img.paste(card, (1380 - card.width // 2, 680 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1540, 790), "ĐỘC LẬP", stamp_p)

    return img


SCENE_RENDERERS = [
    render_scene_001,
    render_scene_002,
    render_scene_003,
    render_scene_004,
    render_scene_005,
    render_scene_006,
    render_scene_007,
    render_scene_008,
]


SCENES_METADATA = [
    {
        "id": "scene_001",
        "narration": "Ngày 5 tháng 6 năm 1911, từ Bến Nhà Rồng, người thanh niên yêu nước Nguyễn Tất Thành bước lên con tàu Đô đốc Latouche-Tréville, bắt đầu hành trình tìm đường cứu nước.",
        "template": "01_subject_slide_headline_pop",
    },
    {
        "id": "scene_002",
        "narration": "Với đôi bàn tay trắng cùng tên gọi Văn Ba, Người chấp nhận làm phụ bếp, vượt qua muôn vàn gian khổ nơi đầu sóng ngọn gió giữa đại dương bao la.",
        "template": "07_document_highlight",
    },
    {
        "id": "scene_003",
        "narration": "Hải trình vạn dặm đưa Người qua ba đại dương, bốn châu lục, từ Singapore, Colombo, qua kênh đào Suez đến cảng Marseille của nước Pháp.",
        "template": "03_map_pan_marker_pulse",
    },
    {
        "id": "scene_004",
        "narration": "Những năm tháng bôn ba tại London và New York, Người vừa lao động kiếm sống, vừa hòa mình vào đời sống công nhân để thấu hiểu bản chất chủ nghĩa tư bản.",
        "template": "09_cutout_parallax",
    },
    {
        "id": "scene_005",
        "narration": "Năm 1919, với tên gọi Nguyễn Ái Quốc, Người gửi Bản Yêu sách của nhân dân An Nam tới Hội nghị Versailles, đòi quyền tự do bình đẳng cho dân tộc.",
        "template": "07_document_highlight",
    },
    {
        "id": "scene_006",
        "narration": "Tròn 30 năm bôn ba qua gần 30 quốc gia, Người đã đúc kết kinh nghiệm từ các cuộc cách mạng lớn trên thế giới để tìm ra con đường cứu nước đúng đắn.",
        "template": "05_stat_number_count",
    },
    {
        "id": "scene_007",
        "narration": "Tháng 7 năm 1920, khi đọc Luận cương của Lênin, Người đã rơi lệ vì xúc động. Đây chính là chân lý giải phóng dân tộc: con đường cách mạng vô sản.",
        "template": "04_before_after_split",
    },
    {
        "id": "scene_008",
        "narration": "Mùa xuân năm 1941, Người trở về cột mốc 108 Pác Bó Cao Bằng, trực tiếp lãnh đạo cách mạng Việt Nam đi tới thắng lợi vẻ vang, giành lại độc lập tự do.",
        "template": "12_conclusion_lockup",
    },
]


def main() -> None:
    logger.info("=== Starting Bác Hồ Ra Đi Tìm Đường Cứu Nước (60s Vox Documentary) ===")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = PROJECT_DIR / "scenes"
    audio_dir = PROJECT_DIR / "audio"
    final_dir = PROJECT_DIR / "final"
    for d in (scenes_dir, audio_dir, final_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Load Piper Voice
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
        logger.info(f"--- Rendering Dynamic Vox Scene: {scene_id} [{idx + 1}/8] ---")

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

        # Render Dynamic Frame-by-Frame Video directly piped into FFmpeg
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
    final_mp4 = final_dir / "bac_ho_tim_duong_cuu_nuoc_60s.mp4"
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
    print(f"\n[DONE] Video Bác Hồ Ra Đi Tìm Đường Cứu Nước hoàn tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
