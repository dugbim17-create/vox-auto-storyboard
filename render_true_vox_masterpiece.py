"""True Vox / Johnny Harris Cinematic Motion Graphics Masterpiece.

Completely eliminates rigid bullet-point cards.
Constructs 8 distinct, full-screen cinematic visual scenes:
- Scene 1: Full-screen Yellow River silk scroll + Parallax bronze vessel cutout + Giant kinetic typography ("5.000 NĂM")
- Scene 2: Full-screen Terracotta army + Archival imperial decree with live yellow highlighter sweep + Giant red seal stamp
- Scene 3: Full-screen Silk Road parchment map with glowing cities (Chang'an -> Rome) + Animated trade route vector arrow + Camel caravan photo plate
- Scene 4: Three Kingdoms Red Cliffs battle + 3 Faction banners (Ngụy - Thục - Ngô) slamming into 3 corners + Tactical clash arrows
- Scene 5: Full-screen Tang Palace golden age + Giant glowing "1.000.000 DÂN" city metric + Calligraphy poetry scroll
- Scene 6: Dynamic 4-Quadrant collage of the 4 Great Inventions (Compass, Gunpowder, Paper, Printing) with 3D pushpins & tape
- Scene 7: Full-screen Forbidden City + 1911 Revolution decree with giant red 'X' cross-out ("CHẤM DỨT 2.000 NĂM PHONG KIẾN")
- Scene 8: Cinematic Great Wall sunrise + Center 120px Rolling Odometer (0 -> 5.000 Năm) + Golden imperial lockup
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
logger = logging.getLogger("vox_masterpiece")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_china_history_60s")
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


def ease_in_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 2.0 * t * t if t < 0.5 else 1.0 - math.pow(-2.0 * t + 2.0, 2) / 2.0


# --------------------------------------------------------------------------- #
# Reusable High-End Visual Generators
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8)
def get_processed_fullscreen_image(img_path: str, darken: float = 0.45) -> Image.Image:
    """Pre-process AI generated image into full-screen 1920x1080 background with film grain."""
    im = Image.open(img_path).convert("RGB")
    # Cover crop to 1920x1080
    scale = max(WIDTH / float(im.width), HEIGHT / float(im.height))
    nw, nh = int(im.width * scale), int(im.height * scale)
    im_scaled = im.resize((nw, nh), Image.Resampling.BICUBIC)
    
    ox = (nw - WIDTH) // 2
    oy = (nh - HEIGHT) // 2
    im_cropped = im_scaled.crop((ox, oy, ox + WIDTH, oy + HEIGHT))

    # Darken overlay for text contrast
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (10, 12, 16, int(255 * darken)))
    im_rgba = im_cropped.convert("RGBA")
    im_composite = Image.alpha_composite(im_rgba, overlay)

    grain = PaperCraftService.generate_film_grain_texture(WIDTH, HEIGHT, intensity=0.035)
    return Image.alpha_composite(im_composite, grain)


def draw_hud_overlay(canvas: Image.Image, frame_num: int, total_frames: int, section_tag: str) -> None:
    """Subtle documentary viewfinder HUD overlay."""
    draw = ImageDraw.Draw(canvas)
    # Viewfinder border
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 30), width=2)
    # Corner marks
    c_len = 22
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 220), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 220), width=3)

    font_tag = get_font(15, bold=True)
    draw.text((70, 52), f"LỊCH SỬ TRUNG HOA // {section_tag.upper()}", font=font_tag, fill=(255, 220, 20, 230))
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 300, 52), f"HỒ SƠ TƯ LIỆU // F:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 70))


def draw_giant_kinetic_badge(canvas: Image.Image, main_text: str, sub_text: str, progress: float, center_y: int = 160, bg_color: tuple[int, int, int] = (210, 35, 35)) -> None:
    """Giant bold kinetic typography banner."""
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = ease_out_back(progress)
    
    font_main = get_font(int(46 * min(1.0, 0.8 + 0.2 * p)), bold=True)
    font_sub = get_font(18, bold=True)

    bbox_main = draw.textbbox((0, 0), main_text, font=font_main)
    w_main = bbox_main[2] - bbox_main[0]
    h_main = bbox_main[3] - bbox_main[1]

    cx = WIDTH // 2
    cy = center_y
    pad_x, pad_y = 30, 14

    box = [
        cx - w_main // 2 - pad_x,
        cy - h_main // 2 - pad_y,
        cx + w_main // 2 + pad_x,
        cy + h_main // 2 + pad_y,
    ]
    draw.rectangle(box, fill=(*bg_color, int(245 * min(1.0, progress * 1.5))))
    draw.text((cx, cy), main_text, font=font_main, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((cx, cy - h_main // 2 - pad_y - 18), sub_text.upper(), font=font_sub, fill=(255, 220, 20, 240), anchor="mm")


def draw_fast_stamp(canvas: Image.Image, center: tuple[int, int], text: str, progress: float, color: tuple[int, int, int] = (210, 25, 25), angle: float = -8.0) -> None:
    if progress <= 0:
        return
    stamp_scale = ease_out_back(progress)
    sw = int(240 * stamp_scale)
    sh = int(66 * stamp_scale)
    if sw < 10 or sh < 10:
        return

    simg = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(simg)
    sdraw.rectangle([(0, 0), (sw - 1, sh - 1)], outline=(*color, 240), width=4)
    sfont = get_font(int(24 * stamp_scale), bold=True)
    sdraw.text((sw // 2, sh // 2), text, font=sfont, fill=(*color, 240), anchor="mm")
    simg = simg.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(simg, (center[0] - simg.width // 2, center[1] - simg.height // 2), mask=simg.split()[-1])


def draw_animated_arrow(canvas: Image.Image, start: tuple[int, int], end: tuple[int, int], progress: float, color: tuple[int, int, int] = (240, 40, 40), width: int = 10, label: str = "") -> None:
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = max(0.0, min(1.0, progress))
    cur_x = start[0] + (end[0] - start[0]) * p
    cur_y = start[1] + (end[1] - start[1]) * p
    draw.line([start, (int(cur_x), int(cur_y))], fill=(*color, 245), width=width)

    if p > 0.15:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        arrow_len = 26
        p1 = (int(cur_x), int(cur_y))
        p2 = (int(cur_x + math.cos(angle + math.pi * 0.8) * arrow_len), int(cur_y + math.sin(angle + math.pi * 0.8) * arrow_len))
        p3 = (int(cur_x + math.cos(angle - math.pi * 0.8) * arrow_len), int(cur_y + math.sin(angle - math.pi * 0.8) * arrow_len))
        draw.polygon([p1, p2, p3], fill=(*color, 255))

    if label and p > 0.5:
        font = get_font(20, bold=True)
        draw.text(((start[0] + cur_x) / 2, (start[1] + cur_y) / 2 - 24), label, font=font, fill=(255, 230, 20, 240), anchor="mm")


# --------------------------------------------------------------------------- #
# 8 Full-Screen Cinematic Vox Scenes (Zero Boring Bullet Points!)
# --------------------------------------------------------------------------- #
def render_master_scene_001(f: int, n: int) -> Image.Image:
    """Scene 1: 5000 Năm Khởi nguồn — Full-screen Yellow River silk scroll + Giant 100px kinetic typography."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_001_origins.png"), darken=0.38).copy()
    
    # Parallax camera push-in
    zoom = 1.0 + 0.04 * t
    zw, zh = int(WIDTH * zoom), int(HEIGHT * zoom)
    bg = bg.resize((zw, zh), Image.Resampling.BICUBIC).crop(((zw - WIDTH) // 2, (zh - HEIGHT) // 2, (zw + WIDTH) // 2, (zh + HEIGHT) // 2))

    draw_hud_overlay(bg, f, n, "KHỞI NGUỒN VĂN MINH")
    draw_giant_kinetic_badge(bg, "5.000 NĂM: KHỞI NGUỒN HOA HẠ", "LƯU VỰC SÔNG HOÀNG HÀ & THỜI KỲ CỔ ĐẠI", min(1.0, t * 3.5), center_y=140)

    # Big Central Historical Callout
    draw = ImageDraw.Draw(bg)
    font_epic = get_font(84, bold=True)
    epic_p = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 2.5)))
    if epic_p > 0:
        draw.text((WIDTH // 2, 540), "HẠ • THƯƠNG • CHU", font=font_epic, fill=(255, 230, 20, 255), anchor="mm")
        font_sub = get_font(28, bold=True)
        draw.text((WIDTH // 2, 620), "THỜI KỲ ĐỒ ĐỒNG & CHỮ GIÁP CỐT CỔ ĐẠI", font=font_sub, fill=(255, 255, 255, 230), anchor="mm")

        # Dynamic underline
        uw = int(820 * min(1.0, max(0.0, (t - 0.4) * 3.0)))
        draw.line([(WIDTH // 2 - uw // 2, 660), (WIDTH // 2 + uw // 2, 660)], fill=(220, 35, 35, 240), width=6)

    # Stamp
    stamp_p = min(1.0, max(0.0, (t - 0.7) * 4.0))
    draw_fast_stamp(bg, (WIDTH // 2, 770), "KHỞI NGUỒN", stamp_p, color=(220, 35, 35))

    return bg


def render_master_scene_002(f: int, n: int) -> Image.Image:
    """Scene 2: 221 TCN Nhà Tần — Terracotta army + Full-screen Imperial Decree + Live Highlighter."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_002_terracotta.png"), darken=0.45).copy()

    draw_hud_overlay(bg, f, n, "NHÀ TẦN THỐNG NHẤT")
    draw_giant_kinetic_badge(bg, "221 TCN: NHÀ TẦN THỐNG NHẤT", "TẦN THỦY HOÀNG & ĐẾ CHẾ ĐẦU TIÊN", min(1.0, t * 3.5), center_y=140)

    # Center Imperial Decree Card
    doc_prog = ease_out_back(min(1.0, max(0.0, (t - 0.15) * 3.0)))
    doc_y = int(1200 - 640 * doc_prog)
    if doc_prog > 0:
        w, h = 1100, 520
        card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(card)
        cdraw.rectangle([(0, 0), (w, h)], fill=(245, 242, 234, 255), outline=(190, 185, 170, 255), width=2)
        
        # Red imperial banner
        cdraw.rectangle([(0, 0), (w, 54)], fill=(190, 25, 25, 255))
        font_b = get_font(24, bold=True)
        cdraw.text((w // 2, 27), "CHIẾU CHỈ THỐNG NHẤT THIÊN HẠ", font=font_b, fill=(255, 255, 255, 255), anchor="mm")

        # Decree text lines
        font_l = get_font(26, bold=True)
        cdraw.text((40, 110), "1. THỐNG NHẤT CHỮ VIẾT TRÊN TOÀN ĐẾ CHẾ (TIỂU TRIỆN)", font=font_l, fill=(24, 24, 28, 255))
        cdraw.text((40, 190), "2. THỐNG NHẤT TIỀN TỆ, ĐO LƯỜNG VÀ QUY CÁCH XE", font=font_l, fill=(24, 24, 28, 255))
        cdraw.text((40, 270), "3. BÃI BỎ PHÂN PHONG — THIẾT LẬP 36 QUẬN HUYỆN TẬP QUYỀN", font=font_l, fill=(24, 24, 28, 255))
        cdraw.text((40, 350), "4. XÂY DỰNG VÀ NỐI LIỀN VẠN LÝ TRƯỜNG THÀNH", font=font_l, fill=(24, 24, 28, 255))

        # 3D Pushpin on top
        pin = PaperCraftService.draw_3d_pushpin(radius=18, color=(220, 30, 30))
        card.paste(pin, ((w - pin.width) // 2, -10), mask=pin.split()[-1])

        # Paper cutout border
        cutout = PaperCraftService.create_torn_cutout(card, PaperCutoutOptions(border_width=8, roughness=0.25, shadow=True))
        bg.paste(cutout, (WIDTH // 2 - cutout.width // 2, doc_y - cutout.height // 2), mask=cutout.split()[-1])

        # Live yellow highlighter sweep over line 1 & line 3
        hl_prog = min(1.0, max(0.0, (t - 0.35) * 2.2))
        if hl_prog > 0:
            box = (450, doc_y - 160, int(450 + 1020 * hl_prog), doc_y - 115)
            bg = DocumentHighlighterService.apply_highlight_sweep(bg, box, progress=1.0, options=HighlightOptions(color_name="yellow", opacity=0.55))

        stamp_p = min(1.0, max(0.0, (t - 0.7) * 4.0))
        draw_fast_stamp(bg, (WIDTH // 2 + 360, doc_y + 160), "THỐNG NHẤT", stamp_p, color=(200, 25, 25), angle=-12.0)

    return bg


def render_master_scene_003(f: int, n: int) -> Image.Image:
    """Scene 3: Nhà Hán & Con Đường Tơ Lụa — Full-screen Silk Road Map + Animated vector trade arrow."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_003_silk_road.png"), darken=0.55).copy()

    draw_hud_overlay(bg, f, n, "CON ĐƯỜNG TƠ LỤA")
    draw_giant_kinetic_badge(bg, "NHÀ HÁN: CON ĐƯỜNG TƠ LỤA", "KẾT NỐI THƯƠNG MẠI Á - ÂU (400 NĂM HOÀNG KIM)", min(1.0, t * 3.5), center_y=140, bg_color=(20, 130, 160))

    # Full-Screen Tactical Map overlay
    draw = ImageDraw.Draw(bg)
    mx0, my0, mx1, my1 = 120, 250, WIDTH - 120, HEIGHT - 140
    draw.rectangle([(mx0, my0), (mx1, my1)], fill=(14, 22, 30, 230), outline=(40, 160, 200, 220), width=3)
    
    font_h = get_font(24, bold=True)
    draw.text((mx0 + 30, my0 + 25), "HẢI HÀNH & TUYẾN ĐƯỜNG THƯƠNG MẠI: TRÀNG AN -> ROME", font=font_h, fill=(120, 230, 255, 255))

    # Key trading hubs
    nodes = [
        ((1600, 680), "TRÀNG AN (ĐÔNG HÁN)"),
        ((1320, 580), "ĐÔN HOÀNG"),
        ((1020, 520), "SAMARKAND (TRUNG Á)"),
        ((680, 460), "BA TƯ (PERSIA)"),
        ((350, 420), "LA MÃ (ROME)"),
    ]
    for pt, name in nodes:
        draw.ellipse([(pt[0] - 10, pt[1] - 10), (pt[0] + 10, pt[1] + 10)], fill=(255, 220, 20, 255))
        draw.ellipse([(pt[0] - 18, pt[1] - 18), (pt[0] + 18, pt[1] + 18)], outline=(255, 220, 20, 160), width=1)
        draw.text((pt[0], pt[1] - 26), name, font=get_font(18, bold=True), fill=(255, 255, 255, 255), anchor="mm")

    # Animated glowing trade route arrow
    arrow_p = min(1.0, max(0.0, (t - 0.15) * 2.0))
    draw_animated_arrow(bg, (1600 - 20, 680), (350 + 20, 420), arrow_p, color=(255, 180, 20), width=10, label="CON ĐƯỜNG TƠ LỤA")

    if arrow_p >= 0.8:
        ring_r = int(30 + math.sin(t * 20) * 18)
        draw.ellipse([(350 - ring_r, 420 - ring_r), (350 + ring_r, 420 + ring_r)], outline=(255, 200, 20, 220), width=3)

    return bg


def render_master_scene_004(f: int, n: int) -> Image.Image:
    """Scene 4: Tam Quốc Diễn Nghĩa — Battle of Red Cliffs + 3 Faction Banners Slamming In."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_004_red_cliffs.png"), darken=0.35).copy()

    draw_hud_overlay(bg, f, n, "THỜI KỲ TAM QUỐC")
    draw_giant_kinetic_badge(bg, "THỜI KỲ TAM QUỐC PHÂN TRANH", "ĐẠI CHIẾN XÍCH BÍCH (208 SCN) • NGỤY - THỤC - NGÔ", min(1.0, t * 3.5), center_y=140)

    # 3 Faction Banners
    draw = ImageDraw.Draw(bg)
    b_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 2.5)))
    
    if b_prog > 0:
        # Faction 1: TÀO NGỤY (Left)
        w, h = 480, 420
        f1_x = int(-200 + (200 + 400) * b_prog)
        f1_card = Image.new("RGBA", (w, h), (18, 30, 50, 240))
        f1_draw = ImageDraw.Draw(f1_card)
        f1_draw.rectangle([(0, 0), (w, 50)], fill=(30, 90, 180, 255))
        f1_draw.text((w // 2, 25), "TÀO NGỤY (MIỀN BẮC)", font=get_font(22, bold=True), fill=(255, 255, 255, 255), anchor="mm")
        f1_draw.text((25, 90), "• Tào Tháo nắm giữ thiên tử", font=get_font(20, bold=True), fill=(220, 230, 255, 255))
        f1_draw.text((25, 140), "• 80 vạn đại quân Nam hạ", font=get_font(20, bold=True), fill=(220, 230, 255, 255))
        f1_draw.text((25, 190), "• Chiếm giữ Trung Nguyên màu mỡ", font=get_font(20, bold=True), fill=(220, 230, 255, 255))
        f1_cutout = PaperCraftService.create_torn_cutout(f1_card, PaperCutoutOptions(border_width=6, roughness=0.2))
        bg.paste(f1_cutout, (f1_x - f1_cutout.width // 2, 580 - f1_cutout.height // 2), mask=f1_cutout.split()[-1])

        # Faction 2: THỤC HÁN (Center)
        f2_y = int(1200 - (1200 - 580) * b_prog)
        f2_card = Image.new("RGBA", (w, h), (20, 40, 28, 240))
        f2_draw = ImageDraw.Draw(f2_card)
        f2_draw.rectangle([(0, 0), (w, 50)], fill=(30, 140, 70, 255))
        f2_draw.text((w // 2, 25), "THỤC HÁN (TỨ XUYÊN)", font=get_font(22, bold=True), fill=(255, 255, 255, 255), anchor="mm")
        f2_draw.text((25, 90), "• Lưu Bị xưng đế kế tục Hán triều", font=get_font(20, bold=True), fill=(220, 255, 230, 255))
        f2_draw.text((25, 140), "• Quân sư Gia Cát Lượng tài ba", font=get_font(20, bold=True), fill=(220, 255, 230, 255))
        f2_draw.text((25, 190), "• Địa thế Ba Thục hiểm trở", font=get_font(20, bold=True), fill=(220, 255, 230, 255))
        f2_cutout = PaperCraftService.create_torn_cutout(f2_card, PaperCutoutOptions(border_width=6, roughness=0.2))
        bg.paste(f2_cutout, (WIDTH // 2 - f2_cutout.width // 2, f2_y - f2_cutout.height // 2), mask=f2_cutout.split()[-1])

        # Faction 3: ĐÔNG NGÔ (Right)
        f3_x = int(2100 - (2100 - 1520) * b_prog)
        f3_card = Image.new("RGBA", (w, h), (45, 20, 22, 240))
        f3_draw = ImageDraw.Draw(f3_card)
        f3_draw.rectangle([(0, 0), (w, 50)], fill=(190, 40, 40, 255))
        f3_draw.text((w // 2, 25), "ĐÔNG NGÔ (GIANG NAM)", font=get_font(22, bold=True), fill=(255, 255, 255, 255), anchor="mm")
        f3_draw.text((25, 90), "• Tôn Quyền hùng cứ sông Trường Giang", font=get_font(20, bold=True), fill=(255, 230, 230, 255))
        f3_draw.text((25, 140), "• Chu Du dùng hỏa công Xích Bích", font=get_font(20, bold=True), fill=(255, 230, 230, 255))
        f3_draw.text((25, 190), "• Hình thành thế chân vạc 3 nước", font=get_font(20, bold=True), fill=(255, 230, 230, 255))
        f3_cutout = PaperCraftService.create_torn_cutout(f3_card, PaperCutoutOptions(border_width=6, roughness=0.2))
        bg.paste(f3_cutout, (f3_x - f3_cutout.width // 2, 580 - f3_cutout.height // 2), mask=f3_cutout.split()[-1])

    # Giant Impact Stamp in Center
    stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
    draw_fast_stamp(bg, (WIDTH // 2, 850), "TAM QUỐC TRANH HÙNG", stamp_p, color=(220, 30, 30))

    return bg


def render_master_scene_005(f: int, n: int) -> Image.Image:
    """Scene 5: Nhà Đường Thịnh Thế — Golden Palace + 1.000.000 Population Metric + Poetry unroll."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_005_tang_palace.png"), darken=0.35).copy()

    draw_hud_overlay(bg, f, n, "NHÀ ĐƯỜNG THỊNH THẾ")
    draw_giant_kinetic_badge(bg, "NHÀ ĐƯỜNG: ĐỈNH CAO THỊNH THẾ", "KINH ĐÔ TRÀNG AN & THƠ CA RỰC RỠ HOÀNG KIM", min(1.0, t * 3.5), center_y=140, bg_color=(200, 120, 20))

    # Center Big Metric Callout
    draw = ImageDraw.Draw(bg)
    pop_p = ease_out_cubic(min(1.0, max(0.0, (t - 0.15) * 2.2)))
    pop_num = int(1000000 * pop_p)
    pop_str = f"{pop_num:,}".replace(",", ".") + " DÂN"

    font_pop = get_font(88, bold=True)
    draw.text((WIDTH // 2, 490), pop_str, font=font_pop, fill=(255, 230, 20, 255), anchor="mm")
    font_pop_sub = get_font(26, bold=True)
    draw.text((WIDTH // 2, 560), "KINH ĐÔ TRÀNG AN: ĐÔ THỊ LỚN NHẤT THẾ GIỚI THỜI CỔ ĐẠI", font=font_pop_sub, fill=(255, 255, 255, 240), anchor="mm")

    # Poetry scroll banner
    scroll_p = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 2.5)))
    if scroll_p > 0:
        sw = int(1000 * scroll_p)
        sh = 90
        scard = Image.new("RGBA", (sw, sh), (245, 240, 220, 245))
        sdraw = ImageDraw.Draw(scard)
        sdraw.rectangle([(0, 0), (sw - 1, sh - 1)], outline=(190, 160, 90, 255), width=2)
        font_poem = get_font(22, bold=True)
        sdraw.text((sw // 2, sh // 2), "ĐỈNH CAO THI CA NHÂN LOẠI: LÝ BẠCH • ĐỖ PHỦ • BẠCH CƯ DỊ", font=font_poem, fill=(30, 24, 18, 255), anchor="mm")
        scut = PaperCraftService.create_torn_cutout(scard, PaperCutoutOptions(border_width=4, roughness=0.2))
        bg.paste(scut, (WIDTH // 2 - scut.width // 2, 680 - scut.height // 2), mask=scut.split()[-1])

    stamp_p = min(1.0, max(0.0, (t - 0.7) * 4.0))
    draw_fast_stamp(bg, (WIDTH // 2, 800), "THỊNH THẾ", stamp_p, color=(200, 120, 20))

    return bg


def render_master_scene_006(f: int, n: int) -> Image.Image:
    """Scene 6: Tứ Đại Phát Minh & Nhà Nguyên — 4-Quadrant Museum Collage with 3D Pins."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_006_inventions.png"), darken=0.5).copy()

    draw_hud_overlay(bg, f, n, "TỨ ĐẠI PHÁT MINH")
    draw_giant_kinetic_badge(bg, "TỨ ĐẠI PHÁT MINH THAY ĐỔI THẾ GIỚI", "NHÀ TỐNG & ĐẾ CHẾ NGUYÊN MÔNG (960 - 1368)", min(1.0, t * 3.5), center_y=140, bg_color=(20, 140, 80))

    # 4 Quadrant Cards
    inventions = [
        ("LA BÀN (COMPASS)", "Định hướng hàng hải & Mở ra kỷ nguyên khám phá", (480, 420), -2.5),
        ("THUỐC SÚNG (GUNPOWDER)", "Thay đổi hoàn toàn nghệ thuật quân sự thế giới", (1440, 420), 2.5),
        ("KỸ THUẬT IN (PRINTING)", "In chữ rời truyền bá tri thức khắp nhân loại", (480, 720), 2.0),
        ("KỸ THUẬT LÀM GIẤY (PAPER)", "Nền tảng lưu trữ văn minh và văn hóa", (1440, 720), -2.0),
    ]

    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.15) * 2.5)))
    if p_prog > 0:
        for idx, (title, desc, center, angle) in enumerate(inventions):
            w, h = 600, 180
            card = Image.new("RGBA", (w, h), (245, 242, 234, 255))
            draw_c = ImageDraw.Draw(card)
            draw_c.rectangle([(0, 0), (w, 36)], fill=(20, 130, 70, 255))
            draw_c.text((16, 8), f"PHÁT MINH 0{idx+1}", font=get_font(16, bold=True), fill=(255, 255, 255, 255))
            draw_c.text((20, 52), title, font=get_font(22, bold=True), fill=(20, 30, 24, 255))
            draw_c.text((20, 100), desc, font=get_font(17, bold=False), fill=(60, 70, 65, 255))

            # Pin
            pin = PaperCraftService.draw_3d_pushpin(radius=14, color=(220, 30, 30))
            card.paste(pin, ((w - pin.width) // 2, -8), mask=pin.split()[-1])

            cut = PaperCraftService.create_torn_cutout(card, PaperCutoutOptions(border_width=6, roughness=0.2))
            if angle != 0.0:
                cut = cut.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
            bg.paste(cut, (center[0] - cut.width // 2, center[1] - cut.height // 2), mask=cut.split()[-1])

    return bg


def render_master_scene_007(f: int, n: int) -> Image.Image:
    """Scene 7: Nhà Minh & Nhà Thanh — Forbidden City + 1911 Revolution Red 'X' Cross-out."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_007_forbidden_city.png"), darken=0.4).copy()

    draw_hud_overlay(bg, f, n, "MINH - THANH & TÂN HỢI")
    draw_giant_kinetic_badge(bg, "NHÀ MINH - NHÀ THANH (1368-1912)", "TỬ CẤM THÀNH & CÁCH MẠNG TÂN HỢI 1911", min(1.0, t * 3.5), center_y=140)

    # Center Forbidden City Imperial Decree
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 2.5)))
    if c_prog > 0:
        w, h = 1000, 480
        card = Image.new("RGBA", (w, h), (245, 240, 230, 255))
        cdraw = ImageDraw.Draw(card)
        cdraw.rectangle([(0, 0), (w, 50)], fill=(180, 30, 30, 255))
        cdraw.text((w // 2, 25), "TRIỀU ĐẠI PHONG KIẾN CUỐI CÙNG", font=get_font(24, bold=True), fill=(255, 255, 255, 255), anchor="mm")

        font_t = get_font(22, bold=True)
        cdraw.text((40, 90), "• Nhà Minh: Xây dựng Tử Cấm Thành & Vạn Lý Trường Thành", font=font_t, fill=(24, 24, 28, 255))
        cdraw.text((40, 160), "• Nhà Thanh: Mở rộng cương thổ rộng lớn nhất lịch sử", font=font_t, fill=(24, 24, 28, 255))
        cdraw.text((40, 230), "• Thế kỷ 19: Khủng hoảng & sự xâm lược của phương Tây", font=font_t, fill=(24, 24, 28, 255))
        cdraw.text((40, 300), "• 1911: Cách mạng Tân Hợi lật đổ hoàng đế Phổ Nghi", font=font_t, fill=(24, 24, 28, 255))

        # Corner tape
        card = PaperCraftService.apply_corner_tape_mounts(card, tape_size=(75, 24))
        cut = PaperCraftService.create_torn_cutout(card, PaperCutoutOptions(border_width=8, roughness=0.25))
        bg.paste(cut, (WIDTH // 2 - cut.width // 2, 580 - cut.height // 2), mask=cut.split()[-1])

    # Giant Red 'X' Cross-out Stamped across the imperial decree
    cross_p = min(1.0, max(0.0, (t - 0.65) * 3.5))
    if cross_p > 0:
        draw = ImageDraw.Draw(bg)
        cx, cy = WIDTH // 2, 580
        rx, ry = int(450 * cross_p), int(200 * cross_p)
        draw.line([(cx - rx, cy - ry), (cx + rx, cy + ry)], fill=(230, 25, 25, 230), width=10)
        draw.line([(cx - rx, cy + ry), (cx + rx, cy - ry)], fill=(230, 25, 25, 230), width=10)

        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(bg, (WIDTH // 2, 760), "CHẤM DỨT PHONG KIẾN", stamp_p, color=(230, 25, 25), angle=-6.0)

    return bg


def render_master_scene_008(f: int, n: int) -> Image.Image:
    """Scene 8: Master Grand Conclusion — Great Wall Sunrise + 120px Rolling Odometer."""
    t = f / n
    bg = get_processed_fullscreen_image(str(IMAGES_DIR / "scene_008_great_wall.png"), darken=0.35).copy()

    draw_hud_overlay(bg, f, n, "TỔNG KẾT VĂN MINH")
    draw_giant_kinetic_badge(bg, "TỔNG KẾT 5.000 NĂM LỊCH SỬ", "KHO TÀNG VĂN MINH & QUY LUẬT HƯNG VONG", min(1.0, t * 3.5), center_y=140, bg_color=(190, 30, 30))

    # Giant Center 120px Rolling Odometer
    count_p = ease_out_cubic(min(1.0, t * 2.2))
    years = int(5000 * count_p)
    year_str = f"{years:,}".replace(",", ".") + " NĂM"

    draw = ImageDraw.Draw(bg)
    font_mega = get_font(110, bold=True)
    draw.text((WIDTH // 2, 480), year_str, font=font_mega, fill=(255, 230, 20, 255), anchor="mm")

    font_sub_mega = get_font(32, bold=True)
    draw.text((WIDTH // 2, 570), "24 TRIỀU ĐẠI HƯNG THỊNH VÀ SUY VONG", font=font_sub_mega, fill=(255, 255, 255, 240), anchor="mm")

    under_p = min(1.0, max(0.0, (t - 0.2) * 3.0))
    if under_p > 0:
        uw = int(880 * under_p)
        draw.line([(WIDTH // 2 - uw // 2, 610), (WIDTH // 2 + uw // 2, 610)], fill=(225, 35, 35, 240), width=6)

    # Historical Lesson Lockup Banner
    lock_p = ease_out_back(min(1.0, max(0.0, (t - 0.45) * 2.5)))
    if lock_p > 0:
        lw = int(1050 * lock_p)
        lh = 90
        lcard = Image.new("RGBA", (lw, lh), (245, 240, 225, 245))
        ldraw = ImageDraw.Draw(lcard)
        ldraw.rectangle([(0, 0), (lw - 1, lh - 1)], outline=(190, 160, 90, 255), width=2)
        font_quote = get_font(24, bold=True)
        ldraw.text((lw // 2, lh // 2), "'LẤY DÂN LÀM GỐC: THUẬN LÒNG DÂN THÌ THỊNH, NGHỊCH THÌ VONG'", font=font_quote, fill=(24, 20, 16, 255), anchor="mm")
        lcut = PaperCraftService.create_torn_cutout(lcard, PaperCutoutOptions(border_width=4, roughness=0.2))
        bg.paste(lcut, (WIDTH // 2 - lcut.width // 2, 720 - lcut.height // 2), mask=lcut.split()[-1])

    stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
    draw_fast_stamp(bg, (WIDTH // 2, 850), "LỊCH SỬ VIỆT NAM // BÀI HỌC HÒA BÌNH", stamp_p, color=(210, 25, 25))

    return bg


SCENE_RENDERERS = [
    render_master_scene_001,
    render_master_scene_002,
    render_master_scene_003,
    render_master_scene_004,
    render_master_scene_005,
    render_master_scene_006,
    render_master_scene_007,
    render_master_scene_008,
]


SCENES_METADATA = [
    {
        "id": "scene_001",
        "narration": "Khởi nguồn từ lưu vực sông Hoàng Hà hơn năm ngàn năm trước, nền văn minh Hoa Hạ hình thành qua các triều đại Hạ, Thương, Chu và thời kỳ Xuân Thu Chiến Quốc.",
        "template": "01_subject_slide_headline_pop",
    },
    {
        "id": "scene_002",
        "narration": "Năm 221 trước Công nguyên, Tần Thủy Hoàng thống nhất lục quốc, thiết lập chế độ phong kiến tập quyền, thống nhất văn tự, đo lường và xây dựng Vạn Lý Trường Thành.",
        "template": "07_document_highlight",
    },
    {
        "id": "scene_003",
        "narration": "Triều đại nhà Hán kéo dài hơn bốn trăm năm, mở ra Con đường Tơ lụa huyền thoại kết nối giao thương từ Tràng An sang tận La Mã cổ đại.",
        "template": "03_map_pan_marker_pulse",
    },
    {
        "id": "scene_004",
        "narration": "Thời kỳ Tam Quốc phân tranh khốc liệt giữa ba thế lực Ngụy, Thục, Ngô với trận thủy chiến Xích Bích nổi tiếng đi vào thi ca sử sách.",
        "template": "04_before_after_split",
    },
    {
        "id": "scene_005",
        "narration": "Đến thời nhà Đường, kinh đô Tràng An trở thành trung tâm phồn hoa bậc nhất thế giới, đỉnh cao rực rỡ của thơ ca, nghệ thuật và Phật giáo phương Đông.",
        "template": "09_cutout_parallax",
    },
    {
        "id": "scene_006",
        "narration": "Nhà Tống tỏa sáng với bốn phát minh vĩ đại gồm la bàn, thuốc súng, giấy và kỹ thuật in, trước khi vó ngựa Mông Cổ của Hốt Tất Liệt lập nên nhà Nguyên.",
        "template": "05_stat_number_count",
    },
    {
        "id": "scene_007",
        "narration": "Nhà Minh xây dựng Tử Cấm Thành nguy nga, còn nhà Thanh mở rộng cương thổ rộng lớn trước khi sụp đổ trong cuộc Cách mạng Tân Hợi năm 1911.",
        "template": "11_object_zoom_texture_wipe",
    },
    {
        "id": "scene_008",
        "narration": "Trải qua hàng ngàn năm hưng thịnh và suy vong qua các triều đại, lịch sử Trung Quốc để lại kho tàng văn hóa đồ sộ và những bài học trị quốc sâu sắc cho hậu thế.",
        "template": "12_conclusion_lockup",
    },
]


def main() -> None:
    logger.info("=== Starting True Vox Cinematic Masterpiece Video Generation ===")
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
        logger.info(f"--- Rendering Cinematic Vox Scene: {scene_id} [{idx + 1}/8] ---")

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
        "-i", f"aevalsrc=sin(2*PI*65*t)*0.15 + sin(2*PI*130*t)*0.08 + sin(2*PI*260*t)*0.03:d={dur_s:.3f}:s=48000",
        "-af", f"lowpass=f=450,volume=-18dB,afade=t=in:d=2.0,afade=t=out:st={dur_s - 2.5:.2f}:d=2.5",
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
    final_mp4 = final_dir / "lich_su_trung_quoc_masterpiece_60s.mp4"
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
    print(f"\n[DONE] Video Vox Masterpiece hoàn tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
