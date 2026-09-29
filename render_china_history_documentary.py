"""Production script to generate a 60-second Vox documentary: 'Lịch Sử Trung Quốc Qua Các Thời Đại'.

Applies all Vox Studio style presets and motion graphics:
- Scene 1: Khởi Nguồn Văn Minh Hoa Hạ (Hạ, Thương, Chu, Hoàng Hà, 3D Pushpin, Archival Scroll)
- Scene 2: 221 TCN: Nhà Tần Thống Nhất (Tần Thủy Hoàng, Đất nung, Live Yellow Highlighter on Reforms, Stamp "THỐNG NHẤT")
- Scene 3: Nhà Hán & Con Đường Tơ Lụa (Silk Road Trade Route Vector Map from Chang'an to Rome)
- Scene 4: Thời Kỳ Tam Quốc (Ngụy, Thục, Ngô, Đại chiến Xích Bích, Split-Screen Comparison)
- Scene 5: Nhà Đường: Đỉnh Cao Thịnh Thế (Kinh đô Tràng An, 1 triệu dân, Thơ Đường, Stamp "THỊNH THẾ")
- Scene 6: Tứ Đại Phát Minh & Nhà Nguyên (La bàn, Thuốc súng, Giấy, Kỹ thuật in, Vó ngựa Mông Cổ)
- Scene 7: Nhà Minh & Nhà Thanh (Tử Cấm Thành, Hoàng đế Phổ Nghi, Cách mạng Tân Hợi 1911, Red Cross-out)
- Scene 8: Tổng Kết 5000 Năm Văn Minh (Rolling Odometer 5.000 Năm • 24 Triều đại, Vạn Lý Trường Thành, Stamp "LỊCH SỬ")
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
logger = logging.getLogger("china_history_vox")

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

    # 3D Pushpin on top center
    pin = PaperCraftService.draw_3d_pushpin(radius=15, color=(220, 30, 30))
    frame.paste(pin, ((w - pin.width) // 2, -10), mask=pin.split()[-1])

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

    # Corner tape mounts
    card = PaperCraftService.apply_corner_tape_mounts(card, tape_size=(65, 22))

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

    if theme == "imperial_gold":
        bg_c1, bg_c2 = (34, 26, 16), (16, 12, 8)    # Ancient bronze/gold dark sepia
    elif theme == "crimson_dynasty":
        bg_c1, bg_c2 = (38, 16, 18), (16, 8, 10)    # Imperial crimson red
    elif theme == "tang_terracotta":
        bg_c1, bg_c2 = (28, 24, 22), (12, 11, 10)   # Terracotta dark stone
    elif theme == "silk_road":
        bg_c1, bg_c2 = (22, 28, 32), (10, 14, 16)   # Deep night teal
    else:
        bg_c1, bg_c2 = (24, 24, 26), (12, 12, 14)

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

    # Top center tag (no overlapping with headline badge)
    font_tag = get_font(15, bold=True)
    draw.text((WIDTH // 2, 52), f"LỊCH SỬ TRUNG HOA // {style_badge.upper()}", font=font_tag, fill=(255, 220, 20, 230), anchor="mm")
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 320, 52), f"HỒ SƠ TRIỀU ĐẠI // KHUNG:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 70))

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
# Scene-specific Frame Renderers
# --------------------------------------------------------------------------- #
def render_china_scene_001(f: int, n: int) -> Image.Image:
    """Scene 1: Khởi nguồn Hoa Hạ — Yellow River & Bronze Age."""
    img = make_canvas("imperial_gold", f, n, "KHỞI NGUỒN VĂN MINH")
    t = f / n
    draw_headline_badge(img, "5.000 NĂM: KHỞI NGUỒN HOA HẠ", "LƯU VỰC HOÀNG HÀ & THỜI KỲ CỔ ĐẠI", min(1.0, t * 4.0))

    # Left: Archival Silk Scroll / Bronze Vessel Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 500) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_001_origins.png"), 540, 440, "TƯ LIỆU: BẢO VẬT ĐỒNG THAU NHÀ CHU", -3.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Origins Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    c_y = int(-300 + (300 + 560) * c_prog)
    if c_prog > 0:
        card = get_cached_card_base(
            620, 450,
            "CÁC TRIỀU ĐẠI ĐẦU TIÊN", "HẠ • THƯƠNG • CHU",
            (
                "• Hình thành dọc lưu vực sông Hoàng Hà",
                "• Nền văn minh đồ đồng rực rỡ và chữ Giáp cốt",
                "• Thời kỳ Xuân Thu - Chiến Quốc phân tranh",
                "• Đặt nền móng triết học Nho gia và Đạo gia",
            ),
            190, 40, 30, 2.5
        )
        img.paste(card, (1340 - card.width // 2, c_y - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1480, c_y + 120), "KHỞI NGUỒN", stamp_p)

    return img


def render_china_scene_002(f: int, n: int) -> Image.Image:
    """Scene 2: 221 TCN: Nhà Tần Thống Nhất — Terracotta Warriors & Live Highlighter."""
    img = make_canvas("tang_terracotta", f, n, "NHÀ TẦN THỐNG NHẤT")
    t = f / n
    draw_headline_badge(img, "221 TCN: NHÀ TẦN THỐNG NHẤT", "TẦN THỦY HOÀNG & ĐẾ CHẾ ĐẦU TIÊN", min(1.0, t * 4.0))

    # Left: Terracotta Army Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_002_terracotta.png"), 520, 440, "TƯ LIỆU: ĐỘI QUÂN ĐẤT NUNG TÂY AN", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Imperial Reforms Card with Live Highlighter
    doc_prog = ease_out_back(min(1.0, max(0.0, (t - 0.15) * 3.0)))
    doc_y = int(1200 - 640 * doc_prog)
    if doc_prog > 0:
        card = get_cached_card_base(
            680, 480,
            "CẢI CÁCH ĐẾ CHẾ QUY MÔ LỚN", "THỐNG NHẤT LỤC QUỐC",
            (
                "DÒNG 1: THỐNG NHẤT CHỮ VIẾT, TIỀN TỆ VÀ ĐO LƯỜNG",
                "DÒNG 2: Thiết lập hệ thống quận huyện phong kiến tập quyền",
                "DÒNG 3: Nối liền và xây dựng Vạn Lý Trường Thành",
                "DÒNG 4: Mở đầu kỷ nguyên đế quốc kéo dài hơn 2000 năm",
            ),
            180, 30, 30, 2.0
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
        draw_fast_stamp(img, (1480, doc_y + 140), "THỐNG NHẤT", stamp_prog)

    return img


def render_china_scene_003(f: int, n: int) -> Image.Image:
    """Scene 3: Nhà Hán & Con Đường Tơ Lụa — Silk Road Vector Navigation Map."""
    img = make_canvas("silk_road", f, n, "CON ĐƯỜNG TƠ LỤA")
    t = f / n
    draw_headline_badge(img, "NHÀ HÁN: CON ĐƯỜNG TƠ LỤA", "TRÀNG AN -> TRUNG Á -> LA MÃ", min(1.0, t * 4.0), bg_color=(20, 130, 160))

    # Left: Silk Road Caravan Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 480) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_003_silk_road.png"), 520, 440, "TƯ LIỆU: ĐOÀN LẠC ĐÀ CON ĐƯỜNG TƠ LỤA", -2.5)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Dynamic Silk Road Map Board
    draw = ImageDraw.Draw(img)
    map_x0, map_y0, map_x1, map_y1 = 780, 260, 1800, 860
    draw.rectangle([(map_x0, map_y0), (map_x1, map_y1)], fill=(16, 24, 30, 240), outline=(40, 140, 180, 220), width=2)
    font_map = get_font(20, bold=True)
    draw.text((map_x0 + 20, map_y0 + 20), "BẢN ĐỒ CON ĐƯỜNG TƠ LỤA THỜI HÁN (400 NĂM)", font=font_map, fill=(120, 220, 240, 240))

    changan = (1620, 680)
    dunhuang = (1380, 580)
    samarkand = (1120, 500)
    rome = (900, 420)

    for pt, name in [(changan, "TRÀNG AN"), (dunhuang, "ĐÔN HOÀNG"), (samarkand, "TRUNG Á"), (rome, "LA MÃ (ROME)")]:
        draw.ellipse([(pt[0] - 8, pt[1] - 8), (pt[0] + 8, pt[1] + 8)], fill=(255, 220, 20, 255))
        draw.text((pt[0], pt[1] - 22), name, font=font_map, fill=(255, 255, 255, 255), anchor="mm")

    # Animated trade route arrow
    arrow_p = min(1.0, max(0.0, (t - 0.15) * 2.2))
    draw_animated_arrow(img, (changan[0] - 15, changan[1]), (rome[0] + 15, rome[1]), arrow_p, color=(255, 180, 30), label="GIAO THƯƠNG Á - ÂU")

    if arrow_p >= 0.8:
        ring_r = int(25 + math.sin(t * 20) * 15)
        draw.ellipse([(changan[0] - ring_r, changan[1] - ring_r), (changan[0] + ring_r, changan[1] + ring_r)], outline=(255, 200, 20, 200), width=3)

    return img


def render_china_scene_004(f: int, n: int) -> Image.Image:
    """Scene 4: Tam Quốc Diễn Nghĩa — Battle of Red Cliffs & Split-Screen Factions."""
    img = make_canvas("crimson_dynasty", f, n, "THỜI KỲ TAM QUỐC")
    t = f / n
    draw_headline_badge(img, "THỜI KỲ TAM QUỐC PHÂN TRANH", "NGỤY • THỤC • NGÔ & TRẬN XÍCH BÍCH", min(1.0, t * 4.0))

    # Center dividing line
    draw = ImageDraw.Draw(img)
    split_p = ease_out_cubic(min(1.0, t * 3.0))
    split_h = int(HEIGHT * split_p)
    draw.line([(WIDTH // 2, (HEIGHT - split_h) // 2), (WIDTH // 2, (HEIGHT + split_h) // 2)], fill=(220, 40, 40, 200), width=4)

    # Left: Red Cliffs Naval Battle Photo
    p1_prog = ease_out_back(min(1.0, t * 3.0))
    if p1_prog > 0:
        plate1 = get_cached_photo_plate(str(IMAGES_DIR / "scene_004_red_cliffs.png"), 580, 450, "TƯ LIỆU: ĐẠI CHIẾN THỦY QUÂN XÍCH BÍCH", -2.5)
        img.paste(plate1, (480 - plate1.width // 2, 560 - plate1.height // 2), mask=plate1.split()[-1])
        stamp_p1 = min(1.0, max(0.0, (t - 0.5) * 4.0))
        draw_fast_stamp(img, (600, 680), "XÍCH BÍCH", stamp_p1)

    # Right: Three Kingdoms Card
    c2_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if c2_prog > 0:
        card2 = get_cached_card_base(
            640, 450,
            "THẾ CHÂN VẠC LỊCH SỬ", "ANH HÙNG TRANH BÁ",
            (
                "• Tào Ngụy: Thống trị miền Bắc Trung Nguyên",
                "• Thục Hán: Lưu Bị, Gia Cát Lượng chiếm Tứ Xuyên",
                "• Đông Ngô: Tôn Quyền hùng cứ vùng Giang Nam",
                "• Thời kỳ bi tráng đi vào tiểu thuyết kinh điển",
            ),
            190, 35, 35, 2.5
        )
        img.paste(card2, (1420 - card2.width // 2, 560 - card2.height // 2), mask=card2.split()[-1])
        stamp_p2 = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1560, 680), "TAM QUỐC", stamp_p2, color=(210, 25, 25))

    return img


def render_china_scene_005(f: int, n: int) -> Image.Image:
    """Scene 5: Nhà Đường: Đỉnh Cao Thịnh Thế — Chang'an Palace & Poetry."""
    img = make_canvas("imperial_gold", f, n, "NHÀ ĐƯỜNG THỊNH THẾ")
    t = f / n
    draw_headline_badge(img, "NHÀ ĐƯỜNG: ĐỈNH CAO THỊNH THẾ", "KINH ĐÔ TRÀNG AN & THƠ CA RỰC RỠ", min(1.0, t * 4.0), bg_color=(200, 120, 20))

    # Left: Tang Palace Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_005_tang_palace.png"), 520, 440, "TƯ LIỆU: ĐẠI CUNG ĐIỆN TRÀNG AN", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Tang Golden Age Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            660, 470,
            "TRUNG TÂM PHỒN HOA THẾ GIỚI", "KỶ NGUYÊN HOÀNG KIM",
            (
                "• Tràng An: Đô thị triệu dân lớn nhất thế giới",
                "• Đỉnh cao thơ ca rực rỡ: Lý Bạch, Đỗ Phủ, Bạch Cư Dị",
                "• Giao lưu văn hóa quốc tế cởi mở và thịnh vượng",
                "• Phật giáo và nghệ thuật điêu khắc phát triển tột bậc",
            ),
            190, 110, 20, 2.0
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1500, 680), "THỊNH THẾ", stamp_p, color=(200, 120, 20))

    return img


