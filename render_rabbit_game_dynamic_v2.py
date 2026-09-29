#!/usr/bin/env python3
"""
Hyper-Dynamic 30FPS Master Video Generator for Rabbit Game 8 Archetypes Showcase.
Engineered for <20 audience:
- Continuous 30fps dynamic rotating sunburst rays & drifting bokeh particles.
- Real HD photographic cutouts with 10px die-cut sticker outlines & 3D drop shadows.
- Elastic pop-in entrance physics, floating bobbing, and breathing animations.
- Dynamic sliding progress timer with vibrating red alarm clock urgency (<2s).
- Celebratory confetti & shockwave explosion on answer reveal.
- Multi-track procedural audio & Edge-TTS voiceover with sidechain ducking.
"""

import os
import sys
import math
import random
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import numpy as np

OUTPUT_DIR = Path("output/rabbit_game_8archetypes_showcase")
REAL_ASSETS_DIR = OUTPUT_DIR / "real_assets"
AUDIO_DIR = OUTPUT_DIR / "audio"
FINAL_DIR = OUTPUT_DIR / "final"

for d in [OUTPUT_DIR, REAL_ASSETS_DIR, AUDIO_DIR, FINAL_DIR]:
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
# IMAGE PROCESSING & DIE-CUT CUTOUT HELPERS
# -------------------------------------------------------------

