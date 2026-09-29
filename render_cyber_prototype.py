#!/usr/bin/env python3
"""
Full 3D Icon Integration Prototype:
- Uses authentic 3D Microsoft Fluent Emoji icons (PNG) with alpha transparency
- Zero font glyph errors or tofu boxes
- High-vibrancy Cyber Arcade aesthetic with 3D icons
"""

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REGULAR = "C:/Windows/Fonts/arial.ttf"
ICONS_DIR = Path("assets/icons_3d")

def get_font(size: int, bold: bool = True):
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def get_3d_icon(name: str, size: int = 48) -> Image.Image | None:
    p = ICONS_DIR / f"{name}.png"
    if p.exists():
        try:
            im = Image.open(p).convert("RGBA")
            scale = size / max(im.width, im.height)
            return im.resize((int(im.width * scale), int(im.height * scale)), Image.Resampling.LANCZOS)
        except Exception:
            return None
    return None

def paste_icon_with_text(canvas, draw, center_xy, text, font, icon_name, icon_size=36, icon_side="left", fill=(255, 255, 255), gap=12, stroke_color=None, stroke_width=0):
    cx, cy = center_xy
    icon = get_3d_icon(icon_name, size=icon_size)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    
    if icon is not None:
        iw = icon.width
        if icon_side == "left":
            total_w = iw + gap + tw
            start_x = cx - total_w // 2
            canvas.paste(icon, (start_x, cy - icon.height // 2), icon)
            text_x = start_x + iw + gap
            draw.text((text_x, cy), text, font=font, fill=fill, stroke_fill=stroke_color, stroke_width=stroke_width, anchor="lm")
        elif icon_side == "right":
            total_w = tw + gap + iw
            start_x = cx - total_w // 2
            draw.text((start_x, cy), text, font=font, fill=fill, stroke_fill=stroke_color, stroke_width=stroke_width, anchor="lm")
            canvas.paste(icon, (start_x + tw + gap, cy - icon.height // 2), icon)
        elif icon_side == "both":
            total_w = iw + gap + tw + gap + iw
            start_x = cx - total_w // 2
            canvas.paste(icon, (start_x, cy - icon.height // 2), icon)
            draw.text((start_x + iw + gap, cy), text, font=font, fill=fill, stroke_fill=stroke_color, stroke_width=stroke_width, anchor="lm")
            canvas.paste(icon, (start_x + iw + gap + tw + gap, cy - icon.height // 2), icon)
    else:
        draw.text((cx, cy), text, font=font, fill=fill, stroke_fill=stroke_color, stroke_width=stroke_width, anchor="mm")

def draw_comic_text(draw, xy, text, font, fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=4, shadow_offset=(3, 4), shadow_color=(0, 0, 0), anchor="mm"):
    x, y = xy
    if shadow_offset and shadow_offset != (0, 0):
        sx, sy = shadow_offset
        draw.text((x + sx, y + sy), text, font=font, fill=shadow_color, stroke_width=stroke_width, stroke_fill=shadow_color, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_color, anchor=anchor)

def render_cyber_16_9_with_3d_icons(out_path: Path):
    w, h = 1920, 1080
    im = Image.new("RGBA", (w, h), (14, 18, 36, 255))
    draw = ImageDraw.Draw(im)

    # 1. Background
    for y in range(h):
        ratio = y / h
        r = int(14 * (1 - ratio) + 24 * ratio)
        g = int(18 * (1 - ratio) + 20 * ratio)
        b = int(38 * (1 - ratio) + 52 * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    # 2. Electric Cyan Speed Rays
    cx, cy = w // 2, h // 2
    for i in range(0, 24, 2):
        a1 = i * (math.pi / 12) + 0.15
        a2 = (i + 1) * (math.pi / 12) + 0.15
        p1 = (cx, cy)
        p2 = (cx + 2200 * math.cos(a1), cy + 2200 * math.sin(a1))
        p3 = (cx + 2200 * math.cos(a2), cy + 2200 * math.sin(a2))
        draw.polygon([p1, p2, p3], fill=(0, 220, 255, 14))

    # 3. Glowing Bokeh
    random.seed(42)
    for _ in range(28):
        px, py = random.randint(40, w - 40), random.randint(40, h - 40)
        pr = random.randint(6, 18)
        col = (0, 230, 255, random.randint(25, 75)) if random.random() > 0.4 else (255, 215, 0, random.randint(25, 70))
        draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=col)

    # 4. Question Banner
    q_text = "Thủ đô của Việt Nam là thành phố nào?"
    draw.rounded_rectangle([175 + 4, 38 + 6, 1535 + 4, 158 + 6], radius=28, fill=(0, 0, 0, 95))
    draw.rounded_rectangle([175, 38, 1535, 158], radius=28, fill=(24, 32, 54), outline=(255, 215, 0), width=4)
    font_q = get_font(42, bold=True)
    draw_comic_text(draw, (855, 98), q_text, font=font_q, fill=(255, 255, 255), stroke_color=(10, 12, 20), stroke_width=3, shadow_offset=(2, 3), shadow_color=(0, 0, 0, 180))

    # 5. Top-Right Difficulty Badge with 3D Fire Icon!
    draw.rounded_rectangle([1565 + 4, 38 + 6, 1865 + 4, 158 + 6], radius=24, fill=(0, 0, 0, 95))
    draw.rounded_rectangle([1565, 38, 1865, 158], radius=24, fill=(46, 204, 113), outline=(255, 255, 255), width=3)
    paste_icon_with_text(im, draw, (1715, 76), "CÂU 1", get_font(30, bold=True), "fire", icon_size=38, icon_side="left", fill=(255, 255, 255), stroke_color=(15, 20, 25), stroke_width=2)
    draw.text((1715, 120), "DỄ (EASY)", font=get_font(20, bold=True), fill=(255, 255, 255), anchor="mm")

    # 6. Left Hero / Clue Glass Card
    draw.rounded_rectangle([175 + 5, 205 + 7, 875 + 5, 835 + 7], radius=32, fill=(0, 0, 0, 95))
    draw.rounded_rectangle([175, 205, 875, 835], radius=32, fill=(22, 29, 48), outline=(0, 220, 255), width=4)

    draw.rounded_rectangle([215, 235, 465, 290], radius=16, fill=(231, 76, 60), outline=(255, 255, 255), width=2)
    draw.text((340, 262), "ĐỐ VUI KIẾN THỨC", font=get_font(22, bold=True), fill=(255, 255, 255), anchor="mm")

    # Center Glowing Orb
    orb_cx, orb_cy = 525, 430
    for gr in range(110, 50, -10):
        draw.ellipse([orb_cx - gr, orb_cy - gr, orb_cx + gr, orb_cy + gr], fill=(0, 220, 255, 6))
    draw.ellipse([orb_cx - 70, orb_cy - 70, orb_cx + 70, orb_cy + 70], fill=(30, 42, 70), outline=(255, 215, 0), width=4)
    draw_comic_text(draw, (orb_cx, orb_cy), "?", font=get_font(80, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=4)

    # Clue Banner
    draw.rounded_rectangle([215, 560, 835, 670], radius=22, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
    draw_comic_text(draw, (525, 615), "GỢI Ý: THỦ ĐÔ", font=get_font(42, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=3)

    # Bottom Guide Bar with 3D Pointing Right Finger!
    draw.rounded_rectangle([215, 710, 835, 785], radius=18, fill=(18, 24, 40), outline=(0, 220, 255), width=2)
    paste_icon_with_text(im, draw, (525, 747), "CHỌN ĐÁP ÁN BÊN PHẢI", get_font(24, bold=True), "point_right", icon_size=36, icon_side="right", fill=(0, 230, 255))

    # 7. Right Options Panel (eSports Cyber Capsules)
    choices = [("A", "Hà Nội"), ("B", "Huế"), ("C", "Đà Nẵng"), ("D", "TP Hồ Chí Minh")]
    py_start = 205
    gap_y = 158
    pill_h = 122
    for i, (cid, ctext) in enumerate(choices):
        cy = py_start + i * gap_y
        draw.rounded_rectangle([925 + 5, cy + 6, 1865 + 5, cy + pill_h + 6], radius=26, fill=(0, 0, 0, 95))
        draw.rounded_rectangle([925, cy, 1865, cy + pill_h], radius=26, fill=(26, 34, 56), outline=(255, 215, 0), width=3)

        badge_cx = 995
        badge_cy = cy + pill_h // 2
        draw.ellipse([badge_cx - 40, badge_cy - 40, badge_cx + 40, badge_cy + 40], fill=(231, 76, 60), outline=(255, 255, 255), width=3)
        draw.text((badge_cx, badge_cy), cid, font=get_font(40, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((1075, badge_cy), ctext, font=get_font(44, bold=True), fill=(255, 255, 255), anchor="lm")

    # 8. Mascot in Bottom-Left
    mascot_p = Path("assets/mascots_hoat_hinh/loc_host_raw_cutout.png")
    if mascot_p.exists():
        raw_m = Image.open(mascot_p).convert("RGBA")
        target_m_h = 330
        sc = target_m_h / raw_m.height
        m_scaled = raw_m.resize((int(raw_m.width * sc), target_m_h), Image.Resampling.LANCZOS)
        from app.services.quiz_engine_v2 import apply_diecut_outline
        m_diecut = apply_diecut_outline(m_scaled, outline_px=6)
        im.paste(m_diecut, (40, h - m_diecut.height - 15), m_diecut)

    # 9. Energy Laser Timer Bar
    tx0, ty0, tx1, ty1 = 280, 905, 1865, 985
    draw.rounded_rectangle([tx0 + 4, ty0 + 5, tx1 + 4, ty1 + 5], radius=32, fill=(0, 0, 0, 95))
    draw.rounded_rectangle([tx0, ty0, tx1, ty1], radius=32, fill=(18, 24, 38), outline=(0, 220, 255), width=3)
    fill_w = int((tx1 - tx0) * 0.7)
    draw.rounded_rectangle([tx0, ty0, tx0 + fill_w, ty1], radius=32, fill=(0, 230, 118))
    from app.services.quiz_engine_v2 import create_alarm_clock_icon
    clock = create_alarm_clock_icon(78)
    im.paste(clock, (tx0 + fill_w - clock.width // 2, ty0 + (ty1 - ty0 - clock.height) // 2), clock)

    im.convert("RGB").save(out_path, quality=95)
    print(f"Rendered Cyber 16:9 with 3D Icons to: {out_path}")

def render_outro_with_3d_icons(out_path: Path):
    w, h = 1920, 1080
    im = Image.new("RGBA", (w, h), (14, 18, 36, 255))
    draw = ImageDraw.Draw(im)

    # Background
    for y in range(h):
        ratio = y / h
        r = int(14 * (1 - ratio) + 24 * ratio)
        g = int(18 * (1 - ratio) + 20 * ratio)
        b = int(38 * (1 - ratio) + 52 * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    # Mascot on left
    mascot_p = Path("assets/mascots_hoat_hinh/loc_host_raw_cutout.png")
    if mascot_p.exists():
        raw_m = Image.open(mascot_p).convert("RGBA")
        target_m_h = 360
        sc = target_m_h / raw_m.height
        m_scaled = raw_m.resize((int(raw_m.width * sc), target_m_h), Image.Resampling.LANCZOS)
        from app.services.quiz_engine_v2 import apply_diecut_outline
        m_diecut = apply_diecut_outline(m_scaled, outline_px=6)
        im.paste(m_diecut, (220, h // 2 - m_diecut.height // 2), m_diecut)

    # Scoreboard card
    draw.rounded_rectangle([680 + 6, 170 + 8, 1800 + 6, 930 + 8], radius=36, fill=(0, 0, 0, 95))
    draw.rounded_rectangle([680, 170, 1800, 930], radius=36, fill=(25, 30, 45), outline=(255, 215, 0), width=6)

    # Header with 3D Trophy Icons on both sides!
    paste_icon_with_text(im, draw, (1240, 250), "BẢNG TỔNG KẾT ĐIỂM SỐ", get_font(48, bold=True), "trophy", icon_size=58, icon_side="both", fill=(255, 215, 0), stroke_color=(0, 0, 0), stroke_width=3)

    # Tier 1 with 3D Crown
    draw.rounded_rectangle([740, 360, 1740, 440], radius=20, fill=(35, 42, 60), outline=(46, 204, 113), width=3)
    paste_icon_with_text(im, draw, (800, 400), "", get_font(34, bold=True), "crown", icon_size=46, icon_side="left")
    draw.text((850, 400), "TOP 1: ĐÚNG 100% — THIÊN TÀI TRÍ TUỆ", font=get_font(32, bold=True), fill=(255, 255, 255), anchor="lm")

    # Tier 2 with 3D Star
    draw.rounded_rectangle([740, 470, 1740, 550], radius=20, fill=(35, 42, 60), outline=(52, 152, 219), width=3)
    paste_icon_with_text(im, draw, (800, 510), "", get_font(34, bold=True), "star", icon_size=46, icon_side="left")
    draw.text((850, 510), "TOP 2: ĐÚNG 70%+ — CAO THỦ XUẤT SẮC", font=get_font(32, bold=True), fill=(255, 255, 255), anchor="lm")

    # Tier 3 with 3D Flame
    draw.rounded_rectangle([740, 580, 1740, 660], radius=20, fill=(35, 42, 60), outline=(231, 76, 60), width=3)
    paste_icon_with_text(im, draw, (800, 620), "", get_font(34, bold=True), "fire", icon_size=44, icon_side="left")
    draw.text((850, 620), "TOP 3: DƯỚI 50% — CẦN CỐ GẮNG THÊM", font=get_font(32, bold=True), fill=(255, 255, 255), anchor="lm")

    # Strong CTA Button with 3D Speech Balloon & Thumbs Up!
    draw.rounded_rectangle([740, 715, 1740, 845], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
    paste_icon_with_text(im, draw, (1240, 755), "BẠN ĐẠT MẤY ĐIỂM? BÌNH LUẬN NGAY!", get_font(36, bold=True), "speech_balloon", icon_size=42, icon_side="left", fill=(255, 255, 255), stroke_color=(0, 0, 0), stroke_width=2)
    paste_icon_with_text(im, draw, (1240, 805), "LIKE & ĐĂNG KÝ KÊNH ĐỂ ĐẤU TIẾP VÒNG SAU!", get_font(24, bold=True), "thumbs_up", icon_size=32, icon_side="left", fill=(255, 215, 0))

    im.convert("RGB").save(out_path, quality=95)
    print(f"Rendered Outro with 3D Icons to: {out_path}")

if __name__ == "__main__":
    out_dir = Path("output/test_optimized_comparison/previews")
    render_cyber_16_9_with_3d_icons(out_dir / "cyber_with_3d_icons_169.jpg")
    render_outro_with_3d_icons(out_dir / "outro_with_3d_icons_169.jpg")