def render_china_scene_006(f: int, n: int) -> Image.Image:
    """Scene 6: Tứ Đại Phát Minh & Nhà Nguyên — Compass, Gunpowder, Printing, Paper."""
    img = make_canvas("tang_terracotta", f, n, "TỨ ĐẠI PHÁT MINH")
    t = f / n
    draw_headline_badge(img, "TỨ ĐẠI PHÁT MINH & NHÀ NGUYÊN", "LA BÀN • THUỐC SÚNG • GIẤY • KỸ THUẬT IN", min(1.0, t * 4.0), bg_color=(30, 130, 80))

    # Left: Four Inventions Museum Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_006_inventions.png"), 520, 440, "TƯ LIỆU: BẢO VẬT PHÁT MINH CỔ ĐẠI", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Inventions & Mongol Dynasty Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            660, 470,
            "ĐÓNG GÓP CHO NHÂN LOẠI", "KHOA HỌC & ĐẾ CHẾ",
            (
                "• Nhà Tống: Phát triển tột bậc kinh tế và công nghệ",
                "• 4 phát minh thay đổi hoàn toàn lịch sử thế giới",
                "• Vó ngựa Mông Cổ lập nên triều đại nhà Nguyên",
                "• Giao thương Bắc - Nam qua kênh đào Đại Vận Hà",
            ),
            30, 130, 80, 2.0
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1500, 680), "PHÁT MINH", stamp_p, color=(30, 140, 80))

    return img


