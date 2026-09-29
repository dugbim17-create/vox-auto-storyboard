"""High-Performance Advanced Frame-by-Frame Vox / Johnny Harris Style Motion Graphics Engine.

Optimized with Pre-Cached Photo Plates & Tactile Cards:
- AI-Generated Archival Documentary Photographs (pre-rendered archival photo plates with paper mount, tape, and photo corners)
- Pre-cached tactile cards with paper borders and drop shadows
- Animated tactical military invasion arrows & pulsing radar rings
- Real-time animated highlighter marker sweeps across archival documents
- Hand-drawn animated red pencil circles & underlines
- Impact red stamps with overshoot bounce & screen shake
- Rolling odometer numbers (0 -> 3,000,000 troops, 0 -> 70,000,000 casualties)
- Split-screen comparison & multi-card shuffles
- High-contrast typography with viewfinder marks and film grain
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
logger = logging.getLogger("vox_advanced")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_hitler_ww2_doc")
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
# Pre-cached Assets Generator
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=16)
def get_cached_photo_plate(img_path: str, w: int, h: int, caption: str = "", angle_deg: float = 0.0) -> Image.Image:
    """Pre-render and cache photo cutout to avoid repeating expensive blur/cutout operations."""
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
    """Pre-render and cache tactile text card base."""
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

    # Tape on top
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
def get_cached_base_bg(theme: str) -> Image.Image:
    """Pre-render static gradient background."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    if theme == "dark_slate":
        bg_c1, bg_c2 = (22, 26, 32), (12, 14, 18)
    elif theme == "sepia":
        bg_c1, bg_c2 = (38, 32, 24), (18, 15, 12)
    elif theme == "military":
        bg_c1, bg_c2 = (26, 32, 28), (14, 18, 15)
    elif theme == "crimson":
        bg_c1, bg_c2 = (42, 16, 18), (16, 8, 10)
    else:
        bg_c1, bg_c2 = (28, 28, 30), (14, 14, 16)

    for y in range(0, HEIGHT, 4):
        rat = y / HEIGHT
        r = int(bg_c1[0] * (1 - rat) + bg_c2[0] * rat)
        g = int(bg_c1[1] * (1 - rat) + bg_c2[1] * rat)
        b = int(bg_c1[2] * (1 - rat) + bg_c2[2] * rat)
        draw.rectangle([(0, y), (WIDTH, y + 4)], fill=(r, g, b, 255))

    grain = PaperCraftService.generate_film_grain_texture(WIDTH, HEIGHT, intensity=0.04)
    return Image.alpha_composite(img, grain)


def make_base_grid_canvas(theme: str, frame_num: int, total_frames: int) -> Image.Image:
    """Archival paper canvas with animated subtle camera pan and coordinate grids."""
    bg_base = get_cached_base_bg(theme)
    img = bg_base.copy()
    draw = ImageDraw.Draw(img)

    t = frame_num / max(1, total_frames)
    pan_x = int(math.sin(t * math.pi) * 20)
    pan_y = int(t * 15)

    # Tactical grid
    grid_alpha = 14
    for x in range((pan_x % 100), WIDTH, 100):
        draw.line([(x, 0), (x, HEIGHT)], fill=(255, 255, 255, grid_alpha), width=1)
    for y in range((pan_y % 100), HEIGHT, 100):
        draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, grid_alpha), width=1)

    # Technical metadata in corners
    font_mono = get_font(14, bold=False)
    draw.text((70, 45), "DEPT. OF HISTORICAL ARCHIVES // SEC-WW2", font=font_mono, fill=(255, 255, 255, 60))
    draw.text((WIDTH - 380, 45), f"LAT: 52°31'12\"N  LON: 13°24'18\"E  FRAME:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 60))

    # Viewfinder crop borders
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
    c_len = 20
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 200), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 200), width=3)

    return img


