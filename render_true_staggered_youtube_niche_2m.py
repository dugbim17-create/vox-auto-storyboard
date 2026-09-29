"""True Staggered Multi-Layer Vox Engine for 2-Minute YouTube Niche Strategy Video.

Zero Ken Burns full-frame zooming:
- Every scene begins on a clean physical surface (Corkboard / Slate Desk).
- Every asset (Laptop, Outlier chart, Gold polaroid, Ancient map, Magnifying glass, Noodle bowl, Cash stack, Calendar, Trophy)
  is an isolated physical cutout that slams down / slides in with spring bounce at the EXACT timestamp of the narration.
- Red yarn strings shoot across pins with natural catenary sag.
- Live yellow highlighter marker sweeps over text.
- Big rubber stamps slam down with screen shake.
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
from app.services.investigation_board import EvidenceChecklist, InvestigationBoardService, StickyNote
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("true_staggered_vox_2m")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_youtube_niche_2m")
ASSETS_DIR = PROJECT_DIR / "isolated_assets"
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


def ease_overshoot_bounce(t: float, overshoot: float = 1.35) -> float:
    t = max(0.0, min(1.0, t))
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    t -= 1.0
    return t * t * ((overshoot + 1.0) * t + overshoot) + 1.0


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)


@lru_cache(maxsize=16)
def get_prepared_sticker(name: str, target_h: int) -> Image.Image:
    raw = Image.open(ASSETS_DIR / f"{name}_cutout.png").convert("RGBA")
    scale = target_h / float(raw.height)
    new_w = max(10, int(raw.width * scale))
    new_h = max(10, int(raw.height * scale))
    fitted = raw.resize((new_w, new_h), Image.Resampling.BICUBIC)
    return PaperCraftService.create_torn_cutout(
        fitted, PaperCutoutOptions(border_width=12, roughness=0.6, shadow=True, shadow_opacity=0.55)
    )


@lru_cache(maxsize=4)
def get_corkboard() -> Image.Image:
    return InvestigationBoardService.generate_corkboard_texture(WIDTH, HEIGHT)


@lru_cache(maxsize=4)
def get_dark_desk() -> Image.Image:
    return InvestigationBoardService.generate_dark_dossier_texture(WIDTH, HEIGHT)


def draw_hud(canvas: Image.Image, frame_num: int, tag: str) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
    c_len = 22
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 220), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 220), width=3)

    font_tag = get_font(16, bold=True)
    draw.text((WIDTH // 2, 52), f"CHIẾN LƯỢC YOUTUBE // {tag.upper()}", font=font_tag, fill=(255, 220, 20, 230), anchor="mm")
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 300, 52), f"HỒ SƠ SỐ // F:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 80))


def draw_top_badge(canvas: Image.Image, title: str, subtitle: str, progress: float, color: tuple[int, int, int] = (255, 220, 20)) -> None:
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = ease_overshoot_bounce(progress, 1.3)
    w_box = int(720 * min(1.0, 0.8 + 0.2 * p))
    h_box = 84
    cx, cy = WIDTH // 2, 110

    draw.rectangle([(cx - w_box // 2, cy - h_box // 2), (cx + w_box // 2, cy + h_box // 2)], fill=(20, 24, 30, 245), outline=(*color, 255), width=2)
    font_t = get_font(28, bold=True)
    draw.text((cx, cy - 12), title.upper(), font=font_t, fill=(*color, 255), anchor="mm")
    if subtitle:
        font_s = get_font(15, bold=True)
        draw.text((cx, cy + 18), subtitle.upper(), font=font_s, fill=(255, 255, 255, 230), anchor="mm")


# --------------------------------------------------------------------------- #
# 8 Staggered Multi-Layer Scenes
# --------------------------------------------------------------------------- #
def render_scene_01(f: int, n: int) -> Image.Image:
    """Scene 1: Cạm bẫy chọn ngách sai & 90% thất bại."""
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "CẠM BẪY CHỌN NGÁCH")

    # Layer 1: Top Badge (at 0.0s)
    draw_top_badge(board, "90% NGƯỜI MỚI THẤT BẠI", "VÌ CHỌN SAI NGÁCH NGAY TỪ ĐẦU", min(1.0, t_sec / 0.6), color=(240, 50, 50))

    # Layer 2: Laptop 0 Views Sticker (Slams down from top at 1.0s)
    if t_sec >= 1.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.0) / 0.6), 1.3)
        cur_y = int(-300 + (300 + 580) * p)
        im = get_prepared_sticker("asset_laptop_0view", 480)
        im_rot = im.rotate(-3.5 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_rot, (480 - im_rot.width // 2, cur_y - im_rot.height // 2), mask=im_rot.split()[-1])

    # Layer 3: Yellow Sticky Note (Drops in at 4.5s)
    if t_sec >= 4.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 4.5) / 0.5), 1.4)
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(text="VLOG ĐỜI THƯỜNG = CHẾT ĐUỐI", subtext="KHÔNG AI QUAN TÂM BẠN LÀ AI", size=(380, 200), angle_deg=4.0)
        )
        board.paste(note, (1420 - note.width // 2, 560 - note.height // 2), mask=note.split()[-1])

    # Layer 4: Red string connects Laptop to Warning Note (at 7.5s)
    if t_sec >= 7.5:
        str_p = min(1.0, (t_sec - 7.5) / 0.8)
        InvestigationBoardService.draw_catenary_red_string(board, (480, 420), (1420, 420), sag=35.0, progress=str_p, width=5)

    # Layer 5: Giant Red Stamp: SAI LẦM CHÍ MẠNG (at 10.5s)
    if t_sec >= 10.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 10.5) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(board, (WIDTH // 2, 800), "SAI LẦM CHÍ MẠNG", angle_deg=-12.0, scale=p * 1.3)

    return board


def render_scene_02(f: int, n: int) -> Image.Image:
    """Scene 2: Chỉ số Outlier Ratio 3x - 35x."""
    t_sec = f / float(FPS)
    board = get_dark_desk().copy()
    draw_hud(board, f, "CÔNG THỨC OUTLIER")

    draw_top_badge(board, "QUY TẮC VÀNG: OUTLIER RATIO", "TÌM KÊNH < 50K SUBS NHƯNG VIEW ĐỘT BIẾN", min(1.0, t_sec / 0.6), color=(40, 240, 90))

    # Layer 2: Outlier Chart Sticker (Slams in at 1.0s)
    if t_sec >= 1.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.0) / 0.6), 1.3)
        cur_x = int(-400 + (400 + 520) * p)
        im = get_prepared_sticker("asset_outlier_chart", 480)
        im_rot = im.rotate(-3.0 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_rot, (cur_x - im_rot.width // 2, 580 - im_rot.height // 2), mask=im_rot.split()[-1])

    # Layer 3: Odometer: OUTLIER 35X VIEW (Rolls in at 4.5s)
    if t_sec >= 4.5:
        p = ease_out_cubic(min(1.0, (t_sec - 4.5) / 1.8))
        mult = int(35 * p)
        draw = ImageDraw.Draw(board)
        draw.rectangle([(1100, 480), (1740, 600)], fill=(16, 22, 28, 245), outline=(40, 240, 90, 255), width=3)
        font_num = get_font(52, bold=True)
        draw.text((1420, 540), f"OUTLIER: {mult}X VIEW", font=font_num, fill=(40, 240, 90, 255), anchor="mm")

    # Layer 4: Sticky Note (at 8.0s)
    if t_sec >= 8.0:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(text="CHỦ ĐỀ ĐANG ĐƯỢC THÈM KHÁT", subtext="CẦU VƯỢT QUÁ CUNG TRÊN YOUTUBE", size=(380, 190), angle_deg=-4.0)
        )
        board.paste(note, (1420 - note.width // 2, 740 - note.height // 2), mask=note.split()[-1])

    # Layer 5: Green Stamp: XÁC NHẬN NGÁCH THẮNG (at 11.5s)
    if t_sec >= 11.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 11.5) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(board, (WIDTH // 2, 850), "XÁC NHẬN NGÁCH THẮNG", angle_deg=8.0, color=(30, 210, 70), scale=p * 1.3)

    return board


def render_scene_03(f: int, n: int) -> Image.Image:
    """Scene 3: Tam Giác Ngách Bất Tử: Tài Chính, Lịch Sử & Điều Tra."""
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "3 TRỤ CỘT BẤT TỬ")

    draw_top_badge(board, "3 NGÁCH NỘI DUNG CPM CAO NHẤT", "TÀI CHÍNH • LỊCH SỬ • PHÓNG SỰ ĐIỀU TRA", min(1.0, t_sec / 0.6), color=(255, 215, 0))

    # Layer 2: Polaroid 1 - Gold Bullion / Finance (Drops at 1.0s)
    if t_sec >= 1.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.0) / 0.5), 1.3)
        im1 = get_prepared_sticker("asset_gold_polaroid", 360)
        im1_rot = im1.rotate(-4.0 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im1_rot, (380 - im1_rot.width // 2, 560 - im1_rot.height // 2), mask=im1_rot.split()[-1])

    # Layer 3: Polaroid 2 - Ancient Map / History (Drops at 4.0s)
    if t_sec >= 4.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 4.0) / 0.5), 1.3)
        im2 = get_prepared_sticker("asset_ancient_map", 360)
        im2_rot = im2.rotate(3.0 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im2_rot, (960 - im2_rot.width // 2, 560 - im2_rot.height // 2), mask=im2_rot.split()[-1])

    # Layer 4: Polaroid 3 - Detective Case / Investigation (Drops at 7.0s)
    if t_sec >= 7.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 7.0) / 0.5), 1.3)
        im3 = get_prepared_sticker("asset_magnifying_glass", 360)
        im3_rot = im3.rotate(-3.5 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im3_rot, (1540 - im3_rot.width // 2, 560 - im3_rot.height // 2), mask=im3_rot.split()[-1])

    # Layer 5: Red Strings connecting 1 -> 2 -> 3 (at 9.5s)
    if t_sec >= 9.5:
        str_p = min(1.0, (t_sec - 9.5) / 0.8)
        InvestigationBoardService.draw_catenary_red_string(board, (380, 420), (960, 420), sag=25.0, progress=str_p, width=5)
        InvestigationBoardService.draw_catenary_red_string(board, (960, 420), (1540, 420), sag=25.0, progress=str_p, width=5)

    # Layer 6: Sticky Note: CPM $15 - $30 (at 11.5s)
    if t_sec >= 11.5:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(text="CPM $15 - $30 / 1.000 VIEWS", subtext="THỊ TRƯỜNG DỒI DÀO TƯ LIỆU", size=(360, 160), angle_deg=2.0)
        )
        board.paste(note, (WIDTH // 2 - note.width // 2, 820 - note.height // 2), mask=note.split()[-1])

    return board


def render_scene_04(f: int, n: int) -> Image.Image:
    """Scene 4: Công thức 3 Điểm Chạm: Cung Cầu & Năng Lực AI."""
    t_sec = f / float(FPS)
    board = get_dark_desk().copy()
    draw_hud(board, f, "CÔNG THỨC 3 ĐIỂM CHẠM")

    draw_top_badge(board, "GIAO ĐIỂM NGÁCH CHIẾN THẮNG", "NHU CẦU CAO • TƯ LIỆU DỄ TÌM • AI TỰ ĐỘNG HÓA", min(1.0, t_sec / 0.6), color=(50, 220, 240))

    # 3 Strategic Circles popping in sequentially
    draw = ImageDraw.Draw(board)
    centers = [(500, 540), (960, 540), (1420, 540)]
    labels = [
        ("1. NHU CẦU CAO", "Khán giả háo hức tìm kiếm"),
        ("2. TƯ LIỆU DỒI DÀO", "Báo chí & lịch sử vô tận"),
        ("3. TỰ ĐỘNG HÓA AI", "Sản xuất nhanh bằng AI"),
    ]

    for idx, (c_pos, (t1, t2)) in enumerate(zip(centers, labels)):
        trig_t = 1.0 + idx * 2.5
        if t_sec >= trig_t:
            p = ease_overshoot_bounce(min(1.0, (t_sec - trig_t) / 0.5), 1.3)
            r = int(180 * p)
            draw.ellipse([(c_pos[0] - r, c_pos[1] - r), (c_pos[0] + r, c_pos[1] + r)], fill=(20, 30, 42, 230), outline=(50, 220, 240, 240), width=3)
            draw.text((c_pos[0], c_pos[1] - 15), t1, font=get_font(20, bold=True), fill=(255, 220, 20, 255), anchor="mm")
            draw.text((c_pos[0], c_pos[1] + 20), t2, font=get_font(15, bold=False), fill=(220, 240, 255, 230), anchor="mm")

    # Live Highlighter across intersection (at 9.0s)
    if t_sec >= 9.0:
        hl_p = min(1.0, (t_sec - 9.0) / 1.8)
        box = (WIDTH // 2 - 360, 780, int(WIDTH // 2 - 360 + 720 * hl_p), 850)
        board = DocumentHighlighterService.apply_highlight_sweep(board, box, progress=1.0)
        draw = ImageDraw.Draw(board)
        draw.text((WIDTH // 2, 815), "KHÔNG CẦN LỘ MẶT • 100% TỰ ĐỘNG HÓA", font=get_font(24, bold=True), fill=(16, 20, 24, 255), anchor="mm")

    return board


def render_scene_05(f: int, n: int) -> Image.Image:
    """Scene 5: Đòn Bẩy RPM/CPM: Bát Phở Việt Nam vs 1000 View Ngoại."""
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "TỐI ƯU RPM / CPM")

    draw_top_badge(board, "ĐÒN BẨY NGOẠI TỆ (USD)", "1.000 VIEW MỸ/ÂU = 15$ - 30$ RPM", min(1.0, t_sec / 0.6), color=(40, 240, 90))

    # Layer 2: Left Photo - Noodle Bowl / Local View (Slams at 1.0s)
    if t_sec >= 1.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.0) / 0.6), 1.3)
        im_noodle = get_prepared_sticker("asset_noodle_bowl", 400)
        im_rot = im_noodle.rotate(-4.0 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_rot, (480 - im_rot.width // 2, 560 - im_rot.height // 2), mask=im_rot.split()[-1])

        draw = ImageDraw.Draw(board)
        draw.rectangle([(280, 780), (680, 850)], fill=(35, 20, 20, 245), outline=(220, 40, 40, 255), width=2)
        draw.text((480, 815), "VIEW NỘI: $0.50 RPM", font=get_font(24, bold=True), fill=(240, 60, 60, 255), anchor="mm")

    # Layer 3: Right Photo - Cash Stacks / Global View (Slams at 4.5s)
    if t_sec >= 4.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 4.5) / 0.6), 1.3)
        im_cash = get_prepared_sticker("asset_cash_stack", 400)
        im_rot = im_cash.rotate(3.5 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_rot, (1440 - im_rot.width // 2, 560 - im_rot.height // 2), mask=im_rot.split()[-1])

        p_val = ease_out_cubic(min(1.0, (t_sec - 4.5) / 2.0))
        val = int(30 * p_val)
        draw = ImageDraw.Draw(board)
        draw.rectangle([(1240, 780), (1640, 850)], fill=(16, 35, 20, 245), outline=(40, 240, 90, 255), width=3)
        draw.text((1440, 815), f"VIEW NGOẠI: ${val}.00 RPM", font=get_font(26, bold=True), fill=(40, 240, 90, 255), anchor="mm")

    # Layer 4: Sticky Note in Center (at 8.5s)
    if t_sec >= 8.5:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(text="CÙNG 1 CÔNG SẢN XUẤT", subtext="HÃY CHỌN THỊ TRƯỜNG TRẢ TIỀN CAO", size=(360, 180), angle_deg=-4.0)
        )
        board.paste(note, (WIDTH // 2 - note.width // 2, 560 - note.height // 2), mask=note.split()[-1])

    # Layer 5: Stamp OPTIMIZE (at 11.5s)
    if t_sec >= 11.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 11.5) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(board, (WIDTH // 2, 800), "TỐI ƯU RPM QUỐC TẾ", angle_deg=-10.0, color=(30, 200, 70), scale=p * 1.3)

    return board


def render_scene_06(f: int, n: int) -> Image.Image:
    """Scene 6: Kỹ Thuật Đạo Nhái Có Trí Tuệ (Reverse-Engineering)."""
    t_sec = f / float(FPS)
    board = get_dark_desk().copy()
    draw_hud(board, f, "BÓC TÁCH VIRAL")

    draw_top_badge(board, "KỸ THUẬT REVERSE-ENGINEERING", "BÓC TÁCH 30 GIÂY ĐẦU CỦA 5 VIDEO VIRAL NHẤT", min(1.0, t_sec / 0.6), color=(255, 215, 0))

    # Layer 2: Checklist Dossier (Slams in at 1.5s)
    if t_sec >= 1.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.5) / 0.6), 1.3)
        chk = EvidenceChecklist(
            title="3 YẾU TỐ GIỮ CHÂN KHÁN GIẢ",
            items=[
                ("Hook 3 giây đầu trực diện, gay cấn", True),
                ("Micro-beat 2.5s đổi khung hình liên tục", True),
                ("Thumbnail CTR > 10% gây tò mò cao", True),
            ],
            size=(560, 320),
            angle_deg=-3.0 * p,
        )
        rchk = InvestigationBoardService.render_checklist_dossier(chk)
        board.paste(rchk, (WIDTH // 2 - rchk.width // 2, 580 - rchk.height // 2), mask=rchk.split()[-1])

    # Layer 3: Stamp DECONSTRUCT (at 10.5s)
    if t_sec >= 10.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 10.5) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(board, (WIDTH // 2, 820), "BÓC TÁCH HOÀN TẤT", angle_deg=8.0, scale=p * 1.3)

    return board


def render_scene_07(f: int, n: int) -> Image.Image:
    """Scene 7: Kế Hoạch Bắn Phá 30 Ngày Đầu (15 Videos)."""
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "KẾ HOẠCH BẮN PHÁ")

    draw_top_badge(board, "KẾ HOẠCH BẮN PHÁ 30 NGÀY", "SẢN XUẤT 10 - 15 VIDEO ĐẦU TIÊN ĐỀU ĐẶN", min(1.0, t_sec / 0.6), color=(255, 140, 40))

    # Layer 2: Calendar Roadmap (Slams in at 1.0s)
    if t_sec >= 1.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.0) / 0.6), 1.3)
        im_cal = get_prepared_sticker("asset_calendar_roadmap", 460)
        im_rot = im_cal.rotate(-3.0 * p, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_rot, (480 - im_rot.width // 2, 580 - im_rot.height // 2), mask=im_rot.split()[-1])

    # Layer 3: Odometer: 30 NGÀY • 15 VIDEOS (at 4.5s)
    if t_sec >= 4.5:
        p = ease_out_cubic(min(1.0, (t_sec - 4.5) / 2.0))
        days = int(30 * p)
        draw = ImageDraw.Draw(board)
        draw.rectangle([(1100, 460), (1780, 560)], fill=(20, 24, 30, 245), outline=(255, 140, 40, 255), width=3)
        font_d = get_font(38, bold=True)
        draw.text((1440, 510), f"MỤC TIÊU: {days} NGÀY • 15 VIDEOS", font=font_d, fill=(255, 160, 40, 255), anchor="mm")

    # Layer 4: Sticky Note (at 8.0s)
    if t_sec >= 8.0:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(text="KHÔNG BỎ CUỘC Ở VIDEO 03", subtext="THUẬT TOÁN CẦN DỮ LIỆU ĐỂ ĐẨY KÊNH", size=(380, 190), angle_deg=4.0)
        )
        board.paste(note, (1440 - note.width // 2, 740 - note.height // 2), mask=note.split()[-1])

    return board


def render_scene_08(f: int, n: int) -> Image.Image:
    """Scene 8: Đúc Kết & Hành Động Ngay."""
    t_sec = f / float(FPS)
    board = get_dark_desk().copy()
    draw_hud(board, f, "HÀNH ĐỘNG NGAY")

    draw_top_badge(board, "CHỌN ĐÚNG NGÁCH = THẮNG 50%", "BẮT ĐẦU NGAY VỚI ĐÒN BẨY TỰ ĐỘNG VOX STUDIO", min(1.0, t_sec / 0.6), color=(255, 215, 0))

    # Layer 2: Gold Trophy (Slams in at 1.0s)
    if t_sec >= 1.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 1.0) / 0.6), 1.3)
        im_trophy = get_prepared_sticker("asset_gold_trophy", 440)
        board.paste(im_trophy, (WIDTH // 2 - im_trophy.width // 2, 540 - im_trophy.height // 2), mask=im_trophy.split()[-1])

    # Layer 3: Quote Lockup (at 4.5s)
    if t_sec >= 4.5:
        draw = ImageDraw.Draw(board)
        draw.rectangle([(WIDTH // 2 - 460, 770), (WIDTH // 2 + 460, 880)], fill=(16, 20, 26, 245), outline=(255, 215, 0, 255), width=3)
        font_q = get_font(32, bold=True)
        draw.text((WIDTH // 2, 805), "HÃY BẮT ĐẦU NGAY TỪ HÔM NAY!", font=font_q, fill=(255, 230, 20, 255), anchor="mm")
        font_qs = get_font(18, bold=True)
        draw.text((WIDTH // 2, 848), "TỰ ĐỘNG HÓA NỘI DUNG • THỐNG TRỊ THỊ TRƯỜNG", font=font_qs, fill=(255, 255, 255, 230), anchor="mm")

    # Layer 4: Giant Stamp ACTION NOW (at 10.0s)
    if t_sec >= 10.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 10.0) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(board, (WIDTH // 2, 540), "HÀNH ĐỘNG NGAY", angle_deg=-10.0, scale=p * 1.4)

    return board


SCENES = [
    {
        "id": "scene_01",
        "narration": "Chín mươi phần trăm người mới làm YouTube thất bại ngay từ tuần đầu tiên vì chọn sai ngách: làm vlog đời thường hoặc lao vào những ngách quá bão hòa mà không ai quan tâm.",
        "renderer": render_scene_01,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("paper_slide", 4600), ("whoosh", 7600), ("camera_click", 10600)],
    },
    {
        "id": "scene_02",
        "narration": "Đừng nhìn vào những kênh triệu sub đã làm mười năm. Hãy tìm những kênh nhỏ dưới năm mươi ngàn đăng ký nhưng video đạt lượng xem đột biến gấp ba đến ba mươi lăm lần.",
        "renderer": render_scene_02,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("typewriter", 4600), ("paper_slide", 8100), ("camera_click", 11600)],
    },
    {
        "id": "scene_03",
        "narration": "Ba ngách kiếm tiền bền vững và CPM cao nhất mọi thời đại: Phóng sự tài chính, Tài liệu lịch sử, và Hồ sơ bí ẩn chưa có lời giải.",
        "renderer": render_scene_03,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("pushpin_hit", 4100), ("pushpin_hit", 7100), ("whoosh", 9600)],
    },
    {
        "id": "scene_04",
        "narration": "Một ngách chiến thắng nằm ở giao điểm của ba yếu tố: Nhu cầu khán giả cao, Nguồn tư liệu dồi dào, và Khả năng sản xuất tự động bằng công cụ trí tuệ nhân tạo.",
        "renderer": render_scene_04,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("pushpin_hit", 3600), ("pushpin_hit", 6100), ("marker_sweep", 9100)],
    },
    {
        "id": "scene_05",
        "narration": "Cùng một công sức làm video, nhưng một ngàn lượt xem từ Mỹ hay Châu Âu mang lại mười lăm đến ba mươi đô la, trong khi làm view nội địa chỉ đủ mua một bát phở.",
        "renderer": render_scene_05,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("pushpin_hit", 4600), ("paper_slide", 8600), ("camera_click", 11600)],
    },
    {
        "id": "scene_06",
        "narration": "Bóc tách cấu trúc ba mươi giây đầu của năm video viral nhất trong ngách: Học cách họ đặt câu hỏi mở đầu, nhịp dựng micro-beat dồn dập và cách thiết kế ảnh bìa thumbnail.",
        "renderer": render_scene_06,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1600), ("camera_click", 10600)],
    },
    {
        "id": "scene_07",
        "narration": "Đừng tốn cả tháng trau chuốt một video duy nhất. Hãy lên kế hoạch sản xuất mười đến mười lăm video đầu tiên theo nhịp độ đều đặn để thuật toán YouTube hiểu và phân phối kênh.",
        "renderer": render_scene_07,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("typewriter", 4600), ("paper_slide", 8100)],
    },
    {
        "id": "scene_08",
        "narration": "Chọn đúng ngách là bạn đã thắng một nửa cuộc chơi. Hãy bắt đầu ngay hôm nay từ một ngách nhỏ, làm sâu và dùng đòn bẩy tự động hóa để thống trị thị trường!",
        "renderer": render_scene_08,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 1100), ("paper_slide", 4600), ("camera_click", 10100)],
    },
]


def main() -> None:
    logger.info("=== Starting True Staggered 2-Minute Vox Video Render ===")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = PROJECT_DIR / "scenes"
    audio_dir = PROJECT_DIR / "audio"
    final_dir = PROJECT_DIR / "final"
    for d in (scenes_dir, audio_dir, final_dir):
        d.mkdir(parents=True, exist_ok=True)

    voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))
    scene_mp4s: list[Path] = []
    durations_ms: list[int] = []
    subtitle_entries: list[SubtitleEntry] = []
    current_time_ms = 0
    sfx_service = AutoSFXService()

    for idx, scene in enumerate(SCENES):
        scene_id = scene["id"]
        narration = scene["narration"]
        logger.info(f"--- Rendering Scene: {scene_id} [{idx + 1}/8] ---")

        # Synthesize Voice
        voice_wav = audio_dir / f"{scene_id}_voice.wav"
        if not voice_wav.is_file():
            with wave.open(str(voice_wav), "wb") as wf:
                voice.synthesize_wav(narration, wf)

        with wave.open(str(voice_wav), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_ms = max(13500, int((frames / float(rate)) * 1000) + 800)

        durations_ms.append(duration_ms)
        total_frames = int(round(duration_ms / 1000.0 * FPS))

        subtitle_entries.append(
            SubtitleEntry(
                index=idx + 1,
                start_ms=current_time_ms + 100,
                end_ms=current_time_ms + duration_ms - 200,
                text=narration,
            )
        )
        current_time_ms += duration_ms

        sfx_events = [
            SFXEvent(sfx_type=sfx_type, start_ms=st_ms, volume_db=-3.0)
            for sfx_type, st_ms in scene["sfx_timeline"]
        ]
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

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
        renderer_fn = scene["renderer"]

        for f in range(total_frames):
            frame_img = renderer_fn(f, total_frames)
            proc.stdin.write(frame_img.tobytes())

        proc.stdin.close()
        proc.wait()
        t1 = time.time()

        SceneAudioMuxer().mux(silent_scene_mp4, scene_audio_wav, scene_mp4, fps=30)
        logger.info(f"Rendered {total_frames} frames in {t1 - t0:.2f}s -> {scene_mp4}")
        scene_mp4s.append(scene_mp4)

    # Subtitles
    srt_path = final_dir / "subtitles.srt"
    srt_path.write_text(entries_to_srt(subtitle_entries), encoding="utf-8")

    # Master Audio track
    audio_concat_list = audio_dir / "audio_concat.txt"
    concat_lines = [f"file '{Path(audio_dir / (s['id'] + '_audio.wav')).resolve().as_posix()}'" for s in SCENES]
    audio_concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    full_voice_wav = audio_dir / "full_voice_sfx.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
        "-c:a", "pcm_s16le", str(full_voice_wav)
    ], check=True, capture_output=True)

    bgm_wav = audio_dir / "strategy_bgm.wav"
    dur_s = sum(durations_ms) / 1000.0 + 2.0
    bgm_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc=sin(2*PI*65*t)*0.16 + sin(2*PI*130*t)*0.08 + sin(2*PI*260*t)*0.04:d={dur_s:.3f}:s=48000",
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

    final_mp4 = final_dir / "true_staggered_youtube_niche_2m.mp4"
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
    print(f"\n[DONE] Video True Staggered 2-Minute Hoàn Tất tại: {output_path.resolve()}")


if __name__ == "__main__":
    main()