def render_china_scene_007(f: int, n: int) -> Image.Image:
    """Scene 7: Nhà Minh & Nhà Thanh — Forbidden City & 1911 Revolution."""
    img = make_canvas("crimson_dynasty", f, n, "MINH - THANH & TÂN HỢI")
    t = f / n
    draw_headline_badge(img, "NHÀ MINH - THANH (1368-1912)", "TỬ CẤM THÀNH & CÁCH MẠNG TÂN HỢI", min(1.0, t * 4.0))

    # Left: Forbidden City Photo
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_007_forbidden_city.png"), 520, 440, "TƯ LIỆU: HOÀNG CUNG TỬ CẤM THÀNH", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: End of Monarchy Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            680, 480,
            "HOÀNG ĐẾ CUỐI CÙNG & TÂN HỢI 1911", "KẾT THÚC PHONG KIẾN",
            (
                "• Nhà Minh: Xây dựng Tử Cấm Thành và Vạn Lý Trường Thành",
                "• Nhà Thanh: Mở rộng lãnh thổ đến mức cực thịnh",
                "• Suy tàn trước sự xâm lược của phương Tây thế kỷ 19",
                "• 1911: Cách mạng Tân Hợi lật đổ chế độ quân chủ chuyên chế",
            ),
            200, 30, 30, 2.0
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_prog = min(1.0, max(0.0, (t - 0.6) * 4.0))
        draw_fast_stamp(img, (1500, 680), "CHẤM DỨT", stamp_prog)

    # Red Cross-Out 'X'
    cross_p = min(1.0, max(0.0, (t - 0.7) * 3.5))
    if cross_p > 0:
        draw = ImageDraw.Draw(img)
        cx, cy = 1340, 560
        r = int(140 * cross_p)
        draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=(240, 25, 25, 220), width=8)
        draw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=(240, 25, 25, 220), width=8)

    return img


