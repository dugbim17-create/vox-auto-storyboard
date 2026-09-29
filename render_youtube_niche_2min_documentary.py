"""2-Minute Vox Documentary Masterpiece: 'Bí Quyết Chọn Ngách YouTube Cho Người Mới Bắt Đầu'.

Implements 100% of the YouTube & MMO benchmark standards:
1. 8 Comprehensive Scenes (each 14-16s) structured into high-retention micro-beats.
2. Full-bleed AI-generated tactile torn-paper collage visuals.
3. Multi-layer staggered popups synchronized with Piper TTS ('Ngọc Huyền').
4. Real-time Odometer rolling counters (Outlier 35x, RPM $30.00, 30 Days).
5. Live yellow highlighter swipes on strategic concepts.
6. Catenary red yarn strings connecting investigative evidence.
7. Precise Foley SFX (whoosh, pushpin_hit, paper_slide, camera_click, typewriter).
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
logger = logging.getLogger("youtube_niche_2m")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_youtube_niche_2m")
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


def ease_overshoot_bounce(t: float, overshoot: float = 1.4) -> float:
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


# --------------------------------------------------------------------------- #
# Image Processors & HUD Overlays
# --------------------------------------------------------------------------- #
def render_tactile_camera_shot(
    img_path: str,
    t_norm: float,
    zoom_start: float = 1.0,
    zoom_end: float = 1.08,
    pan_x_max: int = 35,
    pan_y_max: int = -20,
) -> Image.Image:
    im = Image.open(img_path).convert("RGB")
    cur_zoom = zoom_start + (zoom_end - zoom_start) * (1.0 - math.pow(1.0 - t_norm, 2.5))
    target_w = int(WIDTH * cur_zoom)
    target_h = int(HEIGHT * cur_zoom)
    im_scaled = im.resize((target_w, target_h), Image.Resampling.BICUBIC)

    cur_pan_x = int(pan_x_max * math.sin(t_norm * math.pi * 0.8))
    cur_pan_y = int(pan_y_max * t_norm)

    crop_x0 = max(0, min(im_scaled.width - WIDTH, (target_w - WIDTH) // 2 + cur_pan_x))
    crop_y0 = max(0, min(im_scaled.height - HEIGHT, (target_h - HEIGHT) // 2 + cur_pan_y))

    frame = im_scaled.crop((crop_x0, crop_y0, crop_x0 + WIDTH, crop_y0 + HEIGHT)).convert("RGBA")
    grain = PaperCraftService.generate_film_grain_texture(WIDTH, HEIGHT, intensity=0.03)
    return Image.alpha_composite(frame, grain)


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
    draw.text((WIDTH - 300, 52), f"CASE STUDY // F:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 80))


def draw_top_pill_badge(canvas: Image.Image, title: str, subtitle: str, progress: float, color: tuple[int, int, int] = (255, 220, 20)) -> None:
    if progress <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    p = ease_overshoot_bounce(progress, 1.4)
    w_box = int(680 * min(1.0, 0.8 + 0.2 * p))
    h_box = 80
    cx, cy = WIDTH // 2, 110

    draw.rectangle([(cx - w_box // 2, cy - h_box // 2), (cx + w_box // 2, cy + h_box // 2)], fill=(20, 24, 30, 245), outline=(*color, 255), width=2)
    font_t = get_font(28, bold=True)
    draw.text((cx, cy - 10), title.upper(), font=font_t, fill=(*color, 255), anchor="mm")
    if subtitle:
        font_s = get_font(15, bold=True)
        draw.text((cx, cy + 20), subtitle.upper(), font=font_s, fill=(255, 255, 255, 230), anchor="mm")


# --------------------------------------------------------------------------- #
# 8 Full Staggered Scene Renderers (15s per scene, total 120s)
# --------------------------------------------------------------------------- #
def render_scene_01(f: int, n: int) -> Image.Image:
    """Scene 1: Cạm bẫy chọn ngách sai & 90% thất bại."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene1_trap.png"), f / n, 1.0, 1.07, 30, -15)
    draw_hud(frame, f, "CẠM BẪY CHỌN NGÁCH")

    # Layer 1: Top badge
    draw_top_pill_badge(frame, "90% NGƯỜI MỚI THẤT BẠI", "VÌ CHỌN SAI NGÁCH NGAY TỪ ĐẦU", min(1.0, t_sec / 0.8), color=(240, 50, 50))

    # Layer 2: 0 VIEWS Alert (at 4.0s)
    if t_sec >= 4.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 4.0) / 0.6), 1.5)
        draw = ImageDraw.Draw(frame)
        draw.rectangle([(WIDTH // 2 - 240, 760), (WIDTH // 2 + 240, 850)], fill=(180, 25, 25, 245), outline=(255, 255, 255, 255), width=3)
        font_big = get_font(int(46 * p), bold=True)
        draw.text((WIDTH // 2, 805), "FLATLINE: 0 VIEWS", font=font_big, fill=(255, 255, 255, 255), anchor="mm")

    # Layer 3: Sticky Note (at 8.0s)
    if t_sec >= 8.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 8.0) / 0.5), 1.4)
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(
                text="VLOG ĐỜI THƯỜNG = CHẾT ĐUỐI",
                subtext="KHÔNG AI QUAN TÂM BẠN LÀ AI",
                size=(360, 190),
                angle_deg=-5.0,
            )
        )
        frame.paste(note, (WIDTH // 2 - note.width // 2, 540 - note.height // 2), mask=note.split()[-1])

    # Layer 4: Stamp MISTAKE (at 11.5s)
    if t_sec >= 11.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 11.5) / 0.4), 1.6)
        InvestigationBoardService.render_investigation_stamp(frame, (WIDTH // 2, 540), "SAI LẦM CHÍ MẠNG", angle_deg=-12.0, scale=p * 1.3)

    return frame


def render_scene_02(f: int, n: int) -> Image.Image:
    """Scene 2: Chỉ số Outlier Ratio 3x - 35x."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene2_outlier.png"), f / n, 1.05, 1.0, -35, 20)
    draw_hud(frame, f, "CÔNG THỨC OUTLIER")

    # Layer 1: Top badge
    draw_top_pill_badge(frame, "QUY TẮC VÀNG: OUTLIER RATIO", "TÌM KÊNH < 50K SUBS NHƯNG VIEW ĐỘT BIẾN", min(1.0, t_sec / 0.8), color=(40, 220, 90))

    # Layer 2: Rolling Odometer Multiplier: OUTLIER 35X (at 3.5s)
    if t_sec >= 3.5:
        p = ease_out_cubic(min(1.0, (t_sec - 3.5) / 2.0))
        mult = int(35 * p)
        val_str = f"OUTLIER: {mult}X VIEW"

        draw = ImageDraw.Draw(frame)
        draw.rectangle([(WIDTH // 2 - 320, 770), (WIDTH // 2 + 320, 870)], fill=(16, 22, 28, 245), outline=(40, 240, 90, 255), width=3)
        font_num = get_font(56, bold=True)
        draw.text((WIDTH // 2, 820), val_str, font=font_num, fill=(40, 240, 90, 255), anchor="mm")

    # Layer 3: Sticky Note (at 8.5s)
    if t_sec >= 8.5:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(
                text="CHỦ ĐỀ ĐANG ĐƯỢC THÈM KHÁT",
                subtext="CẦU VƯỢT QUÁ CUNG TRÊN YOUTUBE",
                size=(360, 190),
                angle_deg=6.0,
            )
        )
        frame.paste(note, (WIDTH // 2 - note.width // 2, 540 - note.height // 2), mask=note.split()[-1])

    # Layer 4: Stamp VERIFIED WINNER (at 12.0s)
    if t_sec >= 12.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 12.0) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(frame, (WIDTH // 2, 540), "XÁC NHẬN NGÁCH THẮNG", angle_deg=8.0, color=(30, 200, 70), scale=p * 1.3)

    return frame


def render_scene_03(f: int, n: int) -> Image.Image:
    """Scene 3: Tam Giác Ngách Bất Tử: Tài Chính, Lịch Sử & Điều Tra."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene3_pillars.png"), f / n, 1.0, 1.07, 30, -20)
    draw_hud(frame, f, "3 TRỤ CỘT BẤT TỬ")

    draw_top_pill_badge(frame, "3 NGÁCH NỘI DUNG CPM CAO NHẤT", "TÀI CHÍNH • LỊCH SỬ • PHÓNG SỰ ĐIỀU TRA", min(1.0, t_sec / 0.8), color=(255, 215, 0))

    # Layer 2: 3 Pillars Callouts popping sequentially (at 3.0s, 6.0s, 9.0s)
    draw = ImageDraw.Draw(frame)
    if t_sec >= 3.0:
        p1 = ease_overshoot_bounce(min(1.0, (t_sec - 3.0) / 0.5), 1.4)
        draw.rectangle([(220, 760), (620, 840)], fill=(20, 30, 45, 240), outline=(255, 215, 0, 255), width=2)
        draw.text((420, 800), "1. TÀI CHÍNH (FINANCE)", font=get_font(int(24 * p1), bold=True), fill=(255, 215, 0, 255), anchor="mm")

    if t_sec >= 6.0:
        p2 = ease_overshoot_bounce(min(1.0, (t_sec - 6.0) / 0.5), 1.4)
        draw.rectangle([(760, 760), (1160, 840)], fill=(35, 25, 20, 240), outline=(220, 130, 40, 255), width=2)
        draw.text((960, 800), "2. LỊCH SỬ (HISTORY)", font=get_font(int(24 * p2), bold=True), fill=(240, 150, 50, 255), anchor="mm")

    if t_sec >= 9.0:
        p3 = ease_overshoot_bounce(min(1.0, (t_sec - 9.0) / 0.5), 1.4)
        draw.rectangle([(1300, 760), (1700, 840)], fill=(35, 18, 20, 240), outline=(220, 40, 40, 255), width=2)
        draw.text((1500, 800), "3. ĐIỀU TRA (CRIME)", font=get_font(int(24 * p3), bold=True), fill=(240, 60, 60, 255), anchor="mm")

    # Layer 3: Red String connection (at 11.0s)
    if t_sec >= 11.0:
        InvestigationBoardService.draw_catenary_red_string(frame, (420, 760), (960, 760), sag=25.0, progress=1.0, width=4)
        InvestigationBoardService.draw_catenary_red_string(frame, (960, 760), (1500, 760), sag=25.0, progress=1.0, width=4)

    return frame