def draw_fast_stamp(canvas: Image.Image, center: tuple[int, int], text: str, progress: float) -> None:
    """Fast procedural impact stamp without heavy blurs."""
    if progress <= 0:
        return
    stamp_scale = ease_out_back(progress)
    sw = int(220 * stamp_scale)
    sh = int(60 * stamp_scale)
    if sw < 10 or sh < 10:
        return

    simg = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(simg)
    sdraw.rectangle([(0, 0), (sw - 1, sh - 1)], outline=(210, 25, 25, 230), width=4)
    sfont = get_font(int(22 * stamp_scale), bold=True)
    sdraw.text((sw // 2, sh // 2), text, font=sfont, fill=(210, 25, 25, 230), anchor="mm")
    simg = simg.rotate(-8, resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(simg, (center[0] - simg.width // 2, center[1] - simg.height // 2), mask=simg.split()[-1])


def draw_animated_arrow(
    canvas: Image.Image,
    start: tuple[int, int],
    end: tuple[int, int],
    progress: float,
    *,
    color: tuple[int, int, int] = (225, 35, 35),
    width: int = 8,
    label: str = "",
) -> None:
    """Draw a growing military tactical invasion arrow with arrowhead and label."""
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = max(0.0, min(1.0, progress))

    cur_x = start[0] + (end[0] - start[0]) * p
    cur_y = start[1] + (end[1] - start[1]) * p

    draw.line([start, (int(cur_x), int(cur_y))], fill=(*color, 240), width=width)

    if p > 0.15:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        arrow_len = 22
        left_angle = angle + math.pi * 0.8
        right_angle = angle - math.pi * 0.8

        p1 = (int(cur_x), int(cur_y))
        p2 = (int(cur_x + math.cos(left_angle) * arrow_len), int(cur_y + math.sin(left_angle) * arrow_len))
        p3 = (int(cur_x + math.cos(right_angle) * arrow_len), int(cur_y + math.sin(right_angle) * arrow_len))
        draw.polygon([p1, p2, p3], fill=(*color, 255))

    if label and p > 0.5:
        font = get_font(18, bold=True)
        mid_x = (start[0] + cur_x) / 2
        mid_y = (start[1] + cur_y) / 2 - 20
        draw.text((mid_x, mid_y), label, font=font, fill=(255, 230, 20, 240), anchor="mm")


def draw_animated_circle(
    canvas: Image.Image,
    center: tuple[int, int],
    radius: int,
    progress: float,
    *,
    color: tuple[int, int, int] = (225, 35, 35),
    width: int = 4,
) -> None:
    """Draw a hand-drawn circular stroke around key evidence."""
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


def draw_headline_badge(
    canvas: Image.Image,
    headline: str,
    category: str,
    progress: float,
) -> None:
    """Kinetic headline badge that pops in from the top left."""
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    slide = ease_out_back(progress)
    x = int(-400 + (400 + 70) * slide)
    y = 70

    font_head = get_font(38, bold=True)
    bbox = draw.textbbox((x, y), headline, font=font_head)
    pad_x, pad_y = 20, 10

    draw.rectangle([(bbox[0] - pad_x, bbox[1] - pad_y), (bbox[2] + pad_x, bbox[3] + pad_y)], fill=(220, 32, 32, 245))
    draw.text((x, y), headline, font=font_head, fill=(255, 255, 255, 255))

    font_cat = get_font(16, bold=True)
    draw.text((x, y - 24), category.upper(), font=font_cat, fill=(255, 220, 20, 240))


# --------------------------------------------------------------------------- #
# Scene-specific Frame Renderers
# --------------------------------------------------------------------------- #
def render_frame_scene_001(f: int, n: int) -> Image.Image:
    """Scene 1: 1889-1933 Trỗi dậy — AI Photo print of Munich rally + Weimar crisis card."""
    img = make_base_grid_canvas("dark_slate", f, n)
    t = f / n

    draw_headline_badge(img, "1889 - 1933: TRỖI DẬY", "GIAI ĐOẠN KHỞI NGUỒN", min(1.0, t * 4.0))

    # Left: AI Photo Print
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 520) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_001.png"), 560, 440, "TƯ LIỆU: ĐẠI HỘI MUNICH 1930s", -3.5)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Card base
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    c_y = int(-300 + (300 + 560) * c_prog)
    if c_prog > 0:
        card = get_cached_card_base(
            600, 450,
            "BẦU CỬ & NẮM QUYỀN 1933", "BƯỚC NGOẶT CHÍNH TRỊ",
            (
                "• Nước Đức kiệt quệ sau Thế chiến thứ nhất",
                "• Lạm phát phi mã & khủng hoảng kinh tế 1929",
                "• 30/01/1933: Hitler được bổ nhiệm làm Thủ tướng",
                "• Bắt đầu 12 năm thảm họa của Đế chế thứ Ba",
            ),
            210, 25, 25, 2.5
        )
        img.paste(card, (1360 - card.width // 2, c_y - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1500, c_y + 120), "QUYỀN LỰC", stamp_p)

    circle_p = min(1.0, max(0.0, (t - 0.7) * 3.5))
    if circle_p > 0:
        draw_animated_circle(img, (1360, 430), 105, circle_p, color=(255, 40, 40), width=5)

    return img


def render_frame_scene_002(f: int, n: int) -> Image.Image:
    """Scene 2: 1933 Đế chế độc tài — AI Photo of Reichstag + Enabling Act live highlighter sweep."""
    img = make_base_grid_canvas("sepia", f, n)
    t = f / n

    draw_headline_badge(img, "1933: THIẾT LẬP ĐỘC TÀI", "TẬP TRUNG QUYỀN LỰC", min(1.0, t * 4.0))

    # Left: AI Photo of Reichstag building under spotlights
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_002.png"), 520, 440, "TƯ LIỆU: TÒA QUỐC HỘI REICHSTAG 1933", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Enabling Act legal document
    doc_prog = ease_out_back(min(1.0, max(0.0, (t - 0.15) * 3.0)))
    doc_y = int(1200 - 640 * doc_prog)
    if doc_prog > 0:
        card = get_cached_card_base(
            680, 490,
            "ĐẠO LUẬT TRAO QUYỀN (1933)", "VĂN KIỆN PHÁP LÝ TỐI CAO",
            (
                "DÒNG 1: BÃI BỎ HOÀN TOÀN CƠ CHẾ ĐA ĐẢNG TẠI ĐỨC",
                "DÒNG 2: Trao toàn quyền lập pháp và hành pháp cho Hitler",
                "DÒNG 3: Kiểm soát toàn diện báo chí, giáo dục và quân đội",
                "DÒNG 4: Thành lập lực lượng mật vụ Gestapo khét tiếng",
            ),
            190, 30, 30, 2.0
        )
        img.paste(card, (1320 - card.width // 2, doc_y - card.height // 2), mask=card.split()[-1])

        # Live highlighter sweep over DÒNG 1
        hl_prog = min(1.0, max(0.0, (t - 0.35) * 2.2))
        if hl_prog > 0:
            box = (1030, doc_y - 105, int(1030 + 580 * hl_prog), doc_y - 75)
            img = DocumentHighlighterService.apply_highlight_sweep(
                img, box, progress=1.0, options=HighlightOptions(color_name="yellow", opacity=0.55)
            )

        stamp_prog = min(1.0, max(0.0, (t - 0.65) * 4.0))
        draw_fast_stamp(img, (1480, doc_y + 140), "ĐÃ BÃI BỎ", stamp_prog)

    return img


def render_frame_scene_003(f: int, n: int) -> Image.Image:
    """Scene 3: 1939 Thế chiến II bùng nổ — AI Photo of Panzer tanks + Animated Tactical Map."""
    img = make_base_grid_canvas("military", f, n)
    t = f / n

    draw_headline_badge(img, "1939: THẾ CHIẾN II BÙNG NỔ", "CHIẾN THUẬT BLITZKRIEG", min(1.0, t * 4.0))

    # Left: AI Photo of Panzer armored division
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 480) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_003.png"), 520, 440, "TƯ LIỆU: XE TĂNG PANZER 1939", -3.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Tactical Map Sector (Berlin -> Warsaw)
    draw = ImageDraw.Draw(img)
    map_x0, map_y0, map_x1, map_y1 = 800, 270, 1800, 850
    draw.rectangle([(map_x0, map_y0), (map_x1, map_y1)], fill=(22, 26, 24, 235), outline=(70, 110, 80, 210), width=2)
    font_map = get_font(20, bold=True)
    draw.text((map_x0 + 20, map_y0 + 20), "BẢN ĐỒ TÁC CHIẾN: BERLIN -> WARSAW", font=font_map, fill=(180, 220, 190, 240))

    berlin = (980, 560)
    warsaw = (1620, 560)
    draw.ellipse([(berlin[0] - 12, berlin[1] - 12), (berlin[0] + 12, berlin[1] + 12)], fill=(255, 50, 50, 255))
    draw.text((berlin[0], berlin[1] - 30), "BERLIN (ĐỨC)", font=font_map, fill=(255, 255, 255, 255), anchor="mm")

    draw.ellipse([(warsaw[0] - 12, warsaw[1] - 12), (warsaw[0] + 12, warsaw[1] + 12)], fill=(255, 220, 20, 255))
    draw.text((warsaw[0], warsaw[1] - 30), "WARSAW (BA LAN)", font=font_map, fill=(255, 220, 20, 255), anchor="mm")

    # Animated Blitzkrieg arrow
    arrow_p = min(1.0, max(0.0, (t - 0.2) * 2.2))
    draw_animated_arrow(img, (berlin[0] + 20, berlin[1]), (warsaw[0] - 20, warsaw[1]), arrow_p, color=(255, 40, 40), width=10, label="BLITZKRIEG")

    if arrow_p >= 0.8:
        ring_r = int(25 + math.sin(t * 20) * 15)
        draw.ellipse([(warsaw[0] - ring_r, warsaw[1] - ring_r), (warsaw[0] + ring_r, warsaw[1] + ring_r)], outline=(255, 40, 40, 200), width=3)

    return img


def render_frame_scene_004(f: int, n: int) -> Image.Image:
    """Scene 4: 1941 Barbarossa — AI Photo of Russian invasion + Troop counter rolling up to 3,000,000."""
    img = make_base_grid_canvas("dark_slate", f, n)
    t = f / n

    draw_headline_badge(img, "1941: CHIẾN DỊCH BARBAROSSA", "MẶT TRẬN PHÍA ĐÔNG", min(1.0, t * 4.0))

    # Left: AI Photo of invasion division
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_004.png"), 540, 450, "TƯ LIỆU: BỘ BINH & XE TĂNG ĐỨC 1941", -2.5)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Troop counter card
    count_p = ease_out_cubic(min(1.0, max(0.0, (t - 0.15) * 2.2)))
    troops = int(3000000 * count_p)
    troops_str = f"{troops:,}".replace(",", ".") + "+"

    c2_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if c2_prog > 0:
        card = get_cached_card_base(
            640, 480,
            "CUỘC TIẾN CÔNG LIÊN XÔ", f"QUÂN SỐ: {troops_str}",
            (
                f"• {troops_str} lính phát xít tham chiến",
                "• 3.300 xe tăng & 2.700 máy bay xuất kích",
                "• Phòng tuyến dài 2.900 km từ Baltic đến Biển Đen",
                "• Quân dân Liên Xô kiên cường bảo vệ Tổ quốc",
            ),
            210, 30, 30, 2.5
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.7) * 4.0))
        draw_fast_stamp(img, (1500, 680), "SA LẦY", stamp_p)

    return img


def render_frame_scene_005(f: int, n: int) -> Image.Image:
    """Scene 5: 1943-1944 Bước ngoặt — AI Photo of Normandy D-Day + Dual Pincer Arrows."""
    img = make_base_grid_canvas("military", f, n)
    t = f / n

    draw_headline_badge(img, "1943 - 1944: BƯỚC NGOẶT ĐẢO CHIỀU", "THẤT BẠI CHIẾN LƯỢC", min(1.0, t * 4.0))

    # Left: Stalingrad card
    c1_prog = ease_out_back(min(1.0, max(0.0, (t - 0.1) * 3.0)))
    if c1_prog > 0:
        card = get_cached_card_base(
            520, 460,
            "1943: TRẬN STALINGRAD", "MẶT TRẬN ĐÔNG ÂU",
            (
                "• Tập đoàn quân số 6 của Đức bị tiêu diệt",
                "• Đòn giáng chí mạng vào quân phát xít",
                "• Hồng quân Liên Xô phản công thần tốc",
                "• Bắt đầu cuộc tiến quân về Berlin",
            ),
            200, 30, 30, -3.0
        )
        img.paste(card, (480 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.6) * 4.0))
        draw_fast_stamp(img, (600, 680), "SỤP ĐỔ", stamp_p)

    # Right: AI Photo of Normandy D-Day
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    p_x = int(2100 - (2100 - 1380) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_005.png"), 580, 460, "TƯ LIỆU: ĐỔ BỘ NORMANDY (D-DAY 1944)", 3.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Dual pincer arrows
    arrow_p = min(1.0, max(0.0, (t - 0.4) * 2.5))
    draw_animated_arrow(img, (200, 200), (800, 400), arrow_p, color=(60, 140, 230), width=8, label="ĐỒNG MINH")
    draw_animated_arrow(img, (1720, 200), (1120, 400), arrow_p, color=(240, 40, 40), width=8, label="HỒNG QUÂN")

    return img


def render_frame_scene_006(f: int, n: int) -> Image.Image:
    """Scene 6: Holocaust — AI Photo of concentration camp tracks + Solemn highlighted dossier."""
    img = make_base_grid_canvas("crimson", f, n)
    t = f / n

    draw_headline_badge(img, "THẢM HỌA HOLOCAUST", "TỘI ÁC DIỆT CHỦNG", min(1.0, t * 4.0))

    # Left: AI Photo of camp entrance
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_006.png"), 520, 450, "TƯ LIỆU: TRẠI TẬP TRUNG TỬ THẦN 1940s", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Indictment document
    c_prog = ease_out_cubic(min(1.0, max(0.0, (t - 0.15) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            680, 480,
            "HỒ SƠ TỘI ÁC DIỆT CHỦNG", "TÀI LIỆU LƯU TRỮ QUỐC TẾ",
            (
                "DÒNG 1: HƠN 6.000.000 NGƯỜI DO THÁI BỊ TÀN SÁT CÓ HỆ THỐNG",
                "DÒNG 2: Hàng triệu thường dân vô tội và trẻ em thiệt mạng",
                "DÒNG 3: Mạng lưới các trại tập trung hủy diệt tàn bạo",
                "DÒNG 4: Tội ác chống lại nhân loại không thể dung thứ",
            ),
            180, 20, 20, 1.5
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])

        # Highlighter sweep
        hl_prog = min(1.0, max(0.0, (t - 0.3) * 2.0))
        if hl_prog > 0:
            box = (1030, 460, int(1030 + 580 * hl_prog), 490)
            img = DocumentHighlighterService.apply_highlight_sweep(
                img, box, progress=1.0, options=HighlightOptions(color_name="yellow", opacity=0.55)
            )

        stamp_prog = min(1.0, max(0.0, (t - 0.7) * 4.0))
        draw_fast_stamp(img, (1500, 680), "LÊN ÁN", stamp_prog)

    return img


def render_frame_scene_007(f: int, n: int) -> Image.Image:
    """Scene 7: 1945 Berlin sụp đổ — AI Photo of Reichstag victory + Führerbunker with red 'X' cross-out."""
    img = make_base_grid_canvas("sepia", f, n)
    t = f / n

    draw_headline_badge(img, "1945: BERLIN SỤP ĐỔ", "KẾT THÚC ĐẾ CHẾ THỨ BA", min(1.0, t * 4.0))

    # Left: AI Photo of Berlin 1945
    p_prog = ease_out_cubic(min(1.0, t * 3.0))
    p_x = int(-200 + (200 + 490) * p_prog)
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_007.png"), 520, 450, "TƯ LIỆU: BERLIN THÁNG 5 NĂM 1945", -2.0)
        img.paste(plate, (p_x - plate.width // 2, 560 - plate.height // 2), mask=plate.split()[-1])

    # Right: Führerbunker defeat card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            680, 480,
            "CHIẾN DỊCH CÔNG PHÁ BERLIN & HẦM NGẦM", "30 THÁNG 4 NĂM 1945",
            (
                "• Hồng quân Liên Xô siết chặt vòng vây toàn thành phố",
                "• Lá cờ Chiến thắng phấp phới trên nóc Tòa Quốc hội Đức",
                "• Hitler cùng người tình tự sát trong boong-ke ngầm",
                "• 08/05/1945: Phát xít Đức ký văn kiện đầu hàng không điều kiện",
            ),
            200, 30, 30, 2.0
        )
        img.paste(card, (1340 - card.width // 2, 560 - card.height // 2), mask=card.split()[-1])
        stamp_prog = min(1.0, max(0.0, (t - 0.6) * 4.0))
        draw_fast_stamp(img, (1500, 680), "ĐẦU HÀNG", stamp_prog)

    # Big red Cross-Out 'X' over the right card
    cross_p = min(1.0, max(0.0, (t - 0.7) * 3.5))
    if cross_p > 0:
        draw = ImageDraw.Draw(img)
        cx, cy = 1340, 560
        r = int(140 * cross_p)
        draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=(240, 25, 25, 220), width=8)
        draw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=(240, 25, 25, 220), width=8)

    return img


def render_frame_scene_008(f: int, n: int) -> Image.Image:
    """Scene 8: Kết luận & Bài học lịch sử — Big number count (70M) + AI Photo of Nuremberg Trials."""
    img = make_base_grid_canvas("crimson", f, n)
    t = f / n

    draw_headline_badge(img, "BÀI HỌC VĨNH CỬU CHO NHÂN LOẠI", "TỔNG KẾT LỊCH SỬ", min(1.0, t * 4.0))

    # Top: Big animated casualty number
    count_p = ease_out_cubic(min(1.0, t * 2.5))
    num = int(70000000 * count_p)
    num_str = f"{num:,}".replace(",", ".") + "+"

    draw = ImageDraw.Draw(img)
    font_big = get_font(72, bold=True)
    draw.text((WIDTH // 2, 300), num_str, font=font_big, fill=(255, 230, 20, 255), anchor="mm")

    font_sub_big = get_font(24, bold=True)
    draw.text((WIDTH // 2, 355), "SINH MẠNG THIỆT MẠNG TRONG THẾ CHIẾN THỨ HAI", font=font_sub_big, fill=(255, 255, 255, 240), anchor="mm")

    under_p = min(1.0, max(0.0, (t - 0.25) * 3.0))
    if under_p > 0:
        uw = int(720 * under_p)
        draw.line([(WIDTH // 2 - uw // 2, 385), (WIDTH // 2 + uw // 2, 385)], fill=(225, 35, 35, 240), width=5)

    # Bottom Left: AI Photo of Nuremberg courtroom
    p_prog = ease_out_back(min(1.0, max(0.0, (t - 0.3) * 3.0)))
    if p_prog > 0:
        plate = get_cached_photo_plate(str(IMAGES_DIR / "scene_008.png"), 560, 370, "TƯ LIỆU: TÒA ÁN QUỐC TẾ NUREMBERG 1945", -2.0)
        img.paste(plate, (480 - plate.width // 2, 680 - plate.height // 2), mask=plate.split()[-1])

    # Bottom Right: Conclusion Lockup Card
    c_prog = ease_out_back(min(1.0, max(0.0, (t - 0.45) * 3.0)))
    if c_prog > 0:
        card = get_cached_card_base(
            640, 370,
            "GIÁ TRỊ VĨNH CỬU CỦA HÒA BÌNH", "THÔNG ĐIỆP LỊCH SỬ",
            (
                "• Lên án chủ nghĩa phát xít & bảo vệ quyền con người",
                "• Tinh thần đoàn kết quốc tế ngăn chặn chiến tranh",
                "• Lời cảnh tỉnh đắt giá cho hòa bình của mọi quốc gia",
            ),
            200, 30, 30, 2.0
        )
        img.paste(card, (1380 - card.width // 2, 680 - card.height // 2), mask=card.split()[-1])
        stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
        draw_fast_stamp(img, (1540, 770), "HÒA BÌNH", stamp_p)

    return img


SCENE_RENDERERS = [
    render_frame_scene_001,
    render_frame_scene_002,
    render_frame_scene_003,
    render_frame_scene_004,
    render_frame_scene_005,
    render_frame_scene_006,
    render_frame_scene_007,
    render_frame_scene_008,
]


SCENES_METADATA = [
    {
        "id": "scene_001",
        "narration": "Từ một kẻ lang bạt vô danh ở Vienna, Adolf Hitler trỗi dậy trên đống đổ nát của nước Đức sau Thế chiến thứ nhất.",
        "template": "01_subject_slide_headline_pop",
    },
    {
        "id": "scene_002",
        "narration": "Năm 1933, Hitler trở thành Thủ tướng Đức, nhanh chóng thâu tóm quyền lực và thiết lập đế chế độc tài phát xít tàn bạo.",
        "template": "07_document_highlight",
    },
    {
        "id": "scene_003",
        "narration": "Ngày 1 tháng 9 năm 1939, quân đội Đức tràn qua biên giới Ba Lan. Chiến thuật chớp nhoáng Blitzkrieg đẩy toàn cầu vào thảm họa.",
        "template": "03_map_pan_marker_pulse",
    },
    {
        "id": "scene_004",
        "narration": "Năm 1941, Hitler xé bỏ hiệp ước, điều hơn ba triệu quân tràn vào Liên Xô, mở ra chiến trường đẫm máu nhất lịch sử loài người.",
        "template": "04_before_after_split",
    },
    {
        "id": "scene_005",
        "narration": "Thất bại thảm khốc tại Stalingrad và trận đổ bộ Normandy năm 1944 đã đẩy quân phát xít vào thế gọng kìm sụp đổ không thể cứu vãn.",
        "template": "06_timeline_cards",
    },
    {
        "id": "scene_006",
        "narration": "Dưới ách thống trị tàn độc, hơn sáu triệu người Do Thái cùng hàng triệu thường dân vô tội đã bị tàn sát trong các trại tập trung.",
        "template": "07_document_highlight",
    },
    {
        "id": "scene_007",
        "narration": "Tháng 4 năm 1945, khi Hồng quân Liên Xô siết chặt vòng vây Berlin, Hitler đã tự sát dưới hầm ngầm, kết thúc triều đại bóng tối.",
        "template": "11_object_zoom_texture_wipe",
    },
    {
        "id": "scene_008",
        "narration": "Thế chiến thứ hai cướp đi hơn 70 triệu sinh mạng. Sự sụp đổ của chủ nghĩa phát xít mãi là lời cảnh tỉnh đắt giá cho hòa bình thế giới.",
        "template": "12_conclusion_lockup",
    },
]


def main() -> None:
    logger.info("=== Starting High-Performance Vox Dynamic Frame-by-Frame Video Generation ===")
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
        logger.info(f"--- Rendering Dynamic Vox Scene with AI Photo: {scene_id} [{idx + 1}/8] ---")

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
    final_mp4 = final_dir / "hitler_ww2_60s_final.mp4"
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
    print(f"\n[DONE] Video Vox Motion với Ảnh Minh Họa AI hoàn tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