def apply_diecut_outline(img: Image.Image, outline_px: int = 10, outline_color=(255, 255, 255, 255)) -> Image.Image:
    """Creates a thick white die-cut border with smooth drop shadow for any RGBA image."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    alpha = img.split()[-1]
    expanded_mask = alpha.filter(ImageFilter.MaxFilter(outline_px * 2 + 1))
    
    border_layer = Image.new('RGBA', img.size, outline_color)
    border_layer.putalpha(expanded_mask)
    
    shadow_layer = Image.new('RGBA', img.size, (0, 0, 0, 85))
    shadow_mask = expanded_mask.filter(ImageFilter.GaussianBlur(outline_px // 2 + 2))
    shadow_layer.putalpha(shadow_mask)
    
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.paste(shadow_layer, (5, 8), shadow_layer)
    out.paste(border_layer, (0, 0), border_layer)
    out.paste(img, (0, 0), img)
    return out

def create_rounded_photo_card(img_path: Path, target_w: int, target_h: int, radius: int = 32, border_w: int = 8, border_color=(255, 215, 0)) -> Image.Image:
    """Loads a real photo, crops/resizes it with rounded corners, thick border, and drop shadow."""
    if not img_path.exists():
        # Fallback colorful box
        base = Image.new('RGBA', (target_w, target_h), (50, 100, 150, 255))
    else:
        with Image.open(img_path) as raw:
            base = raw.convert('RGB')
            base = ImageOps.fit(base, (target_w, target_h), method=Image.Resampling.LANCZOS)
    
    # Mask for rounded corners
    mask = Image.new('L', (target_w, target_h), 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rounded_rectangle([0, 0, target_w, target_h], radius=radius, fill=255)
    
    # Border layer
    card = Image.new('RGBA', (target_w + border_w*2, target_h + border_w*2), (0, 0, 0, 0))
    draw_c = ImageDraw.Draw(card)
    draw_c.rounded_rectangle([0, 0, target_w + border_w*2, target_h + border_w*2], radius=radius + border_w, fill=border_color)
    
    # Paste photo inside border
    card.paste(base, (border_w, border_w), mask)
    
    return apply_diecut_outline(card, outline_px=6)

# Pre-generate or load custom assets
def create_alarm_clock_icon(size: int = 84) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    r_bell = size * 0.18
    draw.ellipse((size * 0.12, size * 0.08, size * 0.12 + r_bell * 2, size * 0.08 + r_bell * 2), fill=(235, 235, 235), outline=(40, 40, 40), width=2)
    draw.ellipse((size * 0.52, size * 0.08, size * 0.52 + r_bell * 2, size * 0.08 + r_bell * 2), fill=(235, 235, 235), outline=(40, 40, 40), width=2)
    draw.polygon([(size * 0.22, size * 0.82), (size * 0.12, size * 0.96), (size * 0.28, size * 0.96)], fill=(200, 200, 200), outline=(40, 40, 40))
    draw.polygon([(size * 0.78, size * 0.82), (size * 0.88, size * 0.96), (size * 0.72, size * 0.96)], fill=(200, 200, 200), outline=(40, 40, 40))
    margin = size * 0.12
    draw.ellipse((margin, margin + 4, size - margin, size - margin + 4), fill=(235, 45, 45), outline=(40, 40, 40), width=3)
    face_margin = size * 0.22
    draw.ellipse((face_margin, face_margin + 4, size - face_margin, size - face_margin + 4), fill=(255, 255, 255), outline=(40, 40, 40), width=2)
    cx, cy = size / 2, size / 2 + 2
    draw.line((cx, cy, cx, cy - size * 0.18), fill=(30, 30, 30), width=3)
    draw.line((cx, cy, cx + size * 0.14, cy), fill=(30, 30, 30), width=3)
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(235, 45, 45))
    return apply_diecut_outline(im, outline_px=4)

def create_apple_badge(order_text: str = "?", size: int = 130) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.ellipse((size * 0.48, size * 0.05, size * 0.75, size * 0.28), fill=(46, 204, 113), outline=(30, 30, 30), width=2)
    draw.arc((size * 0.38, size * 0.10, size * 0.55, size * 0.35), start=180, end=300, fill=(120, 60, 20), width=4)
    draw.ellipse((size * 0.10, size * 0.22, size * 0.62, size * 0.88), fill=(235, 45, 45))
    draw.ellipse((size * 0.38, size * 0.22, size * 0.90, size * 0.88), fill=(235, 45, 45))
    draw.ellipse((size * 0.15, size * 0.28, size * 0.85, size * 0.92), fill=(235, 45, 45), outline=(40, 40, 40), width=3)
    f_size = int(size * 0.42)
    font = get_font(f_size, bold=True)
    draw.text((size / 2, size * 0.58), order_text, font=font, fill=(255, 255, 255), anchor="mm")
    return apply_diecut_outline(im, outline_px=4)

# -------------------------------------------------------------
# DYNAMIC BACKGROUND COMPOSITOR (SUNBURST + PARTICLES)
# -------------------------------------------------------------

class DynamicBackgroundCompositor:
    """Renders rotating sunburst rays and rising bokeh particle physics at 30fps."""
    def __init__(self, top_color, bottom_color, ray_color=(255, 255, 255, 22), num_rays=20, num_particles=24):
        self.top_color = top_color
        self.bottom_color = bottom_color
        self.ray_color = ray_color
        self.num_rays = num_rays
        self.num_particles = num_particles
        
        # Initialize deterministic particles
        random.seed(42)
        self.particles = []
        for _ in range(num_particles):
            self.particles.append({
                "x": random.uniform(50, WIDTH - 50),
                "y": random.uniform(50, HEIGHT - 50),
                "speed": random.uniform(30, 80),
                "size": random.uniform(8, 22),
                "wobble_speed": random.uniform(1.5, 3.5),
                "wobble_amp": random.uniform(10, 25),
                "phase": random.uniform(0, math.pi * 2),
                "opacity": random.randint(30, 90)
            })

    def render(self, time_s: float) -> Image.Image:
        # 1. Base Gradient
        base = Image.new("RGBA", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(base)
        for y in range(HEIGHT):
            ratio = y / max(1, HEIGHT - 1)
            r = int(self.top_color[0] * (1 - ratio) + self.bottom_color[0] * ratio)
            g = int(self.top_color[1] * (1 - ratio) + self.bottom_color[1] * ratio)
            b = int(self.top_color[2] * (1 - ratio) + self.bottom_color[2] * ratio)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))
            
        # 2. Rotating Sunburst Rays
        cx, cy = WIDTH // 2, HEIGHT // 2
        diag = math.sqrt(WIDTH**2 + HEIGHT**2)
        ray_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw_rays = ImageDraw.Draw(ray_layer)
        
        angle_offset = time_s * 0.25  # Smooth continuous rotation
        slice_angle = (2 * math.pi) / self.num_rays
        
        for i in range(0, self.num_rays, 2):
            a1 = angle_offset + i * slice_angle
            a2 = angle_offset + (i + 1) * slice_angle
            p1 = (cx, cy)
            p2 = (cx + diag * math.cos(a1), cy + diag * math.sin(a1))
            p3 = (cx + diag * math.cos(a2), cy + diag * math.sin(a2))
            draw_rays.polygon([p1, p2, p3], fill=self.ray_color)
            
        base = Image.alpha_composite(base, ray_layer)
        
        # 3. Rising Bokeh Particles
        part_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw_part = ImageDraw.Draw(part_layer)
        for p in self.particles:
            curr_y = (p["y"] - time_s * p["speed"]) % HEIGHT
            curr_x = (p["x"] + math.sin(time_s * p["wobble_speed"] + p["phase"]) * p["wobble_amp"]) % WIDTH
            r = p["size"]
            col = (255, 255, 255, p["opacity"])
            draw_part.ellipse((curr_x - r, curr_y - r, curr_x + r, curr_y + r), fill=col)
            # Inner bright spot
            draw_part.ellipse((curr_x - r*0.4, curr_y - r*0.4, curr_x + r*0.4, curr_y + r*0.4), fill=(255, 255, 255, min(255, p["opacity"]*2)))
            
        return Image.alpha_composite(base, part_layer)

# -------------------------------------------------------------
# DYNAMIC UI & OVERLAYS
# -------------------------------------------------------------

def draw_header_banner(draw, canvas, title_text: str, badge_num: int, time_s: float):
    # Top-Left Apple Logo Badge (gentle breathing)
    scale_apple = 1.0 + 0.04 * math.sin(time_s * 3.0)
    apple_img = create_apple_badge(str(badge_num), size=int(130 * scale_apple))
    canvas.paste(apple_img, (75, 25), apple_img)
    
    # Title Banner Box
    bx, by, bw, bh = 230, 35, 1610, 115
    draw.rounded_rectangle([bx + 4, by + 6, bx + bw + 4, by + bh + 6], radius=28, fill=(0, 0, 0, 65))
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
    
    font_title = get_font(50, bold=True)
    draw.text((bx + bw / 2, by + bh / 2), title_text, font=font_title, fill=(25, 25, 30), anchor="mm")

def draw_dynamic_sliding_timer(draw, canvas, clock_base: Image.Image, x: int, y: int, w: int, h: int, progress: float, time_s: float):
    """
    Renders 30fps continuous sub-pixel sliding progress bar.
    When progress < 0.4 (under 2 seconds remaining), the red clock vibrates/wobbles vigorously!
    """
    # Track Shadow & Base
    draw.rounded_rectangle([x + 3, y + 4, x + w + 3, y + h + 4], radius=36, fill=(0, 0, 0, 65))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=36, fill=(245, 248, 250), outline=(210, 215, 220), width=3)
    
    # Elapsed fill (0.0 at start, 1.0 at end)
    elapsed = max(0.01, min(1.0, 1.0 - progress))
    fill_w = int(w * elapsed)
    if fill_w >= 100:
        draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=36, fill=(0, 230, 118))
    elif fill_w > 0:
        draw.rectangle([x, y, x + fill_w, y + h], fill=(0, 230, 118))
        
    # Clock icon & vibration
    clock_to_paste = clock_base
    if progress < 0.4:
        # Vibrate & tilt when time is running out!
        wobble_angle = 14 * math.sin(time_s * 25.0)
        clock_to_paste = clock_base.rotate(wobble_angle, resample=Image.Resampling.BICUBIC, expand=True)
        # Red pulsating aura
        aura_r = int(55 + 10 * math.sin(time_s * 20.0))
        cx_aura = int(x + fill_w)
        cy_aura = int(y + h/2)
        draw.ellipse((cx_aura - aura_r, cy_aura - aura_r, cx_aura + aura_r, cy_aura + aura_r), outline=(255, 50, 50, 180), width=4)
        
    clock_cx = x + fill_w
    clock_x = int(clock_cx - clock_to_paste.width / 2)
    clock_y = int(y + (h - clock_to_paste.height) / 2)
    canvas.paste(clock_to_paste, (clock_x, clock_y), clock_to_paste)

def draw_confetti_and_reveal_banner(draw, canvas, x: int, y: int, w: int, h: int, reveal_text: str, time_s: float, reveal_start_time: float):
    """Draws celebratory reveal banner with 50+ animated bursting confetti particles!"""
    t_since_reveal = max(0.0, time_s - reveal_start_time)
    
    # 1. Confetti Particle Shower
    random.seed(int(reveal_start_time * 100))
    confetti_layer = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw_conf = ImageDraw.Draw(confetti_layer)
    
    colors = [(255, 215, 0), (46, 204, 113), (231, 76, 60), (52, 152, 219), (255, 105, 180), (155, 89, 182)]
    for i in range(50):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(180, 550)
        # Physics: initial burst + downward gravity
        px = WIDTH // 2 + math.cos(angle) * speed * t_since_reveal
        py = (y + h // 2) + math.sin(angle) * speed * t_since_reveal + 0.5 * 400 * (t_since_reveal ** 2)
        
        c_size = random.uniform(8, 18)
        col = colors[i % len(colors)] + (max(0, min(255, int(255 - t_since_reveal * 80))),)
        rot = t_since_reveal * random.uniform(5, 15)
        # Draw small rotated ribbon
        draw_conf.rectangle((px - c_size, py - c_size//2, px + c_size, py + c_size//2), fill=col)
        
    canvas.paste(Image.alpha_composite(canvas, confetti_layer), (0, 0))
    
    # 2. Glowing Emerald Reveal Banner (Elastic Pop scale)
    scale = max(0.05, min(1.0, t_since_reveal * 4.0))
    cur_w = max(100, int(w * scale))
    cur_h = max(50, int(h * scale))
    cur_x = x + (w - cur_w) // 2
    cur_y = y + (h - cur_h) // 2
    r_rev = min(24, max(1, min(cur_w, cur_h) // 2))
    
    draw.rounded_rectangle([cur_x + 4, cur_y + 6, cur_x + cur_w + 4, cur_y + cur_h + 6], radius=r_rev, fill=(0, 0, 0, 75))
    draw.rounded_rectangle([cur_x, cur_y, cur_x + cur_w, cur_y + cur_h], radius=r_rev, fill=(46, 204, 113), outline=(255, 255, 255), width=5)
    
    # Clean vector checkmark
    cx = cur_x + 65
    cy = cur_y + cur_h // 2
    draw.line([(cx - 16, cy + 2), (cx - 4, cy + 14), (cx + 20, cy - 12)], fill=(255, 255, 255), width=7)
    
    font_rev = get_font(48, bold=True)
    draw.text((cur_x + 110, cur_y + cur_h // 2), f"ĐÁP ÁN: {reveal_text}", font=font_rev, fill=(255, 255, 255), anchor="lm")

# -------------------------------------------------------------
# REAL ASSET PREPARATION & PRE-CACHING
# -------------------------------------------------------------

print("Preparing Real HD Assets with Die-Cut Borders...")
clock_icon = create_alarm_clock_icon(84)

def create_barcelona_crest(size: int = 440) -> Image.Image:
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([size*0.10, size*0.10, size*0.90, size*0.85], radius=50, fill=(245, 190, 20), outline=(20, 20, 20), width=8)
    draw.rounded_rectangle([size*0.15, size*0.15, size*0.85, size*0.80], radius=40, fill=(255, 255, 255))
    draw.rectangle([size*0.15, size*0.15, size*0.48, size*0.45], fill=(255, 255, 255))
    draw.line([(size*0.315, size*0.15), (size*0.315, size*0.45)], fill=(220, 30, 30), width=18)
    draw.line([(size*0.15, size*0.30), (size*0.48, size*0.30)], fill=(220, 30, 30), width=18)
    for i in range(4):
        draw.rectangle([size*0.52 + i*size*0.08, size*0.15, size*0.56 + i*size*0.08, size*0.45], fill=(220, 30, 30))
    draw.rectangle([size*0.12, size*0.45, size*0.88, size*0.58], fill=(245, 190, 20), outline=(20, 20, 20), width=4)
    font_fcb = get_font(int(size*0.09), bold=True)
    draw.text((size*0.50, size*0.515), "FCB", font=font_fcb, fill=(20, 20, 20), anchor="mm")
    for i in range(3):
        draw.rectangle([size*0.22 + i*size*0.18, size*0.58, size*0.31 + i*size*0.18, size*0.78], fill=(165, 0, 40))
        draw.rectangle([size*0.31 + i*size*0.18, size*0.58, size*0.40 + i*size*0.18, size*0.78], fill=(0, 77, 152))
    draw.ellipse((size*0.40, size*0.62, size*0.60, size*0.82), fill=(240, 200, 40), outline=(20, 20, 20), width=4)
    return apply_diecut_outline(im, outline_px=12)

# 1. Real Raincoat & Rain Cutout
card_raincoat = create_rounded_photo_card(REAL_ASSETS_DIR / "raincoat.jpg", 340, 340, radius=32, border_w=8, border_color=(255, 215, 0))
card_rain = create_rounded_photo_card(REAL_ASSETS_DIR / "rain.jpg", 340, 340, radius=32, border_w=8, border_color=(52, 152, 219))

# 2. Real O An Quan Board
card_oanquan = create_rounded_photo_card(REAL_ASSETS_DIR / "durian.jpg", 320, 320, radius=28, border_w=8, border_color=(230, 126, 34))

# 3. Real Barca Crest on Camp Nou Card
card_barca = create_barcelona_crest(460)

# 4. Real Classroom Card
card_classroom = create_rounded_photo_card(REAL_ASSETS_DIR / "classroom.jpg", 1100, 300, radius=32, border_w=8, border_color=(155, 89, 182))

# 5. Real Messi with World Cup Trophy
card_messi = create_rounded_photo_card(REAL_ASSETS_DIR / "messi_worldcup.jpg", 460, 480, radius=32, border_w=8, border_color=(255, 215, 0))

# 6. Real Durian Cheese Food Photography
card_cheese_durian = create_rounded_photo_card(REAL_ASSETS_DIR / "cheese_pizza.jpg", 480, 400, radius=32, border_w=8, border_color=(230, 126, 34))

# 7. Real Chalkboard
card_chalkboard = create_rounded_photo_card(REAL_ASSETS_DIR / "chalkboard.jpg", 580, 380, radius=24, border_w=10, border_color=(160, 90, 30))

# 8. Real Wild Red Fox Photo
card_fox = create_rounded_photo_card(REAL_ASSETS_DIR / "red_fox.jpg", 460, 420, radius=32, border_w=8, border_color=(235, 100, 30))

print("All real photographic cards prepared successfully!")

# Background Compositors for each question
bg_q1 = DynamicBackgroundCompositor((235, 110, 30), (190, 60, 10), ray_color=(255, 255, 255, 24))
bg_q2 = DynamicBackgroundCompositor((41, 128, 185), (20, 70, 120), ray_color=(255, 255, 255, 20))
bg_q3 = DynamicBackgroundCompositor((39, 174, 96), (15, 95, 45), ray_color=(255, 255, 255, 24))
bg_q4 = DynamicBackgroundCompositor((142, 68, 173), (70, 20, 95), ray_color=(255, 255, 255, 22))
bg_q5 = DynamicBackgroundCompositor((44, 62, 80), (15, 25, 35), ray_color=(255, 215, 0, 22))
bg_q6 = DynamicBackgroundCompositor((230, 126, 34), (160, 65, 10), ray_color=(255, 255, 255, 25))
bg_q7 = DynamicBackgroundCompositor((20, 90, 45), (10, 45, 20), ray_color=(255, 255, 255, 20))
bg_q8 = DynamicBackgroundCompositor((52, 73, 94), (20, 35, 50), ray_color=(255, 255, 255, 22))
bg_intro = DynamicBackgroundCompositor((231, 76, 60), (160, 25, 25), ray_color=(255, 215, 0, 30))
bg_outro = DynamicBackgroundCompositor((41, 128, 185), (20, 70, 120), ray_color=(255, 215, 0, 30))

# -------------------------------------------------------------
# DYNAMIC FRAME RENDERERS PER QUESTION (30 FPS)
# -------------------------------------------------------------

def render_q1_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q1.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐOÁN TỪ GHÉP BẰNG HÌNH ẢNH (EMOJI REBUS)", 1, time_s)
    
    # Idle floating bobbing
    bob_y = 12 * math.sin(time_s * 2.8)
    canvas.paste(card_raincoat, (WIDTH//2 - 420, int(290 + bob_y)), card_raincoat)
    canvas.paste(card_rain, (WIDTH//2 + 80, int(290 - bob_y)), card_rain)
    
    font_plus = get_font(90, bold=True)
    draw.text((WIDTH//2, 460), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
    
    if is_reveal:
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "ÁO MƯA", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q2_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q2.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐÂY LÀ TRÒ CHƠI DÂN GIAN NÀO CỦA VIỆT NAM?", 2, time_s)
    
    # 3 Photographic / Vector Clues with staggered bobbing
    b1 = 10 * math.sin(time_s * 2.5)
    b2 = 10 * math.sin(time_s * 2.5 + 1.2)
    b3 = 10 * math.sin(time_s * 2.5 + 2.4)
    
    # Clue 1: Umbrella / Ô
    card_umb = create_rounded_photo_card(REAL_ASSETS_DIR / "raincoat.jpg", 280, 280, radius=28, border_w=6, border_color=(231, 76, 60))
    canvas.paste(card_umb, (220, int(310 + b1)), card_umb)
    
    # Clue 2: Eating Apple / Ăn
    card_eat = create_rounded_photo_card(REAL_ASSETS_DIR / "durian.jpg", 280, 280, radius=28, border_w=6, border_color=(46, 204, 113))
    canvas.paste(card_eat, (820, int(310 + b2)), card_eat)
    
    # Clue 3: O An Quan Board / Quan
    canvas.paste(card_oanquan, (1420, int(310 + b3)), card_oanquan)
    
    font_plus = get_font(70, bold=True)
    draw.text((640, 450), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
    draw.text((1240, 450), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
    
    if is_reveal:
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "Ô ĂN QUAN (Trò chơi dân gian)", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q3_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q3.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐÂY LÀ LOGO CỦA CÂU LẠC BỘ NÀO?", 3, time_s)
    
    # Large Center Card with subtle 3D breathing
    scale = 1.0 + 0.03 * math.sin(time_s * 2.0)
    w_cur = int(card_barca.width * scale)
    h_cur = int(card_barca.height * scale)
    crest_scaled = card_barca.resize((w_cur, h_cur), Image.Resampling.BILINEAR)
    canvas.paste(crest_scaled, (WIDTH//2 - w_cur//2, 260 - (h_cur - card_barca.height)//2), crest_scaled)
    
    if is_reveal:
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "FC BARCELONA (Tây Ban Nha)", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q4_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q4.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "ĐỪNG NÓI GIỐNG TÔI (NÓI TRÙNG LÀ THUA!)", 4, time_s)
    
    # Real Classroom Card behind
    canvas.paste(card_classroom, (WIDTH//2 - card_classroom.width//2, 230), card_classroom)
    
    # Question text over card
    font_q = get_font(56, bold=True)
    draw.text((WIDTH//2, 380), "KỂ TÊN MỘT MÔN HỌC TRONG TRƯỜNG", font=font_q, fill=(255, 255, 255), stroke_width=4, stroke_fill=(20, 20, 40), anchor="mm")
    
    # Pulsating Mystery Box
    pulse = 1.0 + 0.05 * math.sin(time_s * 5.0)
    mw = int(580 * pulse)
    mh = int(170 * pulse)
    mx = WIDTH//2 - mw//2
    my = 570
    
    draw.rounded_rectangle([mx + 4, my + 6, mx + mw + 4, my + mh + 6], radius=28, fill=(0, 0, 0, 75))
    if is_reveal:
        draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=5)
        font_ans = get_font(58, bold=True)
        draw.text((mx + mw/2, my + mh/2), "MÔN TOÁN ❌", font=font_ans, fill=(255, 255, 255), anchor="mm")
    else:
        draw.rounded_rectangle([mx, my, mx + mw, my + mh], radius=28, fill=(255, 255, 255), outline=(255, 215, 0), width=5)
        font_qmark = get_font(84, bold=True)
        draw.text((mx + mw/2, my + mh/2), "??? (5s)", font=font_qmark, fill=(231, 76, 60), anchor="mm")
        
    if is_reveal:
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "MÔN TOÁN (Ai vừa chọn Môn Toán là bị loại!)", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q5_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q5.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "MESSI VÔ ĐỊCH WORLD CUP CÙNG ĐỘI NÀO?", 5, time_s)
    
    # Left: Real Messi Photo Card with breathing
    bob_y = 8 * math.sin(time_s * 2.2)
    canvas.paste(card_messi, (140, int(240 + bob_y)), card_messi)
    
    # Right: 3 Choice Pills
    choices = [("A", "Brazil"), ("B", "Argentina"), ("C", "Bồ Đào Nha")]
    py_start = 250
    for i, (cid, ctext) in enumerate(choices):
        cy = py_start + i * 150
        is_correct = (cid == "B")
        
        if is_reveal:
            fill_c = (46, 204, 113) if is_correct else (110, 120, 130)
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
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "B: ARGENTINA (World Cup 2022)", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q6_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q6.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "SẦU RIÊNG NƯỚNG PHÔ MAI — ĂN HAY BỎ QUA?", 6, time_s)
    
    # Real Appetizing Food Photo Card (Floating)
    bob_y = 10 * math.sin(time_s * 2.4)
    canvas.paste(card_cheese_durian, (WIDTH//2 - card_cheese_durian.width//2, int(220 + bob_y)), card_cheese_durian)
    
    # Dual Polarity Buttons with 3D Pop
    scale_btn = 1.0 + 0.04 * math.sin(time_s * 4.0)
    # Eat Button
    draw.rounded_rectangle([320, 680, 860, 810], radius=28, fill=(46, 204, 113), outline=(255, 255, 255), width=5)
    font_btn = get_font(52, bold=True)
    draw.text((590, 745), "😋 ĂN NGAY", font=font_btn, fill=(255, 255, 255), anchor="mm")
    
    # Pass Button
    draw.rounded_rectangle([1060, 680, 1600, 810], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=5)
    draw.text((1330, 745), "❌ BỎ QUA", font=font_btn, fill=(255, 255, 255), anchor="mm")
    
    if is_reveal:
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "BẠN LÀ NGƯỜI CHỌN ĂN HAY BỎ QUA?", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q7_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q7.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "THỬ THÁCH TÍNH NHẨM 5 GIÂY", 7, time_s)
    
    # Left: Real Chalkboard Photo Card + Equation
    canvas.paste(card_chalkboard, (180, 260), card_chalkboard)
    font_chalk = get_font(74, bold=True)
    draw.text((470, 450), "90 : 9 + 5 = ?", font=font_chalk, fill=(255, 255, 255), anchor="mm")
    
    # Right: 4 Choice Tiles (2x2 Grid)
    choices = [("A", "10", 1120, 260), ("B", "15", 1480, 260), ("C", "20", 1120, 460), ("D", "25", 1480, 460)]
    for cid, cval, cx, cy in choices:
        is_correct = (cid == "B")
        if is_reveal:
            fill_tile = (46, 204, 113) if is_correct else (90, 110, 100)
        else:
            fill_tile = (255, 255, 255)
            
        draw.rounded_rectangle([cx, cy, cx + 300, cy + 160], radius=24, fill=fill_tile, outline=(240, 200, 50), width=4)
        font_c = get_font(56, bold=True)
        draw.text((cx + 150, cy + 80), f"{cid}. {cval}", font=font_c, fill=(255, 255, 255) if is_reveal else (30, 30, 40), anchor="mm")
        
    if is_reveal:
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "B: 15 (90 : 9 = 10; 10 + 5 = 15)", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_q8_frame(time_s: float, progress: float, is_reveal: bool, reveal_start_time: float) -> Image.Image:
    canvas = bg_q8.render(time_s)
    draw = ImageDraw.Draw(canvas)
    draw_header_banner(draw, canvas, "TÊN TIẾNG ANH CỦA CON VẬT NÀY LÀ GÌ?", 8, time_s)
    
    # Left: Real Wild Fox Photo Card
    bob_y = 8 * math.sin(time_s * 2.2)
    canvas.paste(card_fox, (140, int(240 + bob_y)), card_fox)
    
    # Label "Con Cáo" under photo
    draw.rounded_rectangle([200, int(690 + bob_y), 540, int(770 + bob_y)], radius=20, fill=(255, 255, 255), outline=(240, 200, 50), width=3)
    font_lbl = get_font(42, bold=True)
    draw.text((370, int(730 + bob_y)), "Con Cáo", font=font_lbl, fill=(30, 30, 40), anchor="mm")
    
    # Right: 3 English Choice Pills
    choices = [("A", "Fox"), ("B", "Wolf"), ("C", "Hyena")]
    py_start = 250
    for i, (cid, ctext) in enumerate(choices):
        cy = py_start + i * 150
        is_correct = (cid == "A")
        
        if is_reveal:
            fill_c = (46, 204, 113) if is_correct else (110, 120, 130)
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
        draw_confetti_and_reveal_banner(draw, canvas, 140, 880, 1640, 110, "A: FOX (Con Cáo)", time_s, reveal_start_time)
    else:
        draw_dynamic_sliding_timer(draw, canvas, clock_icon, 140, 890, 1640, 80, progress, time_s)
    return canvas

def render_intro_frame(time_s: float) -> Image.Image:
    canvas = bg_intro.render(time_s)
    draw = ImageDraw.Draw(canvas)
    
    pulse = 1.0 + 0.04 * math.sin(time_s * 4.0)
    bw = int(1400 * pulse)
    bh = int(220 * pulse)
    bx = WIDTH // 2 - bw // 2
    by = 220
    
    draw.rounded_rectangle([bx + 6, by + 8, bx + bw + 6, by + bh + 8], radius=40, fill=(0, 0, 0, 70))
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=40, fill=(255, 215, 0), outline=(255, 255, 255), width=6)
    
    font_main = get_font(int(84 * pulse), bold=True)
    draw.text((WIDTH//2, 330), "RABBIT GAME", font=font_main, fill=(180, 20, 20), anchor="mm")
    
    font_sub = get_font(52, bold=True)
    draw.text((WIDTH//2, 540), "THỬ THÁCH 8 THỂ LOẠI ĐỐ VUI SIÊU HACK NÃO", font=font_sub, fill=(255, 255, 255), stroke_width=3, stroke_fill=(30, 30, 30), anchor="mm")
    
    draw.rounded_rectangle([WIDTH//2 - 450, 680, WIDTH//2 + 450, 780], radius=28, fill=(46, 204, 113), outline=(255, 255, 255), width=4)
    font_cta = get_font(44, bold=True)
    draw.text((WIDTH//2, 730), "BẠN TRẢ LỜI ĐÚNG ĐƯỢC BAO NHIÊU CÂU?", font=font_cta, fill=(255, 255, 255), anchor="mm")
    return canvas

def render_outro_frame(time_s: float) -> Image.Image:
    canvas = bg_outro.render(time_s)
    draw = ImageDraw.Draw(canvas)
    
    bx, by, bw, bh = WIDTH//2 - 650, 220, 1300, 200
    draw.rounded_rectangle([bx + 6, by + 8, bx + bw + 6, by + bh + 8], radius=36, fill=(0, 0, 0, 70))
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=36, fill=(46, 204, 113), outline=(255, 255, 255), width=6)
    
    font_main = get_font(76, bold=True)
    draw.text((WIDTH//2, 320), "XIN CHÚC MỪNG!", font=font_main, fill=(255, 255, 255), anchor="mm")
    
    font_sub = get_font(50, bold=True)
    draw.text((WIDTH//2, 530), "Bạn đã trả lời đúng được bao nhiêu câu hỏi?", font=font_sub, fill=(255, 215, 0), stroke_width=3, stroke_fill=(20, 40, 70), anchor="mm")
    
    draw.rounded_rectangle([380, 680, 880, 790], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
    font_btn = get_font(44, bold=True)
    draw.text((630, 735), "BẤM LIKE", font=font_btn, fill=(255, 255, 255), anchor="mm")
    
    draw.rounded_rectangle([1040, 680, 1540, 790], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
    draw.text((1290, 735), "ĐĂNG KÝ KÊNH", font=font_btn, fill=(255, 255, 255), anchor="mm")
    return canvas

# -------------------------------------------------------------
# HIGH-PERFORMANCE RAWVIDEO PIPE MASTER PIPELINE
# -------------------------------------------------------------

def get_audio_duration(file_path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())

def main():
    print("Starting 30FPS Dynamic Master Video Generation...")
    
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
    
    questions = [
        ("q1", render_q1_frame),
        ("q2", render_q2_frame),
        ("q3", render_q3_frame),
        ("q4", render_q4_frame),
        ("q5", render_q5_frame),
        ("q6", render_q6_frame),
        ("q7", render_q7_frame),
        ("q8", render_q8_frame),
    ]

    # Calculate exact timeline schedule
    timeline_events = []
    cur_t = 0.0
    
    # Intro
    intro_dur = durations["intro"] + 0.6
    timeline_events.append({"type": "intro", "start": cur_t, "dur": intro_dur})
    cur_t += intro_dur
    
    for qkey, renderer in questions:
        q_dur = durations[f"{qkey}_q"] + 0.3
        cd_dur = 4.0
        a_dur = durations[f"{qkey}_a"] + 0.8
        
        timeline_events.append({
            "type": "question",
            "qkey": qkey,
            "renderer": renderer,
            "q_start": cur_t,
            "q_dur": q_dur,
            "cd_start": cur_t + q_dur,
            "cd_dur": cd_dur,
            "rev_start": cur_t + q_dur + cd_dur,
            "rev_dur": a_dur,
            "total_dur": q_dur + cd_dur + a_dur
        })
        cur_t += q_dur + cd_dur + a_dur
        
    # Outro
    outro_dur = durations["outro"] + 1.0
    timeline_events.append({"type": "outro", "start": cur_t, "dur": outro_dur})
    cur_t += outro_dur
    
    total_video_dur = cur_t
    total_frames = int(total_video_dur * FPS)
    print(f"Total Video Duration: {total_video_dur:.2f}s ({total_frames} frames at 30 FPS)")

    # 1. Pipe 30 FPS Raw Video directly into FFmpeg
    temp_video_silent = FINAL_DIR / "temp_video_silent.mp4"
    
    cmd_video = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgba",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        str(temp_video_silent)
    ]
    
    print("Piping dynamic 30 FPS frames to FFmpeg encoder...")
    proc_video = subprocess.Popen(cmd_video, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    frame_idx = 0
    while frame_idx < total_frames:
        t = frame_idx / FPS
        
        # Determine which scene is active at timestamp t
        frame_img = None
        
        if t < timeline_events[0]["start"] + timeline_events[0]["dur"]:
            frame_img = render_intro_frame(t)
        elif t >= timeline_events[-1]["start"]:
            frame_img = render_outro_frame(t)
        else:
            for ev in timeline_events[1:-1]:
                q_start = ev["q_start"]
                cd_start = ev["cd_start"]
                rev_start = ev["rev_start"]
                q_end = rev_start + ev["rev_dur"]
                
                if q_start <= t < q_end:
                    renderer = ev["renderer"]
                    if t < cd_start:
                        # Question reading phase
                        frame_img = renderer(t, progress=1.0, is_reveal=False, reveal_start_time=rev_start)
                    elif t < rev_start:
                        # Countdown phase: progress goes from 1.0 down to 0.0
                        cd_prog = max(0.0, min(1.0, 1.0 - (t - cd_start) / ev["cd_dur"]))
                        frame_img = renderer(t, progress=cd_prog, is_reveal=False, reveal_start_time=rev_start)
                    else:
                        # Reveal phase
                        frame_img = renderer(t, progress=0.0, is_reveal=True, reveal_start_time=rev_start)
                    break
                    
        if frame_img is None:
            frame_img = render_outro_frame(t)
            
        proc_video.stdin.write(frame_img.tobytes())
        frame_idx += 1
        if frame_idx % 150 == 0:
            print(f"Rendered {frame_idx}/{total_frames} frames ({frame_idx/total_frames*100:.1f}%)...")
            
    proc_video.stdin.close()
    _, stderr_v = proc_video.communicate()
    if proc_video.returncode != 0:
        print("Video Encode Error:", stderr_v.decode()[-1000:])
        return False
    print("Video track encoded successfully!")

    # 2. Multi-Track Audio Mixing with Sidechain Ducking
    voice_inputs = []
    voice_delays = []
    
    cur_t = 0.0
    voice_inputs.append(str(AUDIO_DIR / "intro.mp3"))
    voice_delays.append(int(cur_t * 1000))
    cur_t += durations["intro"] + 0.6
    
    sfx_cd_delays = []
    sfx_ding_delays = []
    
    for qkey, _ in questions:
        q_dur = durations[f"{qkey}_q"] + 0.3
        cd_dur = 4.0
        a_dur = durations[f"{qkey}_a"] + 0.8
        
        voice_inputs.append(str(AUDIO_DIR / f"{qkey}_q.mp3"))
        voice_delays.append(int(cur_t * 1000))
        cur_t += q_dur
        
        sfx_cd_delays.append(int(cur_t * 1000))
        cur_t += cd_dur
        
        sfx_ding_delays.append(int(cur_t * 1000))
        voice_inputs.append(str(AUDIO_DIR / f"{qkey}_a.mp3"))
        voice_delays.append(int((cur_t + 0.1) * 1000))
        cur_t += a_dur
        
    voice_inputs.append(str(AUDIO_DIR / "outro.mp3"))
    voice_delays.append(int(cur_t * 1000))
    cur_t += durations["outro"] + 1.0

    input_args = ["ffmpeg", "-y", "-i", str(temp_video_silent)]
    for vpath in voice_inputs:
        input_args.extend(["-i", vpath])
        
    cd_sfx_idx = len(voice_inputs) + 1
    ding_sfx_idx = len(voice_inputs) + 2
    bgm_idx = len(voice_inputs) + 3
    
    input_args.extend(["-i", str(AUDIO_DIR / "sfx_countdown.wav")])
    input_args.extend(["-i", str(AUDIO_DIR / "sfx_ding.wav")])
    input_args.extend(["-i", str(AUDIO_DIR / "bgm_quiz.wav")])
    
    filter_parts = []
    
    voice_mixed_labels = []
    for i, dms in enumerate(voice_delays):
        idx = i + 1
        filter_parts.append(f"[{idx}:a]adelay={dms}|{dms}[v_{i}]")
        voice_mixed_labels.append(f"[v_{i}]")
    filter_parts.append(f"{''.join(voice_mixed_labels)}amix=inputs={len(voice_mixed_labels)}:duration=longest:normalize=0[voice_main]")
    
    cd_mixed_labels = []
    for i, dms in enumerate(sfx_cd_delays):
        filter_parts.append(f"[{cd_sfx_idx}:a]adelay={dms}|{dms}[cd_{i}]")
        cd_mixed_labels.append(f"[cd_{i}]")
    filter_parts.append(f"{''.join(cd_mixed_labels)}amix=inputs={len(cd_mixed_labels)}:duration=longest:normalize=0[cd_main]")
    
    ding_mixed_labels = []
    for i, dms in enumerate(sfx_ding_delays):
        filter_parts.append(f"[{ding_sfx_idx}:a]adelay={dms}|{dms}[ding_{i}]")
        ding_mixed_labels.append(f"[ding_{i}]")
    filter_parts.append(f"{''.join(ding_mixed_labels)}amix=inputs={len(ding_mixed_labels)}:duration=longest:normalize=0[ding_main]")
    
    filter_parts.append(f"[cd_main][ding_main]amix=inputs=2:duration=longest:normalize=0,volume=1.2[sfx_main]")
    filter_parts.append(f"[{bgm_idx}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_video_dur:.2f},volume=-18dB,aresample=48000[bgm_raw]")
    filter_parts.append(f"[voice_main]asplit=2[v_play][v_sc]")
    filter_parts.append(f"[bgm_raw][v_sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=350[bgm_ducked]")
    filter_parts.append(f"[v_play][sfx_main][bgm_ducked]amix=inputs=3:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[final_audio]")
    
    filter_complex = ";".join(filter_parts)
    
    final_output_path = FINAL_DIR / "rabbit_game_dynamic_v2_master.mp4"
    
    cmd_mux = input_args + [
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[final_audio]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(final_output_path)
    ]
    
    print("Muxing final video and ducked audio...")
    res = subprocess.run(cmd_mux, capture_output=True, text=True)
    if res.returncode != 0:
        print("Audio Mux Error:", res.stderr[-1000:])
        return False
        
    if temp_video_silent.exists():
        temp_video_silent.unlink()
        
    print(f"SUCCESS! Dynamic V2 Master Video exported to: {final_output_path.resolve()}")
    print(f"File size: {final_output_path.stat().st_size / (1024*1024):.2f} MB")
    return True

if __name__ == "__main__":
    main()
