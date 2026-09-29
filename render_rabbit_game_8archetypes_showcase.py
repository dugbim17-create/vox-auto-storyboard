#!/usr/bin/env python3
"""
Master Video Generator for Rabbit Game 8 Archetypes Showcase (1080p 30fps)
Renders a complete, broadcast-ready quiz video covering all 8 question formats:
1. emoji_rebus (Đuổi hình bắt chữ Emoji)
2. concept_rebus (Ghép tranh Dân Gian)
3. open_visual (Nhận diện mở Logo)
4. dont_say_same (Đừng nói giống tôi)
5. multiple_choice (Trắc nghiệm Fan Cứng)
6. eat_or_pass (Ăn hay Bỏ qua)
7. fast_math (Thử thách tính nhẩm 5s)
8. vocab_flashcard (Flashcard Song Ngữ)
"""

import os
import sys
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

OUTPUT_DIR = Path("output/rabbit_game_8archetypes_showcase")
ASSETS_DIR = OUTPUT_DIR / "assets"
AUDIO_DIR = OUTPUT_DIR / "audio"
FRAMES_DIR = OUTPUT_DIR / "frames"
FINAL_DIR = OUTPUT_DIR / "final"

for d in [OUTPUT_DIR, ASSETS_DIR, AUDIO_DIR, FRAMES_DIR, FINAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

WIDTH = 1920
HEIGHT = 1080
FPS = 30

FONT_PATH_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_PATH_REGULAR = "C:/Windows/Fonts/arial.ttf"

def get_font(size: int, bold: bool = True):
    try:
        path = FONT_PATH_BOLD if bold else FONT_PATH_REGULAR
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

# -------------------------------------------------------------
# GRAPHIC PRIMITIVES & PROCEDURAL ASSET GENERATORS
# -------------------------------------------------------------

def apply_diecut_outline(img: Image.Image, outline_px: int = 8, outline_color=(255, 255, 255, 255)) -> Image.Image:
    """Expands alpha mask to create a crisp white die-cut sticker border with subtle shadow."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    alpha = img.split()[-1]
    expanded_mask = alpha.filter(ImageFilter.MaxFilter(outline_px * 2 + 1))
    
    # Border layer
    border_layer = Image.new('RGBA', img.size, outline_color)
    border_layer.putalpha(expanded_mask)
    
    # Soft drop shadow
    shadow_layer = Image.new('RGBA', img.size, (0, 0, 0, 75))
    shadow_mask = expanded_mask.filter(ImageFilter.GaussianBlur(outline_px // 2 + 1))
    shadow_layer.putalpha(shadow_mask)
    
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.paste(shadow_layer, (4, 6), shadow_layer)
    out.paste(border_layer, (0, 0), border_layer)
    out.paste(img, (0, 0), img)
    return out

def create_alarm_clock_icon(size: int = 72) -> Image.Image:
    """Draws a cute cartoon red alarm clock with bells and hands."""
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    
    # Bell bells on top
    r_bell = size * 0.18
    draw.ellipse((size * 0.12, size * 0.08, size * 0.12 + r_bell * 2, size * 0.08 + r_bell * 2), fill=(230, 230, 230), outline=(50, 50, 50), width=2)
    draw.ellipse((size * 0.52, size * 0.08, size * 0.52 + r_bell * 2, size * 0.08 + r_bell * 2), fill=(230, 230, 230), outline=(50, 50, 50), width=2)
    
    # Feet
    draw.polygon([(size * 0.22, size * 0.82), (size * 0.12, size * 0.96), (size * 0.28, size * 0.96)], fill=(200, 200, 200), outline=(50, 50, 50))
    draw.polygon([(size * 0.78, size * 0.82), (size * 0.88, size * 0.96), (size * 0.72, size * 0.96)], fill=(200, 200, 200), outline=(50, 50, 50))
    
    # Main red clock body
    margin = size * 0.12
    draw.ellipse((margin, margin + 4, size - margin, size - margin + 4), fill=(235, 50, 50), outline=(40, 40, 40), width=3)
    
    # White face
    face_margin = size * 0.22
    draw.ellipse((face_margin, face_margin + 4, size - face_margin, size - face_margin + 4), fill=(255, 255, 255), outline=(40, 40, 40), width=2)
    
    # Clock center and hands
    cx, cy = size / 2, size / 2 + 2
    draw.line((cx, cy, cx, cy - size * 0.18), fill=(30, 30, 30), width=3)
    draw.line((cx, cy, cx + size * 0.14, cy), fill=(30, 30, 30), width=3)
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(235, 50, 50))
    
    return apply_diecut_outline(im, outline_px=3)

def create_apple_badge(order_text: str = "?", size: int = 120) -> Image.Image:
    """Draws the signature Rabbit Game Red Apple Badge with leaf and center text."""
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    
    # Leaf
    draw.ellipse((size * 0.48, size * 0.05, size * 0.75, size * 0.28), fill=(46, 204, 113), outline=(30, 30, 30), width=2)
    # Stem
    draw.arc((size * 0.38, size * 0.10, size * 0.55, size * 0.35), start=180, end=300, fill=(120, 60, 20), width=4)
    
    # Apple Body (double rounded lobes)
    draw.ellipse((size * 0.10, size * 0.22, size * 0.62, size * 0.88), fill=(235, 45, 45))
    draw.ellipse((size * 0.38, size * 0.22, size * 0.90, size * 0.88), fill=(235, 45, 45))
    draw.ellipse((size * 0.15, size * 0.28, size * 0.85, size * 0.92), fill=(235, 45, 45), outline=(40, 40, 40), width=3)
    
    # Center text / number
    f_size = int(size * 0.42)
    font = get_font(f_size, bold=True)
    draw.text((size / 2, size * 0.58), order_text, font=font, fill=(255, 255, 255), anchor="mm")
    
    return apply_diecut_outline(im, outline_px=4)

def draw_watermark_pattern(canvas: Image.Image, pattern_type: str = "trophy", color=(255, 255, 255, 18)):
    """Renders repeating subtle watermark icons across the canvas."""
    overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    step_x = 180
    step_y = 160
    for y in range(60, canvas.height, step_y):
        offset = (step_x // 2) if (y // step_y) % 2 == 1 else 0
        for x in range(60 + offset, canvas.width, step_x):
            if pattern_type == "trophy":
                # Cup polygon
                draw.polygon([(x - 18, y - 15), (x + 18, y - 15), (x + 12, y + 6), (x - 12, y + 6)], fill=color)
                draw.rectangle((x - 4, y + 6, x + 4, y + 16), fill=color)
                draw.rectangle((x - 14, y + 16, x + 14, y + 20), fill=color)
                # Handles
                draw.arc((x - 26, y - 12, x - 12, y + 4), 90, 270, fill=color, width=3)
                draw.arc((x + 12, y - 12, x + 26, y + 4), 270, 90, fill=color, width=3)
            elif pattern_type == "star":
                r_out, r_in = 16, 7
                points = []
                for i in range(10):
                    ang = -math.pi / 2 + i * (math.pi / 5)
                    r = r_out if i % 2 == 0 else r_in
                    points.append((x + r * math.cos(ang), y + r * math.sin(ang)))
                draw.polygon(points, fill=color)
            elif pattern_type == "doodle":
                draw.rectangle((x - 14, y - 14, x + 14, y + 14), outline=color, width=2)
                draw.ellipse((x - 8, y - 8, x + 8, y + 8), outline=color, width=2)
                
    canvas.paste(Image.alpha_composite(canvas.convert('RGBA'), overlay), (0, 0))

def create_background_gradient(top_color: tuple, bottom_color: tuple, pattern: str = "trophy") -> Image.Image:
    """Generates a high-quality vertical gradient with subtle watermark pattern."""
    img = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))
    draw_watermark_pattern(img, pattern_type=pattern)
    return img

def draw_header_banner(draw, canvas, title_text: str, badge_text: str, badge_num: int):
    """Draws the standard top header banner with Apple Logo & Question title."""
    # Top-Left Apple Logo Badge
    apple_img = create_apple_badge(str(badge_num), size=140)
    canvas.paste(apple_img, (75, 25), apple_img)
    
    # Title Banner Box
    bx, by, bw, bh = 240, 38, 1600, 115
    draw.rounded_rectangle([bx + 4, by + 6, bx + bw + 4, by + bh + 6], radius=28, fill=(0, 0, 0, 50))
    # Gradient Banner Fill (Gold to Orange)
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=28, fill=(255, 202, 40), outline=(255, 255, 255), width=4)
    
    font_title = get_font(52, bold=True)
    draw.text((bx + bw / 2, by + bh / 2), title_text, font=font_title, fill=(25, 25, 30), anchor="mm")

def draw_sliding_timer_bar(draw, canvas, clock_icon: Image.Image, x: int, y: int, w: int, h: int, progress: float):
    """
    Renders dynamic sliding timer progress bar:
    progress goes from 1.0 (start) down to 0.0 (time up).
    Green-to-Cyan elapsed track fills from left to right as time passes (or vice versa).
    """
    # Track Shadow
    draw.rounded_rectangle([x + 3, y + 4, x + w + 3, y + h + 4], radius=h//2, fill=(0, 0, 0, 60))
    # Background Track
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h//2, fill=(245, 248, 250), outline=(210, 215, 220), width=3)
    
    # Filled Portion (1.0 - progress represents elapsed time)
    elapsed = max(0.02, min(1.0, 1.0 - progress))
    fill_w = int(w * elapsed)
    if fill_w > h:
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=h//2, fill=(0, 230, 118))
    
    # Sliding Alarm Clock Icon at the leading edge
    clock_cx = x + fill_w
    clock_x = int(clock_cx - clock_icon.width / 2)
    clock_y = int(y + (h - clock_icon.height) / 2)
    canvas.paste(clock_icon, (clock_x, clock_y), clock_icon)

def draw_reveal_bar(draw, x: int, y: int, w: int, h: int, reveal_text: str):
    """Draws full glowing emerald green reveal banner with clean vector checkmark."""
    draw.rounded_rectangle([x + 3, y + 4, x + w + 3, y + h + 4], radius=24, fill=(0, 0, 0, 70))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=24, fill=(46, 204, 113), outline=(255, 255, 255), width=4)
    
    # Draw pure vector checkmark instead of font glyph
    cx, cy = x + 60, y + h // 2
    draw.line([(cx - 16, cy + 2), (cx - 4, cy + 14), (cx + 18, cy - 12)], fill=(255, 255, 255), width=6)
    
    font_rev = get_font(46, bold=True)
    draw.text((x + 100, y + h // 2), f"ĐÁP ÁN: {reveal_text}", font=font_rev, fill=(255, 255, 255), anchor="lm")

# -------------------------------------------------------------
# STICKER VECTOR ASSETS DRAWING
# -------------------------------------------------------------

def create_shirt_sticker(size: int = 340) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Blue T-Shirt
    pts = [
        (size*0.32, size*0.18), (size*0.68, size*0.18),
        (size*0.88, size*0.35), (size*0.75, size*0.48),
        (size*0.68, size*0.42), (size*0.68, size*0.85),
        (size*0.32, size*0.85), (size*0.32, size*0.42),
        (size*0.25, size*0.48), (size*0.12, size*0.35)
    ]
    draw.polygon(pts, fill=(41, 128, 185), outline=(20, 40, 60), width=6)
    # Collar
    draw.arc((size*0.40, size*0.14, size*0.60, size*0.28), 0, 180, fill=(240, 240, 240), width=8)
    return apply_diecut_outline(im, outline_px=10)

def create_rain_sticker(size: int = 340) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Cloud
    draw.ellipse((size*0.18, size*0.25, size*0.52, size*0.60), fill=(220, 240, 255))
    draw.ellipse((size*0.42, size*0.20, size*0.82, size*0.60), fill=(220, 240, 255))
    draw.ellipse((size*0.28, size*0.12, size*0.68, size*0.55), fill=(220, 240, 255), outline=(100, 150, 190), width=6)
    # Raindrops
    for rx, ry in [(0.25, 0.70), (0.45, 0.72), (0.65, 0.68), (0.35, 0.85), (0.55, 0.86)]:
        draw.ellipse((size*rx, size*ry, size*(rx+0.08), size*(ry+0.12)), fill=(52, 152, 219))
    return apply_diecut_outline(im, outline_px=10)

def create_umbrella_sticker(size: int = 300) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Umbrella dome
    draw.pieslice((size*0.10, size*0.15, size*0.90, size*0.75), 180, 360, fill=(231, 76, 60), outline=(40, 40, 40), width=6)
    # Stem and Hook handle
    draw.line((size*0.50, size*0.45, size*0.50, size*0.82), fill=(50, 50, 50), width=8)
    draw.arc((size*0.42, size*0.76, size*0.58, size*0.92), 0, 180, fill=(50, 50, 50), width=8)
    return apply_diecut_outline(im, outline_px=10)

def create_eating_sticker(size: int = 300) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Cute kid eating apple
    draw.ellipse((size*0.25, size*0.20, size*0.75, size*0.70), fill=(255, 224, 189), outline=(40, 40, 40), width=6)
    # Hair
    draw.pieslice((size*0.20, size*0.10, size*0.80, size*0.50), 180, 360, fill=(60, 40, 20))
    # Apple being eaten
    draw.ellipse((size*0.55, size*0.45, size*0.85, size*0.75), fill=(235, 40, 40), outline=(40, 40, 40), width=4)
    return apply_diecut_outline(im, outline_px=10)

def create_mandarin_sticker(size: int = 300) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Mandarin hat & robe
    draw.polygon([(size*0.25, size*0.25), (size*0.75, size*0.25), (size*0.65, size*0.10), (size*0.35, size*0.10)], fill=(30, 30, 80), outline=(240, 200, 50), width=5)
    draw.ellipse((size*0.30, size*0.22, size*0.70, size*0.62), fill=(255, 224, 189), outline=(40, 40, 40), width=5)
    # Feather fan
    draw.pieslice((size*0.55, size*0.50, size*0.92, size*0.88), 120, 240, fill=(240, 240, 240), outline=(40, 40, 40), width=4)
    return apply_diecut_outline(im, outline_px=10)

def create_barcelona_crest(size: int = 420) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Shield Outer Gold Border
    draw.rounded_rectangle([size*0.10, size*0.10, size*0.90, size*0.85], radius=50, fill=(245, 190, 20), outline=(20, 20, 20), width=8)
    # Inner Background
    draw.rounded_rectangle([size*0.15, size*0.15, size*0.85, size*0.80], radius=40, fill=(255, 255, 255))
    # Cross & Stripes top
    draw.rectangle([size*0.15, size*0.15, size*0.48, size*0.45], fill=(255, 255, 255))
    draw.line([(size*0.315, size*0.15), (size*0.315, size*0.45)], fill=(220, 30, 30), width=18)
    draw.line([(size*0.15, size*0.30), (size*0.48, size*0.30)], fill=(220, 30, 30), width=18)
    # Yellow/Red Stripes top right
    for i in range(4):
        draw.rectangle([size*0.52 + i*size*0.08, size*0.15, size*0.56 + i*size*0.08, size*0.45], fill=(220, 30, 30))
    # Mid banner with FCB
    draw.rectangle([size*0.12, size*0.45, size*0.88, size*0.58], fill=(245, 190, 20), outline=(20, 20, 20), width=4)
    font_fcb = get_font(int(size*0.09), bold=True)
    draw.text((size*0.50, size*0.515), "FCB", font=font_fcb, fill=(20, 20, 20), anchor="mm")
    # Blaugrana Stripes bottom
    for i in range(3):
        draw.rectangle([size*0.22 + i*size*0.18, size*0.58, size*0.31 + i*size*0.18, size*0.78], fill=(165, 0, 40))
        draw.rectangle([size*0.31 + i*size*0.18, size*0.58, size*0.40 + i*size*0.18, size*0.78], fill=(0, 77, 152))
    # Football center
    draw.ellipse((size*0.40, size*0.62, size*0.60, size*0.82), fill=(240, 200, 40), outline=(20, 20, 20), width=4)
    return apply_diecut_outline(im, outline_px=12)

def create_trophy_sticker(size: int = 380) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Golden Trophy Cup
    draw.polygon([(size*0.25, size*0.20), (size*0.75, size*0.20), (size*0.65, size*0.55), (size*0.35, size*0.55)], fill=(255, 215, 0), outline=(180, 140, 0), width=8)
    draw.rectangle([size*0.44, size*0.55, size*0.56, size*0.75], fill=(240, 195, 0), outline=(180, 140, 0), width=6)
    draw.polygon([(size*0.28, size*0.75), (size*0.72, size*0.75), (size*0.78, size*0.88), (size*0.22, size*0.88)], fill=(120, 80, 30), outline=(40, 30, 10), width=6)
    # Handles
    draw.arc((size*0.12, size*0.22, size*0.30, size*0.48), 90, 270, fill=(255, 215, 0), width=12)
    draw.arc((size*0.70, size*0.22, size*0.88, size*0.48), 270, 90, fill=(255, 215, 0), width=12)
    return apply_diecut_outline(im, outline_px=10)

def create_durian_cheese_sticker(size: int = 420) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Golden toasted food bowl / toast
    draw.rounded_rectangle([size*0.15, size*0.35, size*0.85, size*0.85], radius=35, fill=(245, 175, 40), outline=(160, 90, 20), width=8)
    # Melted Cheese Layer
    draw.ellipse((size*0.22, size*0.28, size*0.78, size*0.55), fill=(255, 240, 100), outline=(220, 160, 20), width=6)
    # Durian Segments (Creamy yellow)
    draw.ellipse((size*0.28, size*0.38, size*0.52, size*0.62), fill=(255, 220, 50))
    draw.ellipse((size*0.48, size*0.36, size*0.72, size*0.60), fill=(255, 220, 50))
    return apply_diecut_outline(im, outline_px=12)

def create_owl_professor(size: int = 340) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Owl body
    draw.ellipse((size*0.20, size*0.25, size*0.80, size*0.85), fill=(160, 110, 60), outline=(50, 30, 10), width=6)
    draw.ellipse((size*0.30, size*0.42, size*0.70, size*0.80), fill=(240, 220, 180))
    # Glasses & Eyes
    draw.ellipse((size*0.28, size*0.32, size*0.48, size*0.52), fill=(255, 255, 255), outline=(20, 20, 20), width=5)
    draw.ellipse((size*0.52, size*0.32, size*0.72, size*0.52), fill=(255, 255, 255), outline=(20, 20, 20), width=5)
    draw.ellipse((size*0.36, size*0.38, size*0.44, size*0.46), fill=(20, 20, 20))
    draw.ellipse((size*0.60, size*0.38, size*0.68, size*0.46), fill=(20, 20, 20))
    # Graduation Cap
    draw.polygon([(size*0.15, size*0.20), (size*0.85, size*0.20), (size*0.50, size*0.06)], fill=(20, 20, 20), outline=(255, 215, 0), width=4)
    return apply_diecut_outline(im, outline_px=10)

def create_fox_sticker(size: int = 380) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Orange Fox Face
    pts_face = [(size*0.50, size*0.85), (size*0.12, size*0.35), (size*0.28, size*0.15), (size*0.50, size*0.35), (size*0.72, size*0.15), (size*0.88, size*0.35)]
    draw.polygon(pts_face, fill=(235, 100, 30), outline=(40, 20, 10), width=6)
    # White Cheeks
    draw.polygon([(size*0.50, size*0.85), (size*0.18, size*0.48), (size*0.40, size*0.48)], fill=(255, 255, 255))
    draw.polygon([(size*0.50, size*0.85), (size*0.82, size*0.48), (size*0.60, size*0.48)], fill=(255, 255, 255))
    # Nose & Eyes
    draw.ellipse((size*0.46, size*0.78, size*0.54, size*0.86), fill=(20, 20, 20))
    draw.ellipse((size*0.32, size*0.42, size*0.40, size*0.50), fill=(20, 20, 20))
    draw.ellipse((size*0.60, size*0.42, size*0.68, size*0.50), fill=(20, 20, 20))
    return apply_diecut_outline(im, outline_px=10)

clock_icon = create_alarm_clock_icon(84)

# -------------------------------------------------------------
# 8 ARCHETYPE FRAME RENDERERS
# -------------------------------------------------------------

def render_q1_emoji_rebus(progress: float, is_reveal: bool) -> Image.Image:
    """1. Emoji Rebus: 👕 + 🌧️ = Áo mưa"""
    canvas = create_background_gradient((235, 120, 40), (200, 80, 20), pattern="trophy")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐOÁN TỪ GHÉP BẰNG EMOJI", "CÂU 1/8", 1)
    
    # Center Stage: 2 Stickers side by side
    shirt = create_shirt_sticker(320)
    rain = create_rain_sticker(320)
    canvas.paste(shirt, (WIDTH//2 - 380, 290), shirt)
    canvas.paste(rain, (WIDTH//2 + 60, 290), rain)
    
    # Plus sign between them
    font_plus = get_font(80, bold=True)
    draw.text((WIDTH//2, 450), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
    
    # Bottom Bar
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "ÁO MƯA")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q2_concept_rebus(progress: float, is_reveal: bool) -> Image.Image:
    """2. Concept Rebus: 🌂(Ô) + 👦🍎(Ăn) + 👲(Quan) = Ô ăn quan"""
    canvas = create_background_gradient((41, 128, 185), (25, 80, 130), pattern="star")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐÂY LÀ TRÒ CHƠI DÂN GIAN NÀO?", "CÂU 2/8", 2)
    
    # Center Stage: 3 Stickers in horizontal row
    s1 = create_umbrella_sticker(270)
    s2 = create_eating_sticker(270)
    s3 = create_mandarin_sticker(270)
    
    canvas.paste(s1, (220, 310), s1)
    canvas.paste(s2, (820, 310), s2)
    canvas.paste(s3, (1420, 310), s3)
    
    # Plus signs
    font_plus = get_font(60, bold=True)
    draw.text((640, 445), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
    draw.text((1240, 445), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
    
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "Ô ĂN QUAN (Trò chơi dân gian)")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q3_open_visual(progress: float, is_reveal: bool) -> Image.Image:
    """3. Open Visual: FC Barcelona Logo"""
    canvas = create_background_gradient((39, 174, 96), (20, 110, 60), pattern="trophy")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐÂY LÀ LOGO CỦA CÂU LẠC BỘ NÀO?", "CÂU 3/8", 3)
    
    # Large Center Crest
    crest = create_barcelona_crest(440)
    canvas.paste(crest, (WIDTH//2 - crest.width//2, 260), crest)
    
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "FC BARCELONA (Tây Ban Nha)")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q4_dont_say_same(progress: float, is_reveal: bool) -> Image.Image:
    """4. Reverse Mind Game: Đừng nói giống tôi (Kể tên môn học)"""
    canvas = create_background_gradient((142, 68, 173), (75, 25, 100), pattern="star")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐỪNG NÓI GIỐNG TÔI (TRÙNG LÀ THUA!)", "CÂU 4/8", 4)
    
    # Center Big Question Card
    bx, by, bw, bh = WIDTH//2 - 600, 240, 1200, 260
    draw.rounded_rectangle([bx + 4, by + 6, bx + bw + 4, by + bh + 6], radius=32, fill=(0, 0, 0, 70))
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=32, fill=(41, 128, 185), outline=(255, 255, 255), width=5)
    
    font_q = get_font(56, bold=True)
    draw.text((bx + bw/2, by + bh/2), "Kể tên một Môn Học trong trường", font=font_q, fill=(255, 255, 255), anchor="mm")
    
    # Mystery Capsule
    mx, my, mw, mh = WIDTH//2 - 300, 560, 600, 180
    draw.rounded_rectangle([mx + 4, my + 6, mx + mw + 4, my + mh + 6], radius=28, fill=(0, 0, 0, 70))
    if is_reveal:
        draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=5)
        font_ans = get_font(60, bold=True)
        draw.text((mx + mw/2, my + mh/2), "MÔN TOÁN ❌", font=font_ans, fill=(255, 255, 255), anchor="mm")
    else:
        draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=28, fill=(250, 250, 255), outline=(240, 200, 50), width=5)
        font_qmark = get_font(80, bold=True)
        draw.text((mx + mw/2, my + mh/2), "???", font=font_qmark, fill=(231, 76, 60), anchor="mm")
    
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "MÔN TOÁN (Ai nói Môn Toán là bị loại!)")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q5_multiple_choice(progress: float, is_reveal: bool) -> Image.Image:
    """5. Multiple Choice Fan Cứng (Messi World Cup)"""
    canvas = create_background_gradient((44, 62, 80), (20, 30, 45), pattern="trophy")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "MESSI VÔ ĐỊCH WORLD CUP CÙNG ĐỘI NÀO?", "CÂU 5/8", 5)
    
    # Left Column: Trophy Illustration Card
    trophy = create_trophy_sticker(420)
    canvas.paste(trophy, (160, 260), trophy)
    
    # Right Column: 3 Choice Pills
    choices = [("A", "Brazil"), ("B", "Argentina"), ("C", "Bồ Đào Nha")]
    py_start = 250
    for i, (cid, ctext) in enumerate(choices):
        cy = py_start + i * 150
        is_correct = (cid == "B")
        
        # Choice Box
        if is_reveal:
            fill_c = (46, 204, 113) if is_correct else (120, 130, 140)
            text_c = (255, 255, 255)
        else:
            fill_c = (255, 255, 255)
            text_c = (30, 30, 40)
            
        draw.rounded_rectangle([780, cy, 1780, cy + 115], radius=24, fill=fill_c, outline=(255, 215, 0) if not is_reveal else (255, 255, 255), width=4)
        
        # Badge Circle
        badge_fill = (46, 204, 113) if is_reveal and is_correct else (231, 76, 60)
        draw.ellipse([800, cy + 18, 880, cy + 98], fill=badge_fill)
        font_b = get_font(42, bold=True)
        if is_reveal and is_correct:
            draw.line([(825, cy + 58), (836, cy + 69), (855, cy + 46)], fill=(255, 255, 255), width=5)
        else:
            draw.text((840, cy + 58), cid, font=font_b, fill=(255, 255, 255), anchor="mm")
        
        # Choice Text
        font_t = get_font(46, bold=True)
        draw.text((920, cy + 58), ctext, font=font_t, fill=text_c, anchor="lm")
        
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "B: ARGENTINA")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q6_eat_or_pass(progress: float, is_reveal: bool) -> Image.Image:
    """6. Eat or Pass (Sầu riêng nướng phô mai)"""
    canvas = create_background_gradient((230, 126, 34), (175, 80, 10), pattern="doodle")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "SẦU RIÊNG NƯỚNG PHÔ MAI — ĂN HAY BỎ QUA?", "CÂU 6/8", 6)
    
    # Food Card Center
    food = create_durian_cheese_sticker(400)
    canvas.paste(food, (WIDTH//2 - food.width//2, 230), food)
    
    # Dual Polarity Buttons
    # Eat Button
    draw.rounded_rectangle([320, 680, 860, 810], radius=28, fill=(46, 204, 113), outline=(255, 255, 255), width=5)
    font_btn = get_font(52, bold=True)
    draw.text((590, 745), "ĂN NGAY", font=font_btn, fill=(255, 255, 255), anchor="mm")
    
    # Pass Button
    draw.rounded_rectangle([1060, 680, 1600, 810], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=5)
    draw.text((1330, 745), "BỎ QUA", font=font_btn, fill=(255, 255, 255), anchor="mm")
    
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "BẠN ĐÃ CHỌN ĂN HAY BỎ QUA?")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q7_fast_math(progress: float, is_reveal: bool) -> Image.Image:
    """7. Fast Math 5s: 90 : 9 + 5 = 15"""
    canvas = create_background_gradient((22, 100, 50), (10, 50, 25), pattern="doodle")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "THỬ THÁCH TÍNH NHẨM 5 GIÂY", "CÂU 7/8", 7)
    
    # Left Column: Owl + Blackboard
    owl = create_owl_professor(320)
    canvas.paste(owl, (140, 310), owl)
    
    # Blackboard
    draw.rounded_rectangle([480, 250, 1080, 600], radius=20, fill=(35, 75, 45), outline=(160, 100, 40), width=12)
    font_chalk = get_font(68, bold=True)
    draw.text((780, 425), "90 : 9 + 5 = ?", font=font_chalk, fill=(255, 255, 255), anchor="mm")
    
    # Right Column: 4 Choice Tiles (2x2 Grid)
    choices = [("A", "10", 1160, 250), ("B", "15", 1480, 250), ("C", "20", 1160, 440), ("D", "25", 1480, 440)]
    for cid, cval, cx, cy in choices:
        is_correct = (cid == "B")
        if is_reveal:
            fill_tile = (46, 204, 113) if is_correct else (90, 110, 100)
        else:
            fill_tile = (255, 255, 255)
            
        draw.rounded_rectangle([cx, cy, cx + 280, cy + 150], radius=24, fill=fill_tile, outline=(240, 200, 50), width=4)
        font_c = get_font(52, bold=True)
        draw.text((cx + 140, cy + 75), f"{cid}. {cval}", font=font_c, fill=(255, 255, 255) if is_reveal else (30, 30, 40), anchor="mm")
        
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "B: 15 (90 : 9 = 10; 10 + 5 = 15)")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_q8_vocab_flashcard(progress: float, is_reveal: bool) -> Image.Image:
    """8. Bilingual Vocab: Con Cáo -> Fox"""
    canvas = create_background_gradient((52, 73, 94), (25, 40, 55), pattern="star")
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "TÊN TIẾNG ANH CỦA CON VẬT NÀY LÀ GÌ?", "CÂU 8/8", 8)
    
    # Left Column: Fox Card + VN Label
    fox = create_fox_sticker(380)
    canvas.paste(fox, (160, 240), fox)
    
    draw.rounded_rectangle([200, 680, 540, 760], radius=20, fill=(255, 255, 255), outline=(240, 200, 50), width=3)
    font_lbl = get_font(42, bold=True)
    draw.text((370, 720), "Con Cáo", font=font_lbl, fill=(30, 30, 40), anchor="mm")
    
    # Right Column: 3 English Choice Pills
    choices = [("A", "Fox"), ("B", "Wolf"), ("C", "Hyena")]
    py_start = 250
    for i, (cid, ctext) in enumerate(choices):
        cy = py_start + i * 150
        is_correct = (cid == "A")
        
        if is_reveal:
            fill_c = (46, 204, 113) if is_correct else (120, 130, 140)
            text_c = (255, 255, 255)
        else:
            fill_c = (255, 255, 255)
            text_c = (30, 30, 40)
            
        draw.rounded_rectangle([780, cy, 1780, cy + 115], radius=24, fill=fill_c, outline=(255, 215, 0) if not is_reveal else (255, 255, 255), width=4)
        
        badge_fill = (46, 204, 113) if is_reveal and is_correct else (231, 76, 60)
        draw.ellipse([800, cy + 18, 880, cy + 98], fill=badge_fill)
        font_b = get_font(42, bold=True)
        if is_reveal and is_correct:
            draw.line([(825, cy + 58), (836, cy + 69), (855, cy + 46)], fill=(255, 255, 255), width=5)
        else:
            draw.text((840, cy + 58), cid, font=font_b, fill=(255, 255, 255), anchor="mm")
        
        font_t = get_font(46, bold=True)
        draw.text((920, cy + 58), ctext, font=font_t, fill=text_c, anchor="lm")
        
    if is_reveal:
        draw_reveal_bar(draw, 140, 880, 1640, 110, "A: FOX (Con Cáo)")
    else:
        draw_sliding_timer_bar(draw, canvas, clock_icon, 140, 890, 1640, 80, progress)
    return canvas

def render_intro_card() -> Image.Image:
    canvas = create_background_gradient((235, 87, 87), (180, 40, 40), pattern="trophy")
    draw = ImageDraw.Draw(canvas)
    
    # Big Title Banner
    bx, by, bw, bh = WIDTH//2 - 700, 220, 1400, 220
    draw.rounded_rectangle([bx + 6, by + 8, bx + bw + 6, by + bh + 8], radius=40, fill=(0, 0, 0, 70))
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=40, fill=(255, 215, 0), outline=(255, 255, 255), width=6)
    
    font_main = get_font(84, bold=True)
    draw.text((WIDTH//2, 330), "RABBIT GAME", font=font_main, fill=(180, 20, 20), anchor="mm")
    
    # Subtitle
    font_sub = get_font(52, bold=True)
    draw.text((WIDTH//2, 540), "THỬ THÁCH 8 THỂ LOẠI ĐỐ VUI SIÊU HACK NÃO", font=font_sub, fill=(255, 255, 255), anchor="mm")
    
    # CTA Pills
    draw.rounded_rectangle([WIDTH//2 - 450, 680, WIDTH//2 + 450, 780], radius=28, fill=(46, 204, 113), outline=(255, 255, 255), width=4)
    font_cta = get_font(44, bold=True)
    draw.text((WIDTH//2, 730), "BẠN TRẢ LỜI ĐÚNG ĐƯỢC BAO NHIÊU CÂU?", font=font_cta, fill=(255, 255, 255), anchor="mm")
    return canvas

def render_outro_card() -> Image.Image:
    canvas = create_background_gradient((41, 128, 185), (20, 70, 120), pattern="star")
    draw = ImageDraw.Draw(canvas)
    
    # Finish Banner
    bx, by, bw, bh = WIDTH//2 - 650, 220, 1300, 200
    draw.rounded_rectangle([bx + 6, by + 8, bx + bw + 6, by + bh + 8], radius=36, fill=(0, 0, 0, 70))
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=36, fill=(46, 204, 113), outline=(255, 255, 255), width=6)
    
    font_main = get_font(76, bold=True)
    draw.text((WIDTH//2, 320), "XIN CHÚC MỪNG!", font=font_main, fill=(255, 255, 255), anchor="mm")
    
    font_sub = get_font(50, bold=True)
    draw.text((WIDTH//2, 530), "Bạn đã trả lời đúng được bao nhiêu câu hỏi?", font=font_sub, fill=(255, 215, 0), anchor="mm")
    
    # Like & Sub Buttons
    draw.rounded_rectangle([380, 680, 880, 790], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
    font_btn = get_font(44, bold=True)
    draw.text((630, 735), "BẤM LIKE", font=font_btn, fill=(255, 255, 255), anchor="mm")
    
    draw.rounded_rectangle([1040, 680, 1540, 790], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
    draw.text((1290, 735), "ĐĂNG KÝ KÊNH", font=font_btn, fill=(255, 255, 255), anchor="mm")
    return canvas

# -------------------------------------------------------------
# VIDEO COMPILATION & RENDERING PIPELINE
# -------------------------------------------------------------

def get_audio_duration(file_path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())

def main():
    print("Starting Rabbit Game 8-Archetypes Master Video Generation...")
    
    # 1. Probe audio durations
    durations = {
        "intro": get_audio_duration(AUDIO_DIR / "intro.mp3"),
        "q1_q": get_audio_duration(AUDIO_DIR / "q1_q.mp3"),
        "q1_a": get_audio_duration(AUDIO_DIR / "q1_a.mp3"),
        "q2_q": get_audio_duration(AUDIO_DIR / "q2_q.mp3"),
        "q2_a": get_audio_duration(AUDIO_DIR / "q2_a.mp3"),
        "q3_q": get_audio_duration(AUDIO_DIR / "q3_q.mp3"),
        "q3_a": get_audio_duration(AUDIO_DIR / "q3_a.mp3"),
        "q4_q": get_audio_duration(AUDIO_DIR / "q4_q.mp3"),
        "q4_a": get_audio_duration(AUDIO_DIR / "q4_a.mp3"),
        "q5_q": get_audio_duration(AUDIO_DIR / "q5_q.mp3"),
        "q5_a": get_audio_duration(AUDIO_DIR / "q5_a.mp3"),
        "q6_q": get_audio_duration(AUDIO_DIR / "q6_q.mp3"),
        "q6_a": get_audio_duration(AUDIO_DIR / "q6_a.mp3"),
        "q7_q": get_audio_duration(AUDIO_DIR / "q7_q.mp3"),
        "q7_a": get_audio_duration(AUDIO_DIR / "q7_a.mp3"),
        "q8_q": get_audio_duration(AUDIO_DIR / "q8_q.mp3"),
        "q8_a": get_audio_duration(AUDIO_DIR / "q8_a.mp3"),
        "outro": get_audio_duration(AUDIO_DIR / "outro.mp3"),
    }
    print("Audio durations:", durations)

    # 2. Render all question sequences
    archetype_renderers = [
        ("q1", render_q1_emoji_rebus),
        ("q2", render_q2_concept_rebus),
        ("q3", render_q3_open_visual),
        ("q4", render_q4_dont_say_same),
        ("q5", render_q5_multiple_choice),
        ("q6", render_q6_eat_or_pass),
        ("q7", render_q7_fast_math),
        ("q8", render_q8_vocab_flashcard),
    ]
    
    concat_lines = []
    
    # Intro
    intro_img = render_intro_card()
    intro_path = FRAMES_DIR / "frame_intro.png"
    intro_img.save(intro_path)
    intro_dur = durations["intro"] + 0.6
    concat_lines.append(f"file '{intro_path.name}'\nduration {intro_dur:.3f}")
    
    for qkey, renderer in archetype_renderers:
        q_dur = durations[f"{qkey}_q"] + 0.3
        cd_dur = 4.0  # 4 seconds countdown
        a_dur = durations[f"{qkey}_a"] + 0.8
        
        # 1. Question Voice Phase (progress = 1.0)
        q_img = renderer(1.0, is_reveal=False)
        q_path = FRAMES_DIR / f"frame_{qkey}_question.png"
        q_img.save(q_path)
        concat_lines.append(f"file '{q_path.name}'\nduration {q_dur:.3f}")
        
        # 2. Countdown Animation Frames (10 key steps for smooth clock slider)
        steps = 12
        step_dur = cd_dur / steps
        for s in range(steps):
            prog = 1.0 - (s / steps)
            cd_img = renderer(prog, is_reveal=False)
            cd_path = FRAMES_DIR / f"frame_{qkey}_cd_{s:02d}.png"
            cd_img.save(cd_path)
            concat_lines.append(f"file '{cd_path.name}'\nduration {step_dur:.3f}")
            
        # 3. Reveal Answer Phase
        rev_img = renderer(0.0, is_reveal=True)
        rev_path = FRAMES_DIR / f"frame_{qkey}_reveal.png"
        rev_img.save(rev_path)
        concat_lines.append(f"file '{rev_path.name}'\nduration {a_dur:.3f}")
        
    # Outro
    outro_img = render_outro_card()
    outro_path = FRAMES_DIR / "frame_outro.png"
    outro_img.save(outro_path)
    outro_dur = durations["outro"] + 1.0
    concat_lines.append(f"file '{outro_path.name}'\nduration {outro_dur:.3f}")
    # Last image duplicate rule for ffmpeg concat
    concat_lines.append(f"file '{outro_path.name}'")
    
    concat_file = FRAMES_DIR / "quiz_showcase.ffconcat"
    with open(concat_file, "w", encoding="utf-8") as f:
        f.write("\n".join(concat_lines))
    print(f"Generated ffconcat file with {len(concat_lines)} entries.")

    # 3. Build Audio Timeline (Voice + SFX ticks + SFX dings + BGM)
    # Calculate exact timestamp for each event
    cur_t = 0.0
    voice_inputs = []
    voice_delays = []
    
    # Add intro voice
    voice_inputs.append(str(AUDIO_DIR / "intro.mp3"))
    voice_delays.append(int(cur_t * 1000))
    cur_t += durations["intro"] + 0.6
    
    sfx_cd_delays = []
    sfx_ding_delays = []
    
    for qkey, _ in archetype_renderers:
        q_dur = durations[f"{qkey}_q"] + 0.3
        cd_dur = 4.0
        a_dur = durations[f"{qkey}_a"] + 0.8
        
        # Question voice starts at cur_t
        voice_inputs.append(str(AUDIO_DIR / f"{qkey}_q.mp3"))
        voice_delays.append(int(cur_t * 1000))
        cur_t += q_dur
        
        # Countdown SFX starts at cur_t
        sfx_cd_delays.append(int(cur_t * 1000))
        cur_t += cd_dur
        
        # Reveal Ding SFX + Answer Voice starts at cur_t
        sfx_ding_delays.append(int(cur_t * 1000))
        voice_inputs.append(str(AUDIO_DIR / f"{qkey}_a.mp3"))
        voice_delays.append(int((cur_t + 0.1) * 1000))
        cur_t += a_dur
        
    # Outro voice
    voice_inputs.append(str(AUDIO_DIR / "outro.mp3"))
    voice_delays.append(int(cur_t * 1000))
    cur_t += durations["outro"] + 1.0
    
    total_video_dur = cur_t
    print(f"Total Video Duration: {total_video_dur:.2f} seconds (~{total_video_dur/60:.1f} minutes)")

    # 4. Multi-Track Audio Mixing via FFmpeg Filter Complex
    # Input 0: quiz_showcase.ffconcat
    # Input 1..N: Voice files
    # Input N+1: sfx_countdown
    # Input N+2: sfx_ding
    # Input N+3: bgm_quiz
    
    input_args = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    for vpath in voice_inputs:
        input_args.extend(["-i", vpath])
        
    cd_sfx_idx = len(voice_inputs) + 1
    ding_sfx_idx = len(voice_inputs) + 2
    bgm_idx = len(voice_inputs) + 3
    
    input_args.extend(["-i", str(AUDIO_DIR / "sfx_countdown.wav")])
    input_args.extend(["-i", str(AUDIO_DIR / "sfx_ding.wav")])
    input_args.extend(["-i", str(AUDIO_DIR / "bgm_quiz.wav")])
    
    filter_parts = []
    
    # 4a. Delay and mix all voice lines
    voice_mixed_labels = []
    for i, dms in enumerate(voice_delays):
        idx = i + 1
        filter_parts.append(f"[{idx}:a]adelay={dms}|{dms}[v_{i}]")
        voice_mixed_labels.append(f"[v_{i}]")
    filter_parts.append(f"{''.join(voice_mixed_labels)}amix=inputs={len(voice_mixed_labels)}:duration=longest:normalize=0[voice_main]")
    
    # 4b. Delay and mix countdown SFX
    cd_mixed_labels = []
    for i, dms in enumerate(sfx_cd_delays):
        filter_parts.append(f"[{cd_sfx_idx}:a]adelay={dms}|{dms}[cd_{i}]")
        cd_mixed_labels.append(f"[cd_{i}]")
    filter_parts.append(f"{''.join(cd_mixed_labels)}amix=inputs={len(cd_mixed_labels)}:duration=longest:normalize=0[cd_main]")
    
    # 4c. Delay and mix ding SFX
    ding_mixed_labels = []
    for i, dms in enumerate(sfx_ding_delays):
        filter_parts.append(f"[{ding_sfx_idx}:a]adelay={dms}|{dms}[ding_{i}]")
        ding_mixed_labels.append(f"[ding_{i}]")
    filter_parts.append(f"{''.join(ding_mixed_labels)}amix=inputs={len(ding_mixed_labels)}:duration=longest:normalize=0[ding_main]")
    
    # Mix all SFX
    filter_parts.append(f"[cd_main][ding_main]amix=inputs=2:duration=longest:normalize=0,volume=1.2[sfx_main]")
    
    # 4d. Loop BGM with Sidechain Compression (Ducking when voice plays)
    filter_parts.append(f"[{bgm_idx}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_video_dur:.2f},volume=-18dB,aresample=48000[bgm_raw]")
    filter_parts.append(f"[voice_main]asplit=2[v_play][v_sc]")
    filter_parts.append(f"[bgm_raw][v_sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=350[bgm_ducked]")
    
    # 4e. Final 3-track Mix (Voice + SFX + Ducked BGM)
    filter_parts.append(f"[v_play][sfx_main][bgm_ducked]amix=inputs=3:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[final_audio]")
    
    filter_complex = ";".join(filter_parts)
    
    final_output_path = FINAL_DIR / "rabbit_game_8archetypes_showcase.mp4"
    
    cmd = input_args + [
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[final_audio]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_output_path)
    ]
    
    print("Running FFmpeg video compilation...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg Error:", res.stderr[-1000:])
        return False
        
    print(f"SUCCESS! Master Video exported to: {final_output_path.resolve()}")
    print(f"File size: {final_output_path.stat().st_size / (1024*1024):.2f} MB")
    return True

if __name__ == "__main__":
    main()