def render_china_scene_008(f: int, n: int) -> Image.Image:
    """Scene 8: Tổng kết 5000 Năm Lịch Sử — Rolling Odometer & Great Wall."""
    img = make_canvas("imperial_gold", f, n, "BÀI HỌC HƯNG VONG")
    t = f / n
    draw_headline_badge(img, "TỔNG KẾT 5.000 NĂM VĂN MINH", "KHO TÀNG LỊCH SỬ & BÀI HỌC TRỊ QUỐC", min(1.0, t * 4.0), bg_color=(190, 30, 30))

    # Top: Rolling Odometer Counter: 5000 NĂM • 24 TRIỀU ĐẠI
    count_p = ease_out_cubic(min(1.0, t * 2.5))
    years = int(5000 * count_p)
    year_str = f"{years:,}".replace(",", ".") + " NĂM LỊCH SỬ • 24 TRIỀU ĐẠI"

    draw = ImageDraw.Draw(img)
    font_big = get_font(68, bold=True)
    draw.text((WIDTH // 2, 290), year_str, font=font_big, fill=(255, 220, 20, 255), anchor="mm")

    font_sub_big = get_font(24, bold=True)
    draw.text((WIDTH // 2, 345), "DI SẢN VĂN HÓA ĐỒ SỘ VÀ NHỮNG BÀI HỌC HƯNG VONG ĐẮT GIÁ", font=font_sub_big, fill=(255, 255, 255, 240), anchor="mm")

    under_p = min(1.0, max(0.0, (t - 0.2) * 3.0))
    if under_p > 0:
        uw = int(820 * under_p)
        draw.line([(WIDTH // 2 - uw // 2, 375), (WIDTH // 2 + uw // 2, 375)], fill=(225, 35, 35, 240), width=5)

    # Bottom Left: Great Wall Photo
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_008_great_wall.png"), 580, 420, "TƯ LIỆU: VẠN LÝ TRƯỜNG THÀNH VĨ ĐẠI", -2.0)
        img.paste(plate, (480 - plate.width // 2, 680 - plate.height // 2), mask=plate.split()[-1])

    # Bottom Right: Final Conclusion Card
    card_prog = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 3.0)))
    if card_prog > 0:
        card = get_cached_card_base(
            640, 420,
            "QUY LUẬT HƯNG THỊNH & SUY VONG", "THÔNG ĐIỆP LỊCH SỬ",
            (
                "• Nền văn minh liên tục duy trì qua hàng thiên niên kỷ",
                "• Lấy dân làm gốc: Thuận lòng dân thì thịnh, nghịch thì vong",
                "• Kho tàng kinh nghiệm trị quốc và triết học sâu sắc",
                "• Bài học muôn đời cho sự phát triển của mọi quốc gia",
            ),
            190, 30, 30, 2.0
        )
        img.paste(card, (1380 - card.width // 2, 680 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1540, 790), "LỊCH SỬ", stamp_p)

    return img


SCENE_RENDERERS = [
    render_china_scene_001,
    render_china_scene_002,
    render_china_scene_003,
    render_china_scene_004,
    render_china_scene_005,
    render_china_scene_006,
    render_china_scene_007,
    render_china_scene_008,
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
    logger.info("=== Starting Lịch Sử Trung Quốc Qua Các Thời Đại (60s Vox Documentary) ===")
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

    # Procedural Cinematic BGM (Ancient Guzheng / Flute drone atmosphere)
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
    final_mp4 = final_dir / "lich_su_trung_quoc_60s.mp4"
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
    print(f"\n[DONE] Video Lịch Sử Trung Quốc Qua Các Thời Đại hoàn tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