def render_scene_04(f: int, n: int) -> Image.Image:
    """Scene 4: Công thức 3 Điểm Chạm: Cung Cầu & Năng Lực AI."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene4_venn.png"), f / n, 1.06, 1.0, -30, 15)
    draw_hud(frame, f, "CÔNG THỨC 3 ĐIỂM CHẠM")

    draw_top_pill_badge(frame, "GIAO ĐIỂM NGÁCH CHIẾN THẮNG", "NHU CẦU CAO • TƯ LIỆU DỄ TÌM • AI TỰ ĐỘNG HÓA", min(1.0, t_sec / 0.8), color=(50, 220, 240))

    # Layer 2: Live yellow highlighter sweep over AI AUTOMATION (at 4.5s)
    if t_sec >= 4.5:
        hl_p = min(1.0, max(0.0, (t_sec - 4.5) / 2.0))
        box = (WIDTH // 2 - 400, 760, int(WIDTH // 2 - 400 + 800 * hl_p), 830)
        frame = DocumentHighlighterService.apply_highlight_sweep(frame, box, progress=1.0)
        draw = ImageDraw.Draw(frame)
        draw.text((WIDTH // 2, 795), "ĐÒN BẨY SẢN XUẤT TỰ ĐỘNG BẰNG AI", font=get_font(28, bold=True), fill=(20, 24, 28, 255), anchor="mm")

    # Layer 3: Sticky Note (at 9.0s)
    if t_sec >= 9.0:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(
                text="KHÔNG CẦN LỘ MẶT",
                subtext="100% SẢN XUẤT BẰNG AI WORKFLOW",
                size=(340, 180),
                angle_deg=-6.0,
            )
        )
        frame.paste(note, (WIDTH // 2 - note.width // 2, 540 - note.height // 2), mask=note.split()[-1])

    return frame


def render_scene_05(f: int, n: int) -> Image.Image:
    """Scene 5: Đòn Bẩy RPM/CPM: Bát Phở Việt Nam vs 1000 View Ngoại."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene5_rpm.png"), f / n, 1.0, 1.07, 35, -20)
    draw_hud(frame, f, "TỐI ƯU RPM / CPM")

    draw_top_pill_badge(frame, "ĐÒN BẨY NGOẠI TỆ (USD)", "1.000 VIEW MỸ/ÂU = 15$ - 30$ RPM", min(1.0, t_sec / 0.8), color=(40, 240, 90))

    # Layer 2: Split comparison indicators (at 3.5s)
    draw = ImageDraw.Draw(frame)
    if t_sec >= 3.5:
        # Left: Local RPM $0.5
        draw.rectangle([(260, 760), (660, 850)], fill=(35, 20, 20, 245), outline=(220, 40, 40, 255), width=2)
        draw.text((460, 805), "VIEW NỘI: $0.50 RPM", font=get_font(26, bold=True), fill=(240, 60, 60, 255), anchor="mm")

        # Right: Global RPM $30.00
        p = ease_out_cubic(min(1.0, (t_sec - 3.5) / 2.0))
        val = int(30 * p)
        draw.rectangle([(1260, 760), (1660, 850)], fill=(16, 35, 20, 245), outline=(40, 240, 90, 255), width=3)
        draw.text((1460, 805), f"VIEW NGOẠI: ${val}.00 RPM", font=get_font(28, bold=True), fill=(40, 240, 90, 255), anchor="mm")

    # Layer 3: Sticky note in center (at 8.5s)
    if t_sec >= 8.5:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(
                text="CÙNG 1 CÔNG LÀM VIDEO",
                subtext="HÃY CHỌN THỊ TRƯỜNG TRẢ TIỀN CAO",
                size=(360, 190),
                angle_deg=4.0,
            )
        )
        frame.paste(note, (WIDTH // 2 - note.width // 2, 540 - note.height // 2), mask=note.split()[-1])

    # Layer 4: Stamp OPTIMIZE RPM (at 12.0s)
    if t_sec >= 12.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 12.0) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(frame, (WIDTH // 2, 540), "TỐI ƯU RPM QUỐC TẾ", angle_deg=-10.0, color=(30, 200, 70), scale=p * 1.3)

    return frame


def render_scene_06(f: int, n: int) -> Image.Image:
    """Scene 6: Kỹ Thuật Đạo Nhái Có Trí Tuệ (Reverse-Engineering)."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene6_blueprint.png"), f / n, 1.05, 1.0, -30, 15)
    draw_hud(frame, f, "BÓC TÁCH VIRAL")

    draw_top_pill_badge(frame, "KỸ THUẬT REVERSE-ENGINEERING", "BÓC TÁCH 30 GIÂY ĐẦU CỦA 5 VIDEO VIRAL NHẤT", min(1.0, t_sec / 0.8), color=(255, 215, 0))

    # Layer 2: Checklist Dossier (at 3.5s)
    if t_sec >= 3.5:
        chk = EvidenceChecklist(
            title="3 YẾU TỐ GIỮ CHÂN KHÁN GIẢ",
            items=[
                ("Hook 3 giây đầu trực diện, gay cấn", True),
                ("Micro-beat 2.5s đổi khung hình liên tục", True),
                ("Thumbnail CTR > 10% gây tò mò cao", True),
            ],
            size=(520, 280),
            angle_deg=-2.5,
        )
        rchk = InvestigationBoardService.render_checklist_dossier(chk)
        frame.paste(rchk, (WIDTH // 2 - rchk.width // 2, 580 - rchk.height // 2), mask=rchk.split()[-1])

    # Layer 3: Stamp DECONSTRUCT (at 11.5s)
    if t_sec >= 11.5:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 11.5) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(frame, (WIDTH // 2, 580), "BÓC TÁCH THÀNH CÔNG", angle_deg=8.0, scale=p * 1.3)

    return frame


def render_scene_07(f: int, n: int) -> Image.Image:
    """Scene 7: Kế Hoạch Bắn Phá 30 Ngày Đầu (15 Videos)."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene7_calendar.png"), f / n, 1.0, 1.07, 30, -20)
    draw_hud(frame, f, "KẾ HOẠCH BẮN PHÁ")

    draw_top_pill_badge(frame, "KẾ HOẠCH BẮN PHÁ 30 NGÀY", "SẢN XUẤT 10 - 15 VIDEO ĐẦU TIÊN ĐỀU ĐẶN", min(1.0, t_sec / 0.8), color=(255, 120, 40))

    # Layer 2: 30-Day Milestone Odometer (at 3.5s)
    if t_sec >= 3.5:
        p = ease_out_cubic(min(1.0, (t_sec - 3.5) / 2.0))
        days = int(30 * p)
        val_str = f"MỤC TIÊU: {days} NGÀY • 15 VIDEOS"

        draw = ImageDraw.Draw(frame)
        draw.rectangle([(WIDTH // 2 - 340, 770), (WIDTH // 2 + 340, 860)], fill=(20, 24, 30, 245), outline=(255, 140, 40, 255), width=3)
        font_d = get_font(38, bold=True)
        draw.text((WIDTH // 2, 815), val_str, font=font_d, fill=(255, 160, 40, 255), anchor="mm")

    # Layer 3: Sticky Note (at 8.5s)
    if t_sec >= 8.5:
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(
                text="KHÔNG BỎ CUỘC Ở VIDEO 03",
                subtext="THUẬT TOÁN CẦN DỮ LIỆU ĐỂ ĐẨY KÊNH",
                size=(360, 190),
                angle_deg=-5.0,
            )
        )
        frame.paste(note, (WIDTH // 2 - note.width // 2, 540 - note.height // 2), mask=note.split()[-1])

    return frame


def render_scene_08(f: int, n: int) -> Image.Image:
    """Scene 8: Đúc Kết & Hành Động Ngay."""
    t_sec = f / float(FPS)
    frame = render_tactile_camera_shot(str(IMAGES_DIR / "scene8_mastery.png"), f / n, 1.06, 1.0, -30, 15)
    draw_hud(frame, f, "HÀNH ĐỘNG NGAY")

    draw_top_pill_badge(frame, "CHỌN ĐÚNG NGÁCH = THẮNG 50%", "BẮT ĐẦU NGAY VỚI ĐÒN BẨY TỰ ĐỘNG VOX STUDIO", min(1.0, t_sec / 0.8), color=(255, 215, 0))

    # Layer 2: Big Golden Quote Lockup (at 4.0s)
    if t_sec >= 4.0:
        draw = ImageDraw.Draw(frame)
        draw.rectangle([(WIDTH // 2 - 440, 750), (WIDTH // 2 + 440, 870)], fill=(16, 20, 26, 245), outline=(255, 215, 0, 255), width=3)
        font_q = get_font(34, bold=True)
        draw.text((WIDTH // 2, 790), "HÃY BẮT ĐẦU NGAY TỪ HÔM NAY!", font=font_q, fill=(255, 230, 20, 255), anchor="mm")
        font_qs = get_font(18, bold=True)
        draw.text((WIDTH // 2, 835), "TỰ ĐỘNG HÓA NỘI DUNG • THỐNG TRỊ THỊ TRƯỜNG", font=font_qs, fill=(255, 255, 255, 230), anchor="mm")

    # Layer 3: Giant Stamp ACTION NOW (at 10.0s)
    if t_sec >= 10.0:
        p = ease_overshoot_bounce(min(1.0, (t_sec - 10.0) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(frame, (WIDTH // 2, 540), "HÀNH ĐỘNG NGAY", angle_deg=-10.0, scale=p * 1.4)

    return frame


SCENES = [
    {
        "id": "scene_01",
        "narration": "Chín mươi phần trăm người mới làm YouTube thất bại ngay từ tuần đầu tiên vì chọn sai ngách: làm vlog đời thường hoặc lao vào những ngách quá bão hòa mà không ai quan tâm.",
        "renderer": render_scene_01,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 4200), ("paper_slide", 8200), ("camera_click", 11800)],
    },
    {
        "id": "scene_02",
        "narration": "Đừng nhìn vào những kênh triệu sub đã làm mười năm. Hãy tìm những kênh nhỏ dưới năm mươi ngàn đăng ký nhưng video đạt lượng xem đột biến gấp ba đến ba mươi lăm lần.",
        "renderer": render_scene_02,
        "sfx_timeline": [("pop", 100), ("typewriter", 3700), ("paper_slide", 8700), ("camera_click", 12200)],
    },
    {
        "id": "scene_03",
        "narration": "Ba ngách kiếm tiền bền vững và CPM cao nhất mọi thời đại: Phóng sự tài chính, Tài liệu lịch sử, và Hồ sơ bí ẩn chưa có lời giải.",
        "renderer": render_scene_03,
        "sfx_timeline": [("pop", 100), ("pushpin_hit", 3200), ("pushpin_hit", 6200), ("pushpin_hit", 9200), ("whoosh", 11200)],
    },
    {
        "id": "scene_04",
        "narration": "Một ngách chiến thắng nằm ở giao điểm của ba yếu tố: Nhu cầu khán giả cao, Nguồn tư liệu dồi dào, và Khả năng sản xuất tự động bằng công cụ trí tuệ nhân tạo.",
        "renderer": render_scene_04,
        "sfx_timeline": [("pop", 100), ("marker_sweep", 4700), ("paper_slide", 9200)],
    },
    {
        "id": "scene_05",
        "narration": "Cùng một công sức làm video, nhưng một ngàn lượt xem từ Mỹ hay Châu Âu mang lại mười lăm đến ba mươi đô la, trong khi làm view nội địa chỉ đủ mua một bát phở.",
        "renderer": render_scene_05,
        "sfx_timeline": [("pop", 100), ("typewriter", 3700), ("paper_slide", 8700), ("camera_click", 12200)],
    },
    {
        "id": "scene_06",
        "narration": "Bóc tách cấu trúc ba mươi giây đầu của năm video viral nhất trong ngách: Học cách họ đặt câu hỏi mở đầu, nhịp dựng micro-beat dồn dập và cách thiết kế ảnh bìa thumbnail.",
        "renderer": render_scene_06,
        "sfx_timeline": [("pop", 100), ("paper_slide", 3700), ("camera_click", 11700)],
    },
    {
        "id": "scene_07",
        "narration": "Đừng tốn cả tháng trau chuốt một video duy nhất. Hãy lên kế hoạch sản xuất mười đến mười lăm video đầu tiên theo nhịp độ đều đặn để thuật toán YouTube hiểu và phân phối kênh.",
        "renderer": render_scene_07,
        "sfx_timeline": [("pop", 100), ("typewriter", 3700), ("paper_slide", 8700)],
    },
    {
        "id": "scene_08",
        "narration": "Chọn đúng ngách là bạn đã thắng một nửa cuộc chơi. Hãy bắt đầu ngay hôm nay từ một ngách nhỏ, làm sâu và dùng đòn bẩy tự động hóa để thống trị thị trường!",
        "renderer": render_scene_08,
        "sfx_timeline": [("pop", 100), ("paper_slide", 4200), ("camera_click", 10200)],
    },
]


def main() -> None:
    logger.info("=== Starting 2-Minute YouTube Niche Strategy Vox Video Generation ===")
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
        logger.info(f"--- Rendering 2-Minute Scene: {scene_id} [{idx + 1}/8] ---")

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

        if scene_mp4.is_file() and scene_mp4.stat().st_size > 500000:
            logger.info(f"Reusing existing rendered scene: {scene_mp4}")
            scene_mp4s.append(scene_mp4)
            continue

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

    # Tension Strategic BGM
    total_dur_ms = sum(durations_ms)
    logger.info(f"Total video duration: {total_dur_ms / 1000.0:.2f}s")
    bgm_wav = audio_dir / "strategy_bgm.wav"
    dur_s = total_dur_ms / 1000.0 + 2.0
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

    final_mp4 = final_dir / "cach_chon_ngach_youtube_2min_vox.mp4"
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
    print(f"\n[DONE] Video 2 Phút Chọn Ngách YouTube Hoàn Tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
