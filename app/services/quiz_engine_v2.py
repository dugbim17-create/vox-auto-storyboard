#!/usr/bin/env python3
"""
Quiz Video Engine 2.0 Enterprise Stack.
High-Performance, Multi-Format, Dual-Aspect (16:9 & 9:16) Automated Video Generator.
Supports:
1. Autonomous Script Generation via CLIProxy LLM (Gemini / GPT / Claude).
2. Autonomous AI Image / 3D Sticker Generation via CLIProxy Image (gpt-image-2 / gemini-3.1-flash-image).
3. Free / Royalty-Free Asset Fetching & Local Caching.
4. Production-grade 30FPS Gen Z Motion Compositor (Sunburst, Bokeh, Mascot Thỏ, Urgency Vibrations, Confetti).
5. EBU R128 Audio Normalization & Multi-Track Sidechain Ducking.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
from app.services.quiz_image_layout import image_slot, fitted_size

from app.config import _discover_cliproxy_api_key
from app.providers.base import ImageGenerationRequest
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.providers.llm.cliproxy import CliproxyLLMProvider

_FONT_CANDIDATES_BOLD = (
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/tahomabd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
_FONT_CANDIDATES_REGULAR = (
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def get_font(size: int, bold: bool = True):
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(name, size)
    except Exception:
        return ImageFont.load_default()


ICONS_3D_DIR = Path("assets/icons_3d")


def get_3d_icon(name: str, size: int = 48) -> Image.Image | None:
    p = ICONS_3D_DIR / f"{name}.png"
    if p.exists():
        try:
            im = Image.open(p).convert("RGBA")
            scale = size / max(im.width, im.height)
            return im.resize((int(im.width * scale), int(im.height * scale)), Image.Resampling.LANCZOS)
        except Exception:
            return None
    return None


def paste_icon_with_text(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    center_xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    icon_name: str,
    icon_size: int = 36,
    icon_side: str = "left",
    fill: tuple[int, int, int] = (255, 255, 255),
    gap: int = 12,
    stroke_color: tuple[int, int, int] | None = None,
    stroke_width: int = 0,
):
    """Pastes a 3D PNG icon cleanly next to text with balanced centering and zero tofu boxes."""
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
            draw.text(
                (text_x, cy),
                text,
                font=font,
                fill=fill,
                stroke_fill=stroke_color,
                stroke_width=stroke_width,
                anchor="lm",
            )
        elif icon_side == "right":
            total_w = tw + gap + iw
            start_x = cx - total_w // 2
            draw.text(
                (start_x, cy),
                text,
                font=font,
                fill=fill,
                stroke_fill=stroke_color,
                stroke_width=stroke_width,
                anchor="lm",
            )
            canvas.paste(icon, (start_x + tw + gap, cy - icon.height // 2), icon)
        elif icon_side == "both":
            total_w = iw + gap + tw + gap + iw
            start_x = cx - total_w // 2
            canvas.paste(icon, (start_x, cy - icon.height // 2), icon)
            draw.text(
                (start_x + iw + gap, cy),
                text,
                font=font,
                fill=fill,
                stroke_fill=stroke_color,
                stroke_width=stroke_width,
                anchor="lm",
            )
            canvas.paste(icon, (start_x + iw + gap + tw + gap, cy - icon.height // 2), icon)
    else:
        draw.text(
            (cx, cy),
            text,
            font=font,
            fill=fill,
            stroke_fill=stroke_color,
            stroke_width=stroke_width,
            anchor="mm",
        )


def draw_comic_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] = (255, 215, 0),
    stroke_color: tuple[int, int, int] = (20, 20, 25),
    stroke_width: int = 4,
    shadow_offset: tuple[int, int] = (3, 4),
    shadow_color: tuple[int, int, int] = (0, 0, 0),
    anchor: str = "mm",
):
    """Renders high-impact arcade/comic typography with hard drop shadow and thick outer stroke."""
    x, y = xy
    if shadow_offset and shadow_offset != (0, 0):
        sx, sy = shadow_offset
        draw.text(
            (x + sx, y + sy),
            text,
            font=font,
            fill=shadow_color,
            stroke_width=stroke_width,
            stroke_fill=shadow_color,
            anchor=anchor,
        )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_color,
        anchor=anchor,
    )


def get_difficulty_badge(q_idx: int, total_q: int = 10, lang: str = "vi") -> tuple[str, tuple[int, int, int]]:
    """Calculates scaling difficulty badge and theme color based on question position."""
    ratio = q_idx / max(1, total_q)
    if lang == "en":
        if ratio <= 0.35:
            return ("EASY", (46, 204, 113))
        elif ratio <= 0.70:
            return ("MEDIUM", (241, 196, 15))
        elif ratio <= 0.90:
            return ("HARD", (230, 126, 34))
        else:
            return ("GOD LEVEL", (231, 76, 60))
    else:
        if ratio <= 0.35:
            return ("DỄ (EASY)", (46, 204, 113))
        elif ratio <= 0.70:
            return ("TRUNG BÌNH (MED)", (241, 196, 15))
        elif ratio <= 0.90:
            return ("KHÓ (HARD)", (230, 126, 34))
        else:
            return ("BÁ ĐẠO (GOD)", (231, 76, 60))


# -------------------------------------------------------------
# 1. KNOWLEDGE BANK & REBUS DICTIONARY (VIETNAMESE)
# -------------------------------------------------------------

REBUS_BANK = {
    "emoji_rebus": [
        {
            "id": "er_01",
            "question": "ĐOÁN TỪ GHÉP QUA 2 HÌNH ẢNH QUEN THUỘC",
            "clues": [
                {"word": "ÁO", "image_prompt": "A bright yellow stylish raincoat hoodie, 3D cute cartoon sticker on pure white background", "color": (41, 128, 185)},
                {"word": "MƯA", "image_prompt": "Rainclouds with glowing blue raindrops falling, 3D cute cartoon sticker on pure white background", "color": (52, 152, 219)}
            ],
            "answer_text": "ÁO MƯA",
            "voice_q": "Câu số 1: Nhìn hai hình ảnh này bạn đoán được từ ghép quen thuộc nào không?",
            "voice_a": "Chính xác rồi! Đáp án đúng là Áo Mưa nha bạn ơi!",
        },
        {
            "id": "er_02",
            "question": "ĐOÁN TÊN LOÀI ĐỘNG VẬT QUEN THUỘC",
            "clues": [
                {"word": "BÒ", "image_prompt": "A cute dairy cow with black spots, 3D cartoon sticker on pure white background", "color": (230, 126, 34)},
                {"word": "SỮA", "image_prompt": "A fresh blue milk carton box, 3D cute cartoon sticker on pure white background", "color": (241, 196, 15)}
            ],
            "answer_text": "BÒ SỮA",
            "voice_q": "Câu đố tiếp theo: Đây là con vật quen thuộc nào vậy nhỉ?",
            "voice_a": "Chuẩn luôn bạn yêu! Đó chính là Bò Sữa.",
        },
        {
            "id": "er_03",
            "question": "MÔN THỂ THAO VUA ĐƯỢC NHẮC ĐẾN LÀ GÌ?",
            "clues": [
                {"word": "BÓNG", "image_prompt": "A vibrant orange basketball, 3D cartoon sticker on pure white background", "color": (231, 76, 60)},
                {"word": "RỔ", "image_prompt": "A woven wooden picnic basket, 3D cartoon sticker on pure white background", "color": (230, 126, 34)}
            ],
            "answer_text": "BÓNG RỔ",
            "voice_q": "Nhìn hai hình này bạn có đoán ra môn thể thao nào không?",
            "voice_a": "Quá chuẩn luôn! Đáp án là Bóng Rổ nha bạn!",
        },
        {
            "id": "er_04",
            "question": "VẬT DỤNG MÙA HÈ KHÔNG THỂ THIẾU CỦA PHÁI ĐẸP",
            "clues": [
                {"word": "KEM", "image_prompt": "A delicious pink ice cream cone, 3D cartoon sticker on pure white background", "color": (255, 105, 180)},
                {"word": "NẮNG", "image_prompt": "A shining smiling golden sun, 3D cartoon sticker on pure white background", "color": (241, 196, 15)}
            ],
            "answer_text": "KEM CHỐNG NẮNG",
            "voice_q": "Câu này hơi thử thách một chút, bạn hãy suy nghĩ xem nào!",
            "voice_a": "Xuất sắc! Đó chính là Kem Chống Nắng.",
        },
        {
            "id": "er_05",
            "question": "THỨC UỐNG YÊU THÍCH SỐ MỘT CỦA GIỚI TRẺ",
            "clues": [
                {"word": "TRÀ", "image_prompt": "Green tea cup with fresh tea leaves, 3D cartoon sticker on pure white background", "color": (46, 204, 113)},
                {"word": "SỮA", "image_prompt": "Fresh milk pouring into glass, 3D cartoon sticker on pure white background", "color": (241, 196, 15)}
            ],
            "answer_text": "TRÀ SỮA",
            "voice_q": "Đây là thức uống yêu thích nhất của rất nhiều bạn trẻ, bạn có biết không?",
            "voice_a": "Đúng luôn! Trà Sữa là câu trả lời chuẩn xác!",
        },
    ],
    "concept_rebus": [
        {
            "id": "cr_01",
            "question": "ĐÂY LÀ TRÒ CHƠI DÂN GIAN TRUYỀN THỐNG NÀO?",
            "clues": [
                {"word": "Ô", "image_prompt": "A colorful open umbrella, 3D cartoon sticker on white background", "color": (231, 76, 60)},
                {"word": "ĂN", "image_prompt": "A cute boy eating red apple, 3D cartoon sticker on white background", "color": (46, 204, 113)},
                {"word": "QUAN", "image_prompt": "An ancient mandarin official with feather fan, 3D sticker on white background", "color": (155, 89, 182)}
            ],
            "answer_text": "Ô ĂN QUAN",
            "voice_q": "Câu đố dân gian: Ghép 3 hình ảnh này thành một trò chơi truyền thống nổi tiếng nhé!",
            "voice_a": "Chuẩn luôn! Đó là trò chơi Ô Ăn Quan quen thuộc của tuổi thơ.",
        },
    ],
    "open_visual": [
        {
            "id": "ov_01",
            "question": "ĐÂY LÀ LOGO CỦA CÂU LẠC BỘ BÓNG ĐÁ NÀO?",
            "clues": [
                {"word": "BARCA", "image_prompt": "Official FC Barcelona crest emblem with golden outline on white background", "color": (39, 174, 96)}
            ],
            "answer_text": "FC BARCELONA",
            "voice_q": "Bạn có phải fan bóng đá không? Hãy nhận diện logo câu lạc bộ này nhé!",
            "voice_a": "Chính xác! Đó là câu lạc bộ lừng danh FC Barcelona của Tây Ban Nha.",
        },
    ],
    "dont_say_same": [
        {
            "id": "dss_01",
            "question": "KỂ TÊN MỘT MÔN HỌC TRONG TRƯỜNG (TRÙNG LÀ THUA!)",
            "clues": [
                {"word": "TOÁN", "image_prompt": "A modern colorful high school classroom with desks and blackboard", "color": (142, 68, 173)}
            ],
            "mystery_answer": "MÔN TOÁN",
            "answer_text": "MÔN TOÁN",
            "voice_q": "Thử thách đừng nói giống tôi! Kể tên một môn học, nói trùng với video là bị loại nha!",
            "voice_a": "Đáp án bí mật là Môn Toán! Ai vừa nói môn Toán là thua rồi nha!",
        },
    ],
    "multiple_choice": [
        {
            "id": "mc_01",
            "question": "Messi đã cùng đội tuyển nào nâng cao cúp vàng World Cup 2022?",
            "clues": [
                {"word": "MESSI", "image_prompt": "Lionel Messi lifting the World Cup golden trophy in Argentina jersey", "color": (44, 62, 80)}
            ],
            "choices": [("A", "Brazil"), ("B", "Argentina"), ("C", "Bồ Đào Nha")],
            "correct_id": "B",
            "answer_text": "B: ARGENTINA",
            "voice_q": "Messi đã cùng đội tuyển quốc gia nào vô địch World Cup 2022?",
            "voice_a": "Xuất sắc! Đáp án chính xác là B: Đội tuyển Argentina.",
        },
    ],
    "eat_or_pass": [
        {
            "id": "eop_01",
            "question": "SẦU RIÊNG NƯỚNG PHÔ MAI KÉO SỢI — BẠN ĂN HAY BỎ QUA?",
            "clues": [
                {"word": "SẦU RIÊNG", "image_prompt": "Appetizing roasted durian toast with melting golden cheese strings", "color": (230, 126, 34)}
            ],
            "answer_text": "BẠN ĐÃ CHỌN ĂN HAY BỎ QUA?",
            "voice_q": "Sầu riêng nướng phô mai béo ngậy thơm lừng — Bạn sẽ chọn Ăn hay Bỏ Qua?",
            "voice_a": "Bạn chọn Ăn hay Bỏ Qua? Hãy để lại bình luận cho chúng mình biết nhé!",
        },
    ],
    "fast_math": [
        {
            "id": "fm_01",
            "question": "90 : 9 + 5 = ?",
            "clues": [
                {"word": "TOÁN", "image_prompt": "A green chalkboard with chalk equation and cute professor owl", "color": (20, 90, 45)}
            ],
            "choices": [("A", "10"), ("B", "15"), ("C", "20"), ("D", "25")],
            "correct_id": "B",
            "answer_text": "B: 15",
            "voice_q": "Thử thách tính nhẩm 5 giây: 90 chia 9 cộng 5 bằng bao nhiêu?",
            "voice_a": "Đáp án chính xác là B: 15. Bạn tính có nhanh không nào?",
        },
    ],
    "vocab_flashcard": [
        {
            "id": "vf_01",
            "question": "TÊN TIẾNG ANH CỦA CON VẬT NÀY LÀ GÌ?",
            "clues": [
                {"word": "CON CÁO", "image_prompt": "A close up photo of cute wild red fox in natural winter forest", "color": (52, 73, 94)}
            ],
            "vn_label": "Con Cáo",
            "choices": [("A", "Fox"), ("B", "Wolf"), ("C", "Hyena")],
            "correct_id": "A",
            "answer_text": "A: FOX (Con Cáo)",
            "voice_q": "Con Cáo trong tiếng Anh được gọi là gì nhỉ?",
            "voice_a": "Chuẩn luôn! Con cáo trong tiếng Anh là Fox.",
        },
    ],
    "mystery_box": [
        {
            "id": "mb_01",
            "question": "CHỌN HỘP QUÀ BÍ ẨN: TEST NHÂN PHẨM TIẾT KIỆM CỦA BẠN!",
            "boxes": [
                {"id": "A", "color_name": "Xanh Lá", "reward": "+100 TRIỆU VNĐ", "tier": "jackpot", "color": (46, 204, 113)},
                {"id": "B", "color_name": "Đỏ Ruby", "reward": "NỢ 50 TRIỆU", "tier": "troll", "color": (231, 76, 60)},
                {"id": "C", "color_name": "Vàng Tươi", "reward": "+10 NGHÌN ĐỒNG", "tier": "normal", "color": (241, 196, 15)},
            ],
            "answer_text": "HỘP XANH: +100TR • HỘP ĐỎ: NỢ 50TR • HỘP VÀNG: +10K",
            "voice_q": "Thử thách test nhân phẩm! Bạn có 5 giây để chọn 1 trong 3 hộp quà Xanh, Đỏ hoặc Vàng!",
            "voice_a": "Hết giờ rồi mở quà thôi! Hộp Xanh cộng 100 triệu, Hộp Đỏ nợ 50 triệu, Hộp Vàng cộng 10 nghìn! Bạn trúng hộp nào hãy comment nhé!",
        }
    ],
    "missing_letters": [
        {
            "id": "ml_01",
            "question": "ĐOÁN TÊN QUỐC GIA QUA CÁC CHỮ CÒN THIẾU",
            "word_tiles": [
                [("N", True), ("H", False), ("Ậ", True), ("T", False)],
                [("B", True), ("Ả", False), ("N", True)]
            ],
            "answer_text": "NHẬT BẢN",
            "voice_q": "Câu đố chữ: Nhìn các ô chữ này, bạn có đoán được tên quốc gia nào không?",
            "voice_a": "Chính xác rồi! Đó chính là đất nước Nhật Bản xinh đẹp!",
        }
    ],
    "silhouette_shadow": [
        {
            "id": "ss_01",
            "question": "ĐOÁN TÊN CON VẬT QUA CHIẾC BÓNG BÍ ẨN",
            "silhouette_name": "HƯƠU CAO CỔ",
            "answer_text": "HƯƠU CAO CỔ",
            "voice_q": "Nhìn chiếc bóng đen bí ẩn này, bạn có đoán ra loài động vật nào có chiếc cổ siêu dài không?",
            "voice_a": "Chuẩn luôn bạn ơi! Chiếc bóng bí ẩn chính là Chú Hươu Cao Cổ!",
        }
    ],
    "this_or_that": [
        {
            "id": "tot_01",
            "question": "ĐẠI CHIẾN ẨM THỰC: BẠN CHỌN MÓN NÀO?",
            "side_a": {"name": "TRÀ SỮA TRÂN CHÂU", "action": "BẤM LIKE", "color": (46, 204, 113)},
            "side_b": {"name": "CÀ PHÊ SỮA ĐÁ", "action": "BÌNH LUẬN", "color": (230, 126, 34)},
            "answer_text": "TRÀ SỮA (LIKE) VS CÀ PHÊ (COMMENT)",
            "voice_q": "Đại chiến ẩm thực: Giữa Trà Sữa và Cà Phê, bạn chọn món nào? Chọn Trà Sữa bấm Like, chọn Cà Phê bình luận nhé!",
            "voice_a": "Món ruột của bạn là gì? Hãy bình luận lý do vì sao bạn mê món đó nhé!",
        }
    ],
    "anime_character": [
        {
            "id": "ac_01",
            "question": "ĐOÁN TÊN THUYỀN TRƯỞNG QUA 3 GỢI Ý BIỂU TƯỢNG (ONE PIECE)",
            "universe": "ONE PIECE",
            "clues": [
                {"word": "MŨ RƠM", "color": (241, 196, 15)},
                {"word": "THỊT ĐÙI", "color": (231, 76, 60)},
                {"word": "HẢI TẶC", "color": (41, 128, 185)},
            ],
            "choices": [("A", "Roronoa Zoro"), ("B", "Monkey D. Luffy"), ("C", "Vinsmoke Sanji")],
            "correct_id": "B",
            "answer_text": "B: MONKEY D. LUFFY",
            "reveal_image_path": "assets/anime_illustrations/luffy_cutout_clean.png",
            "progressive_unblur": True,
            "voice_q": "Thử thách nhìn ảnh mờ đoán nhân vật One Piece: Bức ảnh đang rõ dần, đố bạn đây là ai?",
            "voice_a": "Quá xuất sắc! Đó chính là Vua Hải Tặc tương lai Monkey D. Luffy!",
        },
        {
            "id": "ac_02",
            "question": "ĐOÁN TÊN KIẾM SĨ QUA 3 GỢI Ý BIỂU TƯỢNG (ONE PIECE)",
            "universe": "ONE PIECE",
            "clues": [
                {"word": "3 THANH KIẾM", "color": (142, 68, 173)},
                {"word": "TÓC XANH LÁ", "color": (46, 204, 113)},
                {"word": "RƯỢU SAKE", "color": (230, 126, 34)},
            ],
            "choices": [("A", "Roronoa Zoro"), ("B", "Trafalgar Law"), ("C", "Shanks Tóc Đỏ")],
            "correct_id": "A",
            "answer_text": "A: RORONOA ZORO",
            "reveal_image_path": "assets/anime_illustrations/zoro_cutout_clean.png",
            "voice_q": "Ba thanh kiếm sắc bén, mái tóc xanh lá và bình rượu sake, đây là kiếm sĩ trứ danh nào?",
            "voice_a": "Chuẩn luôn bạn ơi! Đó chính là kiếm sĩ đệ nhất Roronoa Zoro!",
        },
        {
            "id": "ac_03",
            "question": "ĐOÁN TÊN NHÂN VẬT QUA BẢO BỐI & SỞ THÍCH (DORAEMON)",
            "universe": "DORAEMON",
            "clues": [
                {"word": "CHUÔNG VÀNG", "color": (241, 196, 15)},
                {"word": "BÁNH RÁN", "color": (230, 126, 34)},
                {"word": "TÚI THẦN KỲ", "color": (41, 128, 185)},
            ],
            "choices": [("A", "Nobi Nobita"), ("B", "Dorami"), ("C", "Doraemon")],
            "correct_id": "C",
            "answer_text": "C: DORAEMON",
            "voice_q": "Chiếc chuông vàng cổ, đĩa bánh rán thơm lừng và túi thần kỳ trước bụng, đây là nhân vật tuổi thơ nào vậy nhỉ?",
            "voice_a": "Chính xác rồi! Chú mèo máy thông minh đến từ tương lai Doraemon!",
        },
        {
            "id": "ac_04",
            "question": "ĐOÁN TÊN CẬU BÉ HẬU ĐẬU TRONG DORAEMON",
            "universe": "DORAEMON",
            "clues": [
                {"word": "KÍNH TRÒN TO", "color": (52, 73, 94)},
                {"word": "ĐIỂM 0 TRÒN TRĨNH", "color": (231, 76, 60)},
                {"word": "KHÓC NHÈ", "color": (41, 128, 185)},
            ],
            "choices": [("A", "Nobi Nobita"), ("B", "Honekawa Suneo"), ("C", "Goda Takeshi")],
            "correct_id": "A",
            "answer_text": "A: NOBI NOBITA",
            "voice_q": "Cặp kính tròn to đùng, bài kiểm tra bị điểm không và hay khóc nhè tìm Doraemon cầu cứu, đây là ai?",
            "voice_a": "Đúng luôn bạn yêu! Đó chính là cậu bạn hậu đậu Nobi Nobita!",
        },
        {
            "id": "ac_05",
            "question": "ĐOÁN TÊN THÁM TỬ NHÍ QUA PHỤ KIỆN (CONAN)",
            "universe": "CONAN",
            "clues": [
                {"word": "KÍNH ĐỊNH VỊ", "color": (52, 73, 94)},
                {"word": "VÁN TRƯỢT SIÊU TỐC", "color": (230, 126, 34)},
                {"word": "NƠ ĐỔI GIỌNG NÓI", "color": (231, 76, 60)},
            ],
            "choices": [("A", "Kaito Kid"), ("B", "Edogawa Conan"), ("C", "Hattori Heiji")],
            "correct_id": "B",
            "answer_text": "B: EDOGAWA CONAN",
            "voice_q": "Chiếc kính định vị mục tiêu, ván trượt năng lượng mặt trời và chiếc nơ cổ nơ đổi giọng, đây là thám tử nào?",
            "voice_a": "Xuất sắc! Đó chính là thám tử lừng danh Edogawa Conan!",
        },
    ],
}


# -------------------------------------------------------------
# 2. AI SCRIPT GENERATOR VIA CLIPROXY LLM
# -------------------------------------------------------------

async def generate_ai_quiz_script(topic: str, count: int = 5, archetype: str = "emoji_rebus", model: str = "gemini-3.6-flash-high") -> list[dict[str, Any]]:
    """Calls CLIProxy LLM to autonomously generate creative Vietnamese quiz units."""
    key = _discover_cliproxy_api_key()
    provider = CliproxyLLMProvider(api_key=key, model=model)
    
    system_prompt = (
        "Bạn là giám đốc sản xuất nội dung cho kênh YouTube giải đố triệu view Rabbit Game. "
        "Hãy tạo danh sách các câu đố tiếng Việt siêu hấp dẫn, vui tươi, lôi cuốn khán giả trẻ dưới 20 tuổi."
    )
    user_prompt = f"Tạo {count} câu đố thể loại '{archetype}' về chủ đề: '{topic}'. Mỗi câu có 2 hoặc 3 từ khóa (clues) ghép thành đáp án có nghĩa."
    
    schema = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "clues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "word": {"type": "string"},
                                    "image_prompt": {"type": "string"},
                                    "color_hex": {"type": "string"}
                                },
                                "required": ["word", "image_prompt"]
                            }
                        },
                        "answer_text": {"type": "string"},
                        "voice_q": {"type": "string"},
                        "voice_a": {"type": "string"}
                    },
                    "required": ["question", "clues", "answer_text", "voice_q", "voice_a"]
                }
            }
        },
        "required": ["questions"]
    }
    
    try:
        res = await provider.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=schema,
            temperature=0.7,
            request_id=f"quiz_gen_{random.randint(1000, 9999)}"
        )
        questions = res.get("questions", [])
        # Assign colors & IDs
        color_palette = [(41, 128, 185), (52, 152, 219), (46, 204, 113), (230, 126, 34), (231, 76, 60), (155, 89, 182), (241, 196, 15)]
        for i, q in enumerate(questions, 1):
            q["id"] = f"ai_q_{i:02d}"
            for ci, c in enumerate(q.get("clues", [])):
                c["color"] = color_palette[(i + ci) % len(color_palette)]
        return questions
    except Exception as e:
        logger.warning(f"AI Script Gen failed: {e}")
        raise RuntimeError(f"AI Script Generation failed: {e}") from e


# -------------------------------------------------------------
# 3. AI IMAGE GENERATION & ASSET FETCHING VIA CLIPROXY
# -------------------------------------------------------------

async def generate_ai_image_asset(prompt: str, output_path: Path, model: str = "gpt-image-2") -> Path:
    """Generates high quality 3D sticker assets using CLIProxy gpt-image-2."""
    if output_path.exists() and output_path.stat().st_size > 5000:
        return output_path
        
    key = _discover_cliproxy_api_key()
    provider = CliproxyImageProvider(api_key=key, model=model)
    req = ImageGenerationRequest(
        prompt=f"{prompt}, high resolution 3D glossy sticker, die-cut white outline, isolated on pure white background, cute game asset",
        role="subject",
        output_path=str(output_path),
        candidate_count=1
    )
    try:
        await provider.generate(req)
        # Apply die-cut outline to transparent cutout
        with Image.open(output_path) as raw:
            cutout = apply_diecut_outline(raw.convert("RGBA"), outline_px=8)
            cutout.save(output_path)
        print(f"AI Image Generated: {output_path.name}")
    except Exception as e:
        logger.error(f"AI Image Generation failed for {prompt}: {e}")
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"AI Image Generation failed for {prompt}: {e}") from e
    return output_path


# -------------------------------------------------------------
# 4. PROCEDURAL GRAPHICS, STICKERS & MASCOT ENGINE
# -------------------------------------------------------------

def apply_diecut_outline(img: Image.Image, outline_px: int = 8, outline_color=(255, 255, 255, 255)) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[-1]
    expanded_mask = alpha.filter(ImageFilter.MaxFilter(outline_px * 2 + 1))
    
    border_layer = Image.new("RGBA", img.size, outline_color)
    border_layer.putalpha(expanded_mask)
    
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 80))
    shadow_mask = expanded_mask.filter(ImageFilter.GaussianBlur(outline_px // 2 + 1))
    shadow_layer.putalpha(shadow_mask)
    
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(shadow_layer, (4, 6), shadow_layer)
    out.paste(border_layer, (0, 0), border_layer)
    out.paste(img, (0, 0), img)
    return out


def draw_rabbit_mascot(size: int = 240, state: str = "WELCOME", time_s: float = 0.0) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    
    ear_wobble = 6 * math.sin(time_s * 4.0)
    draw.ellipse((size*0.22 + ear_wobble, size*0.04, size*0.42 + ear_wobble, size*0.48), fill=(255, 255, 255), outline=(40, 40, 40), width=4)
    draw.ellipse((size*0.27 + ear_wobble, size*0.12, size*0.37 + ear_wobble, size*0.40), fill=(255, 182, 193))
    draw.ellipse((size*0.58 - ear_wobble, size*0.04, size*0.78 - ear_wobble, size*0.48), fill=(255, 255, 255), outline=(40, 40, 40), width=4)
    draw.ellipse((size*0.63 - ear_wobble, size*0.12, size*0.73 - ear_wobble, size*0.40), fill=(255, 182, 193))
    
    draw.ellipse((size*0.18, size*0.32, size*0.82, size*0.88), fill=(255, 255, 255), outline=(40, 40, 40), width=5)
    draw.ellipse((size*0.22, size*0.60, size*0.36, size*0.72), fill=(255, 192, 203, 180))
    draw.ellipse((size*0.64, size*0.60, size*0.78, size*0.72), fill=(255, 192, 203, 180))
    
    if state == "THINKING":
        draw.ellipse((size*0.32, size*0.46, size*0.44, size*0.58), fill=(30, 30, 30))
        draw.ellipse((size*0.56, size*0.46, size*0.68, size*0.58), fill=(30, 30, 30))
        draw.ellipse((size*0.38, size*0.48, size*0.43, size*0.53), fill=(255, 255, 255))
        draw.ellipse((size*0.62, size*0.48, size*0.67, size*0.53), fill=(255, 255, 255))
        draw.ellipse((size*0.47, size*0.68, size*0.53, size*0.76), fill=(40, 40, 40))
    elif state == "CELEBRATE":
        draw.arc((size*0.30, size*0.44, size*0.46, size*0.58), 180, 360, fill=(30, 30, 30), width=5)
        draw.arc((size*0.54, size*0.44, size*0.70, size*0.58), 180, 360, fill=(30, 30, 30), width=5)
        draw.pieslice((size*0.40, size*0.62, size*0.60, size*0.82), 0, 180, fill=(231, 76, 60), outline=(40, 40, 40), width=3)
        draw.pieslice((size*0.44, size*0.70, size*0.56, size*0.82), 0, 180, fill=(255, 182, 193))
    else:  # WELCOME
        draw.ellipse((size*0.30, size*0.46, size*0.44, size*0.60), fill=(30, 30, 30))
        draw.ellipse((size*0.56, size*0.46, size*0.70, size*0.60), fill=(30, 30, 30))
        draw.ellipse((size*0.33, size*0.48, size*0.39, size*0.54), fill=(255, 255, 255))
        draw.ellipse((size*0.59, size*0.48, size*0.65, size*0.54), fill=(255, 255, 255))
        draw.arc((size*0.40, size*0.62, size*0.50, size*0.72), 0, 180, fill=(40, 40, 40), width=4)
        draw.arc((size*0.50, size*0.62, size*0.60, size*0.72), 0, 180, fill=(40, 40, 40), width=4)
        
    draw.polygon([(size*0.47, size*0.58), (size*0.53, size*0.58), (size*0.50, size*0.63)], fill=(255, 105, 180))
    return apply_diecut_outline(im, outline_px=6)


def create_alarm_clock_icon(size: int = 80) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
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


# -------------------------------------------------------------
# 5. DYNAMIC 30FPS BACKGROUND COMPOSITOR
# -------------------------------------------------------------

class DynamicBackgroundCompositor:
    def __init__(self, w: int, h: int, top_color=(235, 110, 30), bottom_color=(190, 60, 10), ray_color=(255, 255, 255, 22), num_rays=20, num_particles=24, custom_image_path: str | Path | None = None, blur_bg: bool = True):
        self.w = w
        self.h = h
        self.top_color = top_color
        self.bottom_color = bottom_color
        self.ray_color = ray_color
        self.num_rays = num_rays
        self.num_particles = num_particles
        self.custom_bg = None
        
        if custom_image_path and Path(custom_image_path).exists():
            try:
                raw_bg = Image.open(custom_image_path).convert("RGBA")
                # Scale & Crop to fill w, h
                scale = max(w / raw_bg.width, h / raw_bg.height)
                nw, nh = int(raw_bg.width * scale), int(raw_bg.height * scale)
                scaled_bg = raw_bg.resize((nw, nh), Image.Resampling.LANCZOS)
                # Center crop
                cx, cy = (nw - w) // 2, (nh - h) // 2
                cropped_bg = scaled_bg.crop((cx, cy, cx + w, cy + h))
                
                # Apply subtle blur and dark vignette for optimal text readability
                if blur_bg:
                    cropped_bg = cropped_bg.filter(ImageFilter.GaussianBlur(radius=3))
                # Add dark/colored overlay
                tint_layer = Image.new("RGBA", (w, h), (15, 20, 30, 85))
                self.custom_bg = Image.alpha_composite(cropped_bg, tint_layer)
            except Exception as e:
                print(f"Error loading custom background: {e}")
                self.custom_bg = None
        
        random.seed(42)
        self.particles = []
        for _ in range(num_particles):
            self.particles.append({
                "x": random.uniform(30, w - 30),
                "y": random.uniform(30, h - 30),
                "speed": random.uniform(25, 75),
                "size": random.uniform(6, 18),
                "wobble_speed": random.uniform(1.5, 3.5),
                "wobble_amp": random.uniform(10, 20),
                "phase": random.uniform(0, math.pi * 2),
                "opacity": random.randint(30, 85)
            })

        self.base_gradient = Image.new("RGBA", (self.w, self.h))
        draw_g = ImageDraw.Draw(self.base_gradient)
        for y in range(self.h):
            ratio = y / max(1, self.h - 1)
            r = int(self.top_color[0] * (1 - ratio) + self.bottom_color[0] * ratio)
            g = int(self.top_color[1] * (1 - ratio) + self.bottom_color[1] * ratio)
            b = int(self.top_color[2] * (1 - ratio) + self.bottom_color[2] * ratio)
            draw_g.line([(0, y), (self.w, y)], fill=(r, g, b, 255))

        # Pre-render 60-frame seamless loop for 5.7x render throughput speedup
        self._cached_loop: list[Image.Image] = [self._render_raw_frame(f / 30.0) for f in range(60)]

    def _render_raw_frame(self, time_s: float) -> Image.Image:
        if self.custom_bg is not None:
            base = self.custom_bg.copy()
        else:
            base = self.base_gradient.copy()
            
        cx, cy = self.w // 2, self.h // 2
        diag = math.sqrt(self.w**2 + self.h**2)
        ray_layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw_rays = ImageDraw.Draw(ray_layer)
        
        slice_angle = (2 * math.pi) / self.num_rays
        angle_offset = time_s * ((2 * slice_angle) / 2.0)
        for i in range(0, self.num_rays, 2):
            a1 = angle_offset + i * slice_angle
            a2 = angle_offset + (i + 1) * slice_angle
            p1 = (cx, cy)
            p2 = (cx + diag * math.cos(a1), cy + diag * math.sin(a1))
            p3 = (cx + diag * math.cos(a2), cy + diag * math.sin(a2))
            draw_rays.polygon([p1, p2, p3], fill=self.ray_color)
            
        base = Image.alpha_composite(base, ray_layer)
        
        part_layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw_part = ImageDraw.Draw(part_layer)
        for p in self.particles:
            curr_y = (p["y"] - time_s * p["speed"]) % self.h
            curr_x = (p["x"] + math.sin(time_s * p["wobble_speed"] + p["phase"]) * p["wobble_amp"]) % self.w
            r = p["size"]
            col = (255, 255, 255, p["opacity"])
            draw_part.ellipse((curr_x - r, curr_y - r, curr_x + r, curr_y + r), fill=col)
            draw_part.ellipse((curr_x - r*0.4, curr_y - r*0.4, curr_x + r*0.4, curr_y + r*0.4), fill=(255, 255, 255, min(255, p["opacity"]*2)))
            
        return Image.alpha_composite(base, part_layer)

    def render(self, time_s: float) -> Image.Image:
        idx = int(round(time_s * 30.0)) % len(self._cached_loop)
        return self._cached_loop[idx].copy()


# -------------------------------------------------------------
# 6. DUAL-ASPECT RENDER PIPELINE (16:9 & 9:16)
# -------------------------------------------------------------

@dataclass
class QuizRenderOptions:
    channel_profile: str = ""
    visual_style: dict[str, Any] | None = None
    aspect_ratio: str = "16:9"  # "16:9" or "9:16"
    fps: int = 30
    tts_engine: str = "vieneu"  # "vieneu", "piper", or "edge"
    vieneu_voice: str = "Ngọc Huyền"  # "Ngọc Huyền", "Thanh Bình", "Trúc Ly", "Minh Đức", "Đoan Trang"
    vieneu_speed: float = 1.05
    piper_voice: str = "minh_khang"  # "minh_khang", "ngoc_huyen_moi", "ngocngan3701", "manh_dung", "nguyet_nga"
    piper_model_dir: Path = Path("D:/ALL AI/TestProjects/Voice/assets/models/piper")
    piper_exe: Path = Path("D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe")
    piper_speed: float = 1.05
    voice_name: str = "vi-VN-HoaiMyNeural"
    mascot_type: str = "loc"  # "loc", "my", or "rabbit"
    bg_image: Path | str | None = None  # Path to custom image background (e.g. Anime island / Wano / Harbor)
    bg_video: Path | str | None = None  # Path to motion background video loop (MP4)
    bg_theme: str = "auto"  # "auto", "orange", "blue", "purple", "forest", "dark_gold"
    output_path: Path = Path("output/quiz_output.mp4")
    pacing: str = "standard"  # "standard" (3.5s/4s) or "fast" (3.0s viral cd)
    archetype: str = "classic"  # "classic" or "riddle_mystra" (QuizMystra style)
    countdown_seconds: float = 3.5
    image_model: str = "gpt-image-2"
    language: str = "auto"  # "auto", "en", or "vi"
    bgm_path: Path | str | None = None  # Path to custom studio BGM track


class QuizVideoEngineV2:
    @property
    def is_english(self) -> bool:
        if self.opt.language == "en":
            return True
        if self.opt.language == "vi":
            return False
        voice = str(self.opt.piper_voice or self.opt.voice_name or "").lower()
        return voice.startswith("en_") or "en-" in voice or "english" in voice

    def __init__(self, options: QuizRenderOptions | None = None):
        self.opt = options or QuizRenderOptions()
        if self.opt.visual_style is not None:
            from app.services.quiz_style_packs import resolve_style_snapshot
            style = self.opt.visual_style
            self.opt.visual_style = resolve_style_snapshot(
                str(style.get("id")),
                locale=str(style.get("locale") or self.opt.language or "en-US"),
                motion=str(style.get("motion") or "medium"),
                mascot=style.get("mascot", False),
                snapshot_override=style.get("snapshot"),
                version=style.get("version"),
            )
        if self.opt.channel_profile:
            from app.services.quiz_channel_profiles import get_profile
            profile = get_profile(self.opt.channel_profile)
            self.opt.language = profile["locale"]
            self.opt.bg_theme = profile["theme"]
            self.opt.countdown_seconds = profile["timer"]
        if self.opt.aspect_ratio == "9:16":
            self.width, self.height = 1080, 1920
        else:
            self.width, self.height = 1920, 1080
            
        self.clock_icon = create_alarm_clock_icon(72 if self.opt.aspect_ratio == "9:16" else 84)
        
        # Load Mascot: Hoạt Hình Voxel Mascot (Lộc / Mỵ) or Classic Rabbit
        loc_cutout_p = Path("assets/mascots_hoat_hinh/loc_host_raw_cutout.png")
        my_cutout_p = Path("assets/mascots_hoat_hinh/my_host_raw_cutout.png")
        
        target_h = 360 if self.opt.aspect_ratio == "16:9" else 300
        if self.opt.mascot_type == "loc" and loc_cutout_p.exists():
            raw_m = Image.open(loc_cutout_p).convert("RGBA")
            scale = target_h / max(1, raw_m.height)
            m_scaled = raw_m.resize((int(raw_m.width * scale), target_h), Image.Resampling.LANCZOS)
            m_diecut = apply_diecut_outline(m_scaled, outline_px=6)
            self.mascots = {
                "WELCOME": m_diecut,
                "THINKING": m_diecut,
                "CELEBRATE": m_diecut,
            }
        elif self.opt.mascot_type == "my" and my_cutout_p.exists():
            raw_m = Image.open(my_cutout_p).convert("RGBA")
            scale = target_h / max(1, raw_m.height)
            m_scaled = raw_m.resize((int(raw_m.width * scale), target_h), Image.Resampling.LANCZOS)
            m_diecut = apply_diecut_outline(m_scaled, outline_px=6)
            self.mascots = {
                "WELCOME": m_diecut,
                "THINKING": m_diecut,
                "CELEBRATE": m_diecut,
            }
        else:
            mascot_s = 220 if self.opt.aspect_ratio == "16:9" else 200
            self.mascots = {
                "WELCOME": draw_rabbit_mascot(mascot_s, state="WELCOME", time_s=0.0),
                "THINKING": draw_rabbit_mascot(mascot_s, state="THINKING", time_s=0.0),
                "CELEBRATE": draw_rabbit_mascot(mascot_s, state="CELEBRATE", time_s=0.0),
            }

    def render_quiz_video(self, question_units: list[dict[str, Any]], title: str = "RABBIT GAME") -> Path:
        out_dir = self.opt.output_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_dir = out_dir / "audio_cache"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[{self.opt.aspect_ratio}] Starting Video Render ({len(question_units)} questions, {self.width}x{self.height})...")
        
        voice_files = self._synthesize_voice_tracks(question_units, audio_dir)
        sfx_files = self._synthesize_procedural_audio(audio_dir)
        
        temp_silent = out_dir / f"temp_{self.opt.aspect_ratio.replace(':', '_')}.mp4"
        total_dur, timeline_events = self._pipe_frames_to_ffmpeg(question_units, voice_files, temp_silent)
        
        final_mp4 = self.opt.output_path
        self._mux_audio_and_video(temp_silent, voice_files, sfx_files, total_dur, timeline_events, final_mp4)
        
        if temp_silent.exists():
            temp_silent.unlink()
            
        print(f"[{self.opt.aspect_ratio}] Finished! Saved to: {final_mp4.resolve()} ({final_mp4.stat().st_size / (1024*1024):.2f} MB)")
        return final_mp4

    def _synthesize_voice_tracks(self, units: list[dict[str, Any]], audio_dir: Path) -> dict[str, Path]:
        if self.opt.channel_profile:
            from app.services.quiz_channel_profiles import get_profile, require_voice, labels
            require_voice(self.opt.channel_profile, self.opt.piper_voice, self.opt.piper_model_dir)
            from copy import deepcopy
            units = deepcopy(units)
            profile = get_profile(self.opt.channel_profile)
            if units:
                units[0].setdefault("intro_text", profile["hook"])
                units[-1].setdefault("outro_text", profile["cta"])
            for q in units:
                q.setdefault("voice_a", labels(self.opt.channel_profile)["answer"] + ": " + str(q.get("answer_text") or q.get("correct_id") or q.get("correct_option")))
        tracks = {}
        self.tts_calls = 0
        self.tts_cache_hits = 0
        identity = {"engine": self.opt.tts_engine, "language": self.opt.language,
                    "voice": self.opt.piper_voice if self.opt.tts_engine == "piper" else self.opt.vieneu_voice if self.opt.tts_engine == "vieneu" else self.opt.voice_name,
                    "speed": self.opt.piper_speed if self.opt.tts_engine == "piper" else self.opt.vieneu_speed}
        if self.opt.tts_engine == "piper":
            model_path = Path(self.opt.piper_model_dir) / f"{self.opt.piper_voice}.onnx"
            if not model_path.is_file():
                raise RuntimeError(f"Selected Piper model missing: {model_path}; no voice fallback allowed")
            with model_path.open("rb") as stream:
                identity["model_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
            config_path = model_path.with_suffix(".onnx.json")
            identity["config_sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest() if config_path.is_file() else "missing"

        def fingerprint(text):
            return hashlib.sha256(json.dumps({"text": " ".join(text.split()), **identity}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]

        def valid_audio(path):
            try:
                if path.suffix == ".wav":
                    with wave.open(str(path), "rb") as stream:
                        count = stream.getnframes()
                        expected = count * stream.getnchannels() * stream.getsampwidth()
                        return count > 0 and len(stream.readframes(count)) == expected
                return self._probe_dur(path) > 0
            except (OSError, EOFError, wave.Error, RuntimeError):
                return False
        ext = ".wav" if self.opt.tts_engine in {"piper", "vieneu"} else ".mp3"
        
        default_intro = (
            f"Welcome to the {self.opt.archetype} challenge! Can you get all {len(units)} questions right? Let's go!"
            if self.is_english
            else f"Chào mừng các bạn đến với thử thách đố vui! Cùng thử tài với {len(units)} câu hỏi ngay nào!"
        )
        intro_text = (units[0].get("intro_text") if units and isinstance(units[0], dict) else None) or default_intro
        intro_hash = fingerprint(intro_text)
        intro_p = audio_dir / f"intro_{intro_hash}{ext}"
        
        tts_jobs = []
        if not valid_audio(intro_p):
            tts_jobs.append((intro_text, intro_p))
        tracks["intro"] = intro_p
        
        for i, q in enumerate(units, 1):
            qid = str(q.get("id") or f"q{i}")
            q_text = q.get("voice_q") or q.get("question") or ""
            default_ans = f"The correct answer is {q.get('answer_text', '')}!" if self.is_english else f"Đáp án là {q.get('answer_text', '')} nha!"
            a_text = q.get("voice_a") or default_ans
            
            q_hash = fingerprint(q_text)
            a_hash = fingerprint(a_text)
            
            qp = audio_dir / f"{qid}_q_{q_hash}{ext}"
            ap = audio_dir / f"{qid}_a_{a_hash}{ext}"
            
            if not valid_audio(qp):
                tts_jobs.append((q_text, qp))
            if not valid_audio(ap):
                tts_jobs.append((a_text, ap))
            tracks[f"q{i}_q"] = qp
            tracks[f"q{i}_a"] = ap
            
        default_outro = (
            "Time is up! How many questions did you answer correctly? Comment below, and make sure to like and subscribe!"
            if self.is_english
            else "Thời gian đã hết! Bạn đã trả lời đúng bao nhiêu câu? Hãy like và đăng ký kênh nhé!"
        )
        outro_text = (units[-1].get("outro_text") if units and isinstance(units[-1], dict) else None) or default_outro
        outro_hash = fingerprint(outro_text)
        outro_p = audio_dir / f"outro_{outro_hash}{ext}"
        
        if not valid_audio(outro_p):
            tts_jobs.append((outro_text, outro_p))
        tracks["outro"] = outro_p
        self.tts_cache_hits = len(tracks) - len(tts_jobs)
        
        if tts_jobs:
            if self.opt.tts_engine == "vieneu":
                import sys
                voice_backend = Path("D:/ALL AI/TestProjects/Voice/backend")
                if str(voice_backend) not in sys.path:
                    sys.path.insert(0, str(voice_backend))
                from engines.vieneu_engine import synthesize_vieneu
                print(f"[VieNeu TTS] Synthesizing {len(tts_jobs)} speech clips using voice: {self.opt.vieneu_voice}...")
                for text, path in tts_jobs:
                    clean_txt = " ".join(text.split())
                    try:
                        self.tts_calls += 1
                        synthesize_vieneu(
                            text=clean_txt,
                            output_path=path,
                            voice_id=self.opt.vieneu_voice,
                            speed=self.opt.vieneu_speed
                        )
                    except Exception as e:
                        print(f"VieNeu TTS error for {path.name}: {e}")
            elif self.opt.tts_engine == "piper":
                model_path = self.opt.piper_model_dir / f"{self.opt.piper_voice}.onnx"
                if not model_path.exists():
                    raise RuntimeError(f"Selected Piper model missing: {model_path}")
                
                length_scale = round(1.0 / max(0.25, min(3.0, self.opt.piper_speed)), 3)
                env = os.environ.copy()
                env["PYTHONUTF8"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                
                print(f"[Piper TTS] Synthesizing {len(tts_jobs)} speech clips using voice: {self.opt.piper_voice}...")
                for text, path in tts_jobs:
                    clean_txt = " ".join(text.split())
                    cmd = [
                        str(self.opt.piper_exe),
                        "--model", str(model_path),
                        "--output_file", str(path),
                        "--length-scale", str(length_scale)
                    ]
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)
                    self.tts_calls += 1
                    try:
                        stdout, stderr = p.communicate(input=clean_txt, timeout=120)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.communicate()
                        path.unlink(missing_ok=True)
                        raise RuntimeError(f"Piper timeout: {path.name}")
                    if p.returncode != 0:
                        path.unlink(missing_ok=True)
                        raise RuntimeError(f"Piper TTS failed: {stderr[-500:]}")
            else:
                import edge_tts
                async def run_all_tts():
                    async def run_one(text, path):
                        try:
                            comm = edge_tts.Communicate(text, voice=self.opt.voice_name)
                            self.tts_calls += 1
                            await comm.save(str(path))
                        except Exception as e:
                            print(f"TTS error for {path.name}: {e}")
                    tasks = [run_one(text, path) for text, path in tts_jobs]
                    if tasks:
                        await asyncio.gather(*tasks)

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            pool.submit(lambda: asyncio.run(run_all_tts())).result()
                    else:
                        loop.run_until_complete(run_all_tts())
                except Exception:
                    asyncio.run(run_all_tts())
                    
        # Safeguard: ensure every required audio track exists and is valid
        missing = [track_name for track_name, track_path in tracks.items() if not valid_audio(track_path)]
        if missing:
            raise RuntimeError(f"TTS audio synthesis failed for tracks: {missing}. Production video render cannot proceed with missing speech.")

        return tracks

    def _synthesize_procedural_audio(self, audio_dir: Path) -> dict[str, Path]:
        sr = 48000
        def write_wav(path, data):
            data = np.clip(data, -1.0, 1.0)
            int_data = (data * 32767).astype(np.int16)
            with wave.open(str(path), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sr)
                f.writeframes(int_data.tobytes())

        p_ding = audio_dir / "sfx_ding.wav"
        if not p_ding.exists():
            dur = 2.0
            t = np.linspace(0, dur, int(sr * dur), endpoint=False)
            ding = 0.45 * np.sin(2 * np.pi * 1046.5 * t) * np.exp(-t * 3.5) + \
                   0.35 * np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 4.0) + \
                   0.30 * np.sin(2 * np.pi * 1568.0 * t) * np.exp(-t * 4.5)
            write_wav(p_ding, ding)

        p_cd = audio_dir / "sfx_countdown.wav"
        if not p_cd.exists():
            dur_cd = 4.5
            t_cd = np.linspace(0, dur_cd, int(sr * dur_cd), endpoint=False)
            ticks = np.zeros_like(t_cd)
            cur_t = 0.0
            interval = 0.5
            while cur_t < dur_cd:
                idx = int(cur_t * sr)
                click_dur = int(0.045 * sr)
                if idx + click_dur < len(ticks):
                    t_click = np.linspace(0, 0.045, click_dur, endpoint=False)
                    # Frequency crescendo: 1000Hz -> 1600Hz as time runs out
                    freq = 1000 + (cur_t / dur_cd) * 600
                    click = 0.75 * np.sin(2 * np.pi * freq * t_click) * np.exp(-t_click * 110)
                    ticks[idx:idx + click_dur] += click
                # Accelerando in the final 1.8 seconds: intervals shrink from 0.5s down to 0.12s
                if cur_t >= (dur_cd - 1.8):
                    interval = max(0.12, interval * 0.82)
                cur_t += interval
            write_wav(p_cd, ticks)

        # BGM: Priority to custom high-energy studio BGM track
        custom_bgm_cand = self.opt.bgm_path or Path("assets/bgm/bgm_cyber_trap.wav")
        if custom_bgm_cand and Path(custom_bgm_cand).exists():
            p_bgm = Path(custom_bgm_cand)
        else:
            p_bgm = audio_dir / "bgm_quiz.wav"
            if not p_bgm.exists():
                dur_b = 16.0
                t_b = np.linspace(0, dur_b, int(sr * dur_b), endpoint=False)
                bgm = np.zeros_like(t_b)
                notes = [261.63, 329.63, 392.00, 440.00, 523.25, 392.00, 329.63, 293.66]
                for i, step_t in enumerate(np.arange(0.0, dur_b, 0.25)):
                    idx = int(step_t * sr)
                    n_len = int(0.2 * sr)
                    if idx + n_len <= len(t_b):
                        t_sub = np.linspace(0, 0.2, n_len, endpoint=False)
                        bgm[idx:idx + n_len] += 0.25 * np.sin(2 * np.pi * notes[i % len(notes)] * t_sub) * np.exp(-t_sub * 16)
                write_wav(p_bgm, bgm * 0.7)

        return {"ding": p_ding, "countdown": p_cd, "bgm": p_bgm}

    def _probe_dur(self, file_path: Path) -> float:
        if not file_path.exists() or file_path.stat().st_size == 0:
            raise RuntimeError(f"Cannot probe duration: audio file missing or empty: {file_path}")
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {file_path}: {res.stderr.strip()}")
        dur_str = res.stdout.strip()
        try:
            dur = float(dur_str)
            if not math.isfinite(dur) or dur <= 0:
                raise ValueError()
            return dur
        except Exception as e:
            raise RuntimeError(f"Invalid duration '{dur_str}' from ffprobe for {file_path}") from e

    def _pipe_frames_to_ffmpeg(self, units: list[dict[str, Any]], voice_files: dict[str, Path], output_file: Path) -> tuple[float, list[dict[str, Any]]]:
        # Pre-cache and pre-scale images in memory for 100x render speedup
        card_w_169, card_h_169 = 380, 380
        card_w_916, card_h_916 = 320, 320
        for q in units:
            for c in q.get("clues", []):
                ip = c.get("image_path")
                if ip and Path(ip).exists():
                    try:
                        with Image.open(ip) as raw_img:
                            im = raw_img.convert("RGBA")
                            # 16:9 cache: fit into max_w=460, max_h=300 with golden border & shadow
                            sc_169 = min(460 / max(1, im.width), 300 / max(1, im.height))
                            tw_169 = int(im.width * sc_169)
                            th_169 = int(im.height * sc_169)
                            s_169 = im.resize((tw_169, th_169), Image.Resampling.LANCZOS)
                            card_169 = Image.new("RGBA", (tw_169 + 16, th_169 + 16), (0, 0, 0, 0))
                            draw_169 = ImageDraw.Draw(card_169)
                            draw_169.rounded_rectangle([0, 0, tw_169 + 15, th_169 + 15], radius=16, fill=(0, 0, 0, 110))
                            draw_169.rounded_rectangle([3, 3, tw_169 + 12, th_169 + 12], radius=14, fill=(255, 255, 255), outline=(255, 215, 0), width=3)
                            card_169.paste(s_169, (8, 8), s_169)
                            c["_cached_169"] = card_169

                            # 9:16 cache: fit into max_w=380, max_h=250 with golden border & shadow
                            sc_916 = min(380 / max(1, im.width), 250 / max(1, im.height))
                            tw_916 = int(im.width * sc_916)
                            th_916 = int(im.height * sc_916)
                            s_916 = im.resize((tw_916, th_916), Image.Resampling.LANCZOS)
                            card_916 = Image.new("RGBA", (tw_916 + 16, th_916 + 16), (0, 0, 0, 0))
                            draw_916 = ImageDraw.Draw(card_916)
                            draw_916.rounded_rectangle([0, 0, tw_916 + 15, th_916 + 15], radius=16, fill=(0, 0, 0, 110))
                            draw_916.rounded_rectangle([3, 3, tw_916 + 12, th_916 + 12], radius=14, fill=(255, 255, 255), outline=(255, 215, 0), width=3)
                            card_916.paste(s_916, (8, 8), s_916)
                            c["_cached_916"] = card_916
                    except Exception:
                        pass

            # Also pre-cache reveal_image_path if provided!
            rev_p = q.get("reveal_image_path")
            if rev_p and Path(rev_p).exists():
                try:
                    with Image.open(rev_p) as raw_rev:
                        im_r = raw_rev.convert("RGBA")
                        sc_r169 = min(540 / max(1, im_r.width), 340 / max(1, im_r.height))
                        tw_r169 = int(im_r.width * sc_r169)
                        th_r169 = int(im_r.height * sc_r169)
                        s_r169 = im_r.resize((tw_r169, th_r169), Image.Resampling.LANCZOS)
                        card_r169 = Image.new("RGBA", (tw_r169 + 16, th_r169 + 16), (0, 0, 0, 0))
                        draw_r169 = ImageDraw.Draw(card_r169)
                        draw_r169.rounded_rectangle([0, 0, tw_r169 + 15, th_r169 + 15], radius=16, fill=(0, 0, 0, 120))
                        draw_r169.rounded_rectangle([3, 3, tw_r169 + 12, th_r169 + 12], radius=14, fill=(255, 255, 255), outline=(255, 215, 0), width=3)
                        card_r169.paste(s_r169, (8, 8), s_r169)
                        q["_cached_rev_169"] = card_r169

                        sc_r916 = min(420 / max(1, im_r.width), 280 / max(1, im_r.height))
                        tw_r916 = int(im_r.width * sc_r916)
                        th_r916 = int(im_r.height * sc_r916)
                        s_r916 = im_r.resize((tw_r916, th_r916), Image.Resampling.LANCZOS)
                        card_r916 = Image.new("RGBA", (tw_r916 + 16, th_r916 + 16), (0, 0, 0, 0))
                        draw_r916 = ImageDraw.Draw(card_r916)
                        draw_r916.rounded_rectangle([0, 0, tw_r916 + 15, th_r916 + 15], radius=16, fill=(0, 0, 0, 120))
                        draw_r916.rounded_rectangle([3, 3, tw_r916 + 12, th_r916 + 12], radius=14, fill=(255, 255, 255), outline=(255, 215, 0), width=3)
                        card_r916.paste(s_r916, (8, 8), s_r916)
                        q["_cached_rev_916"] = card_r916
                except Exception:
                    pass

        cur_t = 0.0
        events = []
        
        intro_dur = self._probe_dur(voice_files["intro"]) + 0.5
        events.append({"type": "intro", "start": cur_t, "dur": intro_dur})
        cur_t += intro_dur
        
        for i, q in enumerate(units, 1):
            q_dur = self._probe_dur(voice_files[f"q{i}_q"]) + (0.2 if self.opt.pacing == "fast" else 0.3)
            cd_dur = float(q.get("countdown_seconds") or (3.0 if self.opt.pacing == "fast" else self.opt.countdown_seconds))
            a_dur = self._probe_dur(voice_files[f"q{i}_a"]) + (0.5 if self.opt.pacing == "fast" else 0.8)
            events.append({
                "type": "question",
                "idx": i,
                "total_q": len(units),
                "data": q,
                "q_start": cur_t,
                "q_dur": q_dur,
                "cd_start": cur_t + q_dur,
                "cd_dur": cd_dur,
                "rev_start": cur_t + q_dur + cd_dur,
                "rev_dur": a_dur,
                "total_dur": q_dur + cd_dur + a_dur
            })
            cur_t += q_dur + cd_dur + a_dur
            
        outro_dur = self._probe_dur(voice_files["outro"]) + 1.0
        events.append({"type": "outro", "start": cur_t, "dur": outro_dur})
        cur_t += outro_dur
        
        total_dur = cur_t
        total_frames = int(total_dur * self.opt.fps)
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.opt.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-r", str(self.opt.fps),
            str(output_file)
        ]
        
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Determine theme colors if not using custom image
        theme_colors = {
            "cyber": ((14, 18, 38), (24, 20, 52)),
            "blue": ((18, 28, 56), (12, 16, 32)),
            "orange": ((235, 110, 30), (190, 60, 10)),
            "purple": ((142, 68, 173), (74, 35, 90)),
            "forest": ((39, 174, 96), (20, 90, 50)),
            "dark_gold": ((212, 175, 55), (120, 90, 20)),
        }
        top_c, bot_c = theme_colors.get(self.opt.bg_theme, ((14, 18, 38), (24, 20, 52)))
        
        bg = DynamicBackgroundCompositor(
            self.width, self.height,
            top_color=top_c,
            bottom_color=bot_c,
            custom_image_path=self.opt.bg_image,
            blur_bg=True
        )
        
        for f in range(total_frames):
            t = f / self.opt.fps
            frame = self._render_frame_at_time(t, events, bg)
            proc.stdin.write(frame.tobytes())
            
        proc.stdin.close()
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg rawvideo pipeline failed with exit code {proc.returncode}")
        return total_dur, events

    def _render_frame_at_time(self, t: float, events: list[dict[str, Any]], bg: DynamicBackgroundCompositor) -> Image.Image:
        canvas = bg.render(t)
        draw = ImageDraw.Draw(canvas)
        
        if t < events[0]["start"] + events[0]["dur"]:
            return self._render_intro_card(canvas, draw, t)
        elif t >= events[-1]["start"]:
            return self._render_outro_card(canvas, draw, t)
        else:
            for ev in events[1:-1]:
                if ev["q_start"] <= t < ev["rev_start"] + ev["rev_dur"]:
                    card_frame = self._render_question_card(canvas, draw, t, ev)
                    # Punch Screen Shake on Reveal (first 0.18s when chime sounds)
                    if t >= ev["rev_start"]:
                        t_rev = t - ev["rev_start"]
                        if 0.0 <= t_rev <= 0.18:
                            intensity = 1.0 - (t_rev / 0.18)
                            shake_x = int(5 * math.sin(t_rev * 70.0) * intensity)
                            shake_y = int(4 * math.cos(t_rev * 75.0) * intensity)
                            return ImageChops.offset(card_frame, shake_x, shake_y)
                    return card_frame
                    
        return canvas

    def _render_intro_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> Image.Image:
        if self.opt.channel_profile:
            return self._render_channel_cover(canvas, draw, False)
        mascot = self.mascots["WELCOME"]
        bob = 8 * math.sin(t * 4.0)
        if self.opt.aspect_ratio == "16:9":
            mx = 260
            my = int(self.height // 2 - mascot.height // 2 + bob)
            canvas.paste(mascot, (mx, my), mascot)
            
            # Intro card on right 2/3: bounds [720, 240, 1780, 840], height 600px
            draw.rounded_rectangle([720 + 6, 240 + 6, 1780 + 6, 840 + 6], radius=36, fill=(0, 0, 0, 85))
            draw.rounded_rectangle([720, 240, 1780, 840], radius=36, fill=(25, 30, 45), outline=(255, 215, 0), width=6)
            
            # Line 1: Golden arcade title flanked by 3D Lightning icons
            font_title = get_font(60 if self.is_english else 64, bold=True)
            title_txt = "THE ULTIMATE CHALLENGE" if self.is_english else "THỬ THÁCH TRÍ TUỆ"
            paste_icon_with_text(canvas, draw, (1250, 380), title_txt, font_title, "lightning", icon_size=64, icon_side="both", fill=(255, 215, 0), stroke_color=(20, 20, 20), stroke_width=4)
            
            # Line 2: White subtitle
            font_sub = get_font(38, bold=True)
            sub_txt = "CAN YOU SCORE 100%?" if self.is_english else "ĐỐ BẠN TRẢ LỜI ĐÚNG HẾT 100%!"
            draw_comic_text(draw, (1250, 490), sub_txt, font=font_sub, fill=(255, 255, 255), stroke_width=3, stroke_color=(20, 20, 20))
            
            # Line 3: High-contrast Rule Pill container with 3D Fire icon
            draw.rounded_rectangle([860, 610, 1640, 700], radius=24, fill=(231, 76, 60), outline=(255, 255, 255), width=3)
            font_cta = get_font(28 if self.is_english else 30, bold=True)
            cta_txt = "3 SECONDS PER QUESTION • READY?" if self.is_english else "3 GIÂY MỖI CÂU • BẠN ĐÃ SẴN SÀNG?"
            paste_icon_with_text(canvas, draw, (1250, 655), cta_txt, font_cta, "fire", icon_size=38, icon_side="left", fill=(255, 255, 255))
        else:
            # 9:16 Vertical: Mascot top-center (y=260), Card below (y=680..1340)
            target_h = min(380, int(self.height * 0.24))
            m_scaled = mascot.resize((int(mascot.width * (target_h / max(1, mascot.height))), target_h), Image.Resampling.LANCZOS)
            canvas.paste(m_scaled, (self.width // 2 - m_scaled.width // 2, int(260 + bob)), m_scaled)
            
            draw.rounded_rectangle([80 + 5, 680 + 6, 1000 + 5, 1340 + 6], radius=32, fill=(0, 0, 0, 85))
            draw.rounded_rectangle([80, 680, 1000, 1340], radius=32, fill=(25, 30, 45), outline=(255, 215, 0), width=5)
            
            # Line 1 with 3D Lightning
            font_title = get_font(52 if self.is_english else 56, bold=True)
            title_txt = "THE ULTIMATE CHALLENGE" if self.is_english else "THỬ THÁCH TRÍ TUỆ"
            paste_icon_with_text(canvas, draw, (540, 810), title_txt, font_title, "lightning", icon_size=56, icon_side="both", fill=(255, 215, 0), stroke_color=(20, 20, 20), stroke_width=4)
            
            # Line 2
            font_sub = get_font(36, bold=True)
            sub_txt = "CAN YOU SCORE 100%?" if self.is_english else "ĐỐ BẠN ĐÚNG HẾT 100%!"
            draw_comic_text(draw, (540, 930), sub_txt, font=font_sub, fill=(255, 255, 255), stroke_width=3, stroke_color=(20, 20, 20))
            
            # Line 3: High-contrast Rule Pill container with 3D Fire icon
            draw.rounded_rectangle([150, 1060, 930, 1150], radius=24, fill=(231, 76, 60), outline=(255, 255, 255), width=3)
            font_cta = get_font(28 if self.is_english else 30, bold=True)
            cta_txt = "3S PER QUESTION • READY?" if self.is_english else "3 GIÂY / CÂU • BẮT ĐẦU NGAY!"
            paste_icon_with_text(canvas, draw, (540, 1105), cta_txt, font_cta, "fire", icon_size=36, icon_side="left", fill=(255, 255, 255))
        return canvas

    def _render_outro_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> Image.Image:
        if self.opt.channel_profile:
            return self._render_channel_cover(canvas, draw, True)
        mascot = self.mascots["CELEBRATE"]
        bob = 8 * math.sin(t * 4.0)
        if self.opt.aspect_ratio == "16:9":
            mx = 240
            my = int(self.height // 2 - mascot.height // 2 + bob)
            canvas.paste(mascot, (mx, my), mascot)
            
            # Scoreboard Arcade Card on right 2/3
            draw.rounded_rectangle([680 + 6, 170 + 8, 1800 + 6, 930 + 8], radius=36, fill=(0, 0, 0, 85))
            draw.rounded_rectangle([680, 170, 1800, 930], radius=36, fill=(25, 30, 45), outline=(255, 215, 0), width=6)
            
            # Title with 3D Trophies on both sides
            out_title = "FINAL SCOREBOARD" if self.is_english else "BẢNG TỔNG KẾT ĐIỂM SỐ"
            paste_icon_with_text(canvas, draw, (1240, 250), out_title, get_font(50, bold=True), "trophy", icon_size=58, icon_side="both", fill=(255, 215, 0), stroke_color=(0, 0, 0), stroke_width=3)
            
            # Tiers with 3D Crown, Star, Fire
            if self.is_english:
                tiers = [
                    ("TOP 1: 100% — GEOGRAPHY GENIUS", (46, 204, 113), "crown"),
                    ("TOP 2: 70%+ — MASTER TRAVELER", (52, 152, 219), "star"),
                    ("TOP 3: UNDER 50% — KEEP PRACTICING", (231, 76, 60), "fire"),
                ]
            else:
                tiers = [
                    ("TOP 1: ĐÚNG 100% — THIÊN TÀI TRÍ TUỆ", (46, 204, 113), "crown"),
                    ("TOP 2: ĐÚNG 70%+ — CAO THỦ XUẤT SẮC", (52, 152, 219), "star"),
                    ("TOP 3: DƯỚI 50% — CẦN CỐ GẮNG THÊM", (231, 76, 60), "fire"),
                ]
            for ti, (t_text, t_color, t_icon) in enumerate(tiers):
                ty = 360 + ti * 105
                draw.rounded_rectangle([740, ty, 1740, ty + 80], radius=20, fill=(35, 42, 60), outline=t_color, width=3)
                paste_icon_with_text(canvas, draw, (795, ty + 40), "", get_font(32, bold=True), t_icon, icon_size=46, icon_side="left")
                draw.text((845, ty + 40), t_text, font=get_font(32, bold=True), fill=(255, 255, 255), anchor="lm")
            
            # Strong CTA Button with 3D Speech Balloon & Thumbs Up!
            draw.rounded_rectangle([740, 715, 1740, 845], radius=28, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
            cta1_txt = "COMMENT YOUR SCORE BELOW!" if self.is_english else "BẠN ĐẠT MẤY ĐIỂM? BÌNH LUẬN NGAY!"
            cta2_txt = "LIKE & SUBSCRIBE FOR NEXT ROUND!" if self.is_english else "LIKE & ĐĂNG KÝ KÊNH ĐỂ ĐẤU TIẾP VÒNG SAU!"
            paste_icon_with_text(canvas, draw, (1240, 755), cta1_txt, get_font(36, bold=True), "speech_balloon", icon_size=42, icon_side="left", fill=(255, 255, 255), stroke_color=(0, 0, 0), stroke_width=2)
            paste_icon_with_text(canvas, draw, (1240, 805), cta2_txt, get_font(24, bold=True), "thumbs_up", icon_size=32, icon_side="left", fill=(255, 215, 0))
        else:
            # 9:16 Vertical Shorts Scoreboard
            target_h = min(360, int(self.height * 0.22))
            m_scaled = mascot.resize((int(mascot.width * (target_h / max(1, mascot.height))), target_h), Image.Resampling.LANCZOS)
            canvas.paste(m_scaled, (self.width // 2 - m_scaled.width // 2, int(220 + bob)), m_scaled)
            
            draw.rounded_rectangle([80 + 5, 620 + 6, 1000 + 5, 1420 + 6], radius=32, fill=(0, 0, 0, 85))
            draw.rounded_rectangle([80, 620, 1000, 1420], radius=32, fill=(25, 30, 45), outline=(255, 215, 0), width=5)
            
            out_title_916 = "FINAL SCOREBOARD" if self.is_english else "BẢNG TỔNG KẾT ĐIỂM"
            paste_icon_with_text(canvas, draw, (540, 700), out_title_916, get_font(46, bold=True), "trophy", icon_size=52, icon_side="both", fill=(255, 215, 0), stroke_color=(0, 0, 0), stroke_width=3)
            
            # Tiers with 3D icons
            if self.is_english:
                tiers_916 = [
                    ("TOP 1: 100% — GENIUS", (46, 204, 113), "crown"),
                    ("TOP 2: 70%+ — MASTER", (52, 152, 219), "star"),
                    ("TOP 3: UNDER 50% — PRACTICE", (231, 76, 60), "fire"),
                ]
            else:
                tiers_916 = [
                    ("TOP 1: ĐÚNG HẾT — THIÊN TÀI", (46, 204, 113), "crown"),
                    ("TOP 2: ĐÚNG 70%+ — XUẤT SẮC", (52, 152, 219), "star"),
                    ("TOP 3: DƯỚI 50% — CẦN TẬP TIẾP", (231, 76, 60), "fire"),
                ]
            for ti, (t_text, t_color, t_icon) in enumerate(tiers_916):
                ty = 780 + ti * 110
                draw.rounded_rectangle([120, ty, 960, ty + 90], radius=18, fill=(35, 42, 60), outline=t_color, width=3)
                paste_icon_with_text(canvas, draw, (170, ty + 45), "", get_font(30, bold=True), t_icon, icon_size=42, icon_side="left")
                draw.text((220, ty + 45), t_text, font=get_font(30, bold=True), fill=(255, 255, 255), anchor="lm")
            
            # CTA at bottom
            draw.rounded_rectangle([120, 1180, 960, 1360], radius=24, fill=(231, 76, 60), outline=(255, 255, 255), width=4)
            cta1_916 = "COMMENT YOUR SCORE BELOW!" if self.is_english else "BẠN ĐẠT MẤY ĐIỂM? BÌNH LUẬN NGAY!"
            cta2_916 = "LIKE & FOLLOW FOR NEXT ROUND!" if self.is_english else "LIKE & FOLLOW ĐỂ XEM TIẾP!"
            paste_icon_with_text(canvas, draw, (540, 1245), cta1_916, get_font(30 if self.is_english else 32, bold=True), "speech_balloon", icon_size=38, icon_side="left", fill=(255, 255, 255), stroke_color=(0, 0, 0), stroke_width=2)
            paste_icon_with_text(canvas, draw, (540, 1305), cta2_916, get_font(24, bold=True), "thumbs_up", icon_size=28, icon_side="left", fill=(255, 215, 0))
        return canvas

    def _render_channel_cover(self, canvas, draw, outro=False):
        from app.services.quiz_channel_renderer import render
        return render(self, canvas, draw, get_font, outro=outro)

    def _render_channel_question(self, canvas, draw, t, event):
        from app.services.quiz_channel_renderer import render
        return render(self, canvas, draw, get_font, event=event, time=t)

    def _render_question_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float, ev: dict[str, Any]) -> Image.Image:
        if self.opt.channel_profile:
            return self._render_channel_question(canvas, draw, t, ev)
        q_data = ev["data"]
        q_idx = ev["idx"]
        is_cd = ev["cd_start"] <= t < ev["rev_start"]
        is_rev = t >= ev["rev_start"]
        
        if t < ev["cd_start"]:
            progress = 1.0
            cd_elapsed = 0.0
        elif is_cd:
            progress = max(0.0, min(1.0, 1.0 - (t - ev["cd_start"]) / ev["cd_dur"]))
            cd_elapsed = max(0.0, min(1.0, (t - ev["cd_start"]) / ev["cd_dur"]))
        else:
            progress = 0.0
            cd_elapsed = 1.0
            
        mascot_state = "CELEBRATE" if is_rev else ("THINKING" if is_cd else "WELCOME")
        bob = 10 * math.sin(t * 3.0)
        
        if "cards" in q_data or "scene_image" in q_data:
            return self._render_riddle_mystra(canvas, draw, t, ev, cd_elapsed, is_cd, is_rev)

        if self.opt.aspect_ratio == "16:9":
            # Dynamic Font Fit for Question Title with Comic Polish
            q_text = q_data.get("question", "ĐỐ VUI")
            font_size_q = 44
            if len(q_text) > 48:
                font_size_q = 36
            if len(q_text) > 60:
                font_size_q = 30
            draw.rounded_rectangle([190 + 4, 35 + 5, 1600 + 4, 150 + 5], radius=28, fill=(0, 0, 0, 75))
            draw.rounded_rectangle([190, 35, 1600, 150], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
            font_h = get_font(font_size_q, bold=True)
            draw.text((895, 92), q_text, font=font_h, fill=(25, 25, 30), anchor="mm")
            
            # Difficulty & Level Badge (Top Right)
            diff_label, diff_color = get_difficulty_badge(q_idx, ev.get("total_q", 10), lang="en" if self.is_english else "vi")
            draw.rounded_rectangle([1620 + 4, 35 + 5, 1900 + 4, 150 + 5], radius=24, fill=(0, 0, 0, 75))
            draw.rounded_rectangle([1620, 35, 1900, 150], radius=24, fill=diff_color, outline=(255, 255, 255), width=3)
            q_label = f"QUESTION {q_idx}" if self.is_english else f"CÂU {q_idx}"
            paste_icon_with_text(canvas, draw, (1760, 72), q_label, get_font(24 if self.is_english else 28, bold=True), "fire", icon_size=32, icon_side="left", fill=(255, 255, 255), stroke_color=(20, 20, 20), stroke_width=2)
            draw.text((1760, 114), diff_label, font=get_font(18, bold=True), fill=(255, 255, 255), anchor="mm")
            
            # 1. Mode: Mystery Box
            if "boxes" in q_data:
                self._draw_mystery_boxes_169(draw, canvas, q_data["boxes"], is_rev, bob)
            # 2. Mode: Missing Letters
            elif "word_tiles" in q_data:
                self._draw_word_tiles_169(draw, q_data["word_tiles"], is_rev, bob)
            # 3. Mode: This or That
            elif "side_a" in q_data and "side_b" in q_data:
                self._draw_this_or_that_169(draw, q_data["side_a"], q_data["side_b"], bob, t)
            # 4. Mode: Anime Character Clues or Multiple Choice (with Pills)
            elif "universe" in q_data or "choices" in q_data:
                self._draw_anime_character_169(draw, canvas, q_data, is_rev, is_cd, cd_elapsed, bob, t, ev["rev_start"])
            # 5. Mode: Rebus Clues / Question Box
            else:
                clues = q_data.get("clues", [])
                num_clues = len(clues)
                if num_clues >= 1:
                    spacing = 1500 / max(1, num_clues)
                    start_x = 210 + spacing / 2
                    for ci, c in enumerate(clues):
                        cx = int(start_x + ci * spacing)
                        c_col = c.get("color", (41, 128, 185))
                        c_lbl = c.get("word", "")
                        card_w = min(420, int(spacing * 0.75))
                        card_h = min(420, int(spacing * 0.75))
                        
                        c_scaled = c.get("_cached_169")
                        if c_scaled is not None:
                            canvas.paste(c_scaled, (cx - card_w // 2, int(300 + bob)), c_scaled)
                        else:
                            draw.rounded_rectangle([cx - card_w // 2, int(300 + bob), cx + card_w // 2, int(300 + card_h + bob)], radius=28, fill=c_col, outline=(255, 255, 255), width=6)
                            font_cl = get_font(56, bold=True)
                            draw.text((cx, int(300 + card_h // 2 + bob)), c_lbl, font=font_cl, fill=(255, 255, 255), anchor="mm")
                            
                        if ci < num_clues - 1:
                            next_cx = int(start_x + (ci + 1) * spacing)
                            mid_x = (cx + next_cx) // 2
                            font_plus = get_font(72, bold=True)
                            draw.text((mid_x, int(300 + card_h // 2 + bob)), "+", font=font_plus, fill=(255, 255, 255), anchor="mm")
                else:
                    draw.rounded_rectangle([360, int(320 + bob), 1560, int(680 + bob)], radius=32, fill=(41, 128, 185), outline=(255, 255, 255), width=6)
                    font_q = get_font(56, bold=True)
                    draw.text((960, int(500 + bob)), q_data.get("question", ""), font=font_q, fill=(255, 255, 255), anchor="mm")
                
            mascot = self.mascots[mascot_state]
            my_y = int(self.height - mascot.height - 20 + bob * 0.5)
            canvas.paste(mascot, (60, my_y), mascot)
            
            if is_rev:
                self._draw_reveal_bar(draw, 340, 880, 1500, 110, q_data.get("answer_text", ""), t, ev["rev_start"])
            else:
                self._draw_timer_bar(draw, canvas, 340, 890, 1500, 80, progress, t)
                
        else:  # 9:16 Vertical Shorts
            # Multi-line word-wrap & responsive font for 9:16 title box
            q_text = q_data.get("question", "ĐỐ VUI")
            words = q_text.split()
            if len(words) > 6 and len(q_text) > 30:
                mid = len(words) // 2
                line1 = " ".join(words[:mid])
                line2 = " ".join(words[mid:])
                draw.rounded_rectangle([60 + 4, 150 + 5, 1020 + 4, 310 + 5], radius=28, fill=(0, 0, 0, 75))
                draw.rounded_rectangle([60, 150, 1020, 310], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
                font_h = get_font(32, bold=True)
                draw.text((540, 205), line1, font=font_h, fill=(25, 25, 30), anchor="mm")
                draw.text((540, 255), line2, font=font_h, fill=(25, 25, 30), anchor="mm")
            else:
                draw.rounded_rectangle([60 + 4, 160 + 5, 1020 + 4, 290 + 5], radius=28, fill=(0, 0, 0, 75))
                draw.rounded_rectangle([60, 160, 1020, 290], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
                font_h = get_font(34, bold=True)
                draw.text((540, 225), q_text, font=font_h, fill=(25, 25, 30), anchor="mm")
            
            # Difficulty & Level Badge (Pill in Center)
            diff_label, diff_color = get_difficulty_badge(q_idx, ev.get("total_q", 10), lang="en" if self.is_english else "vi")
            draw.rounded_rectangle([250 + 4, 325 + 4, 830 + 4, 395 + 4], radius=22, fill=(0, 0, 0, 75))
            draw.rounded_rectangle([250, 325, 830, 395], radius=22, fill=diff_color, outline=(255, 255, 255), width=3)
            q_center_lbl = f"QUESTION {q_idx} - {diff_label}" if self.is_english else f"CÂU {q_idx} - {diff_label}"
            paste_icon_with_text(canvas, draw, (540, 360), q_center_lbl, get_font(24 if self.is_english else 28, bold=True), "fire", icon_size=32, icon_side="left", fill=(255, 255, 255), stroke_color=(20, 20, 20), stroke_width=2)
            
            if "boxes" in q_data:
                self._draw_mystery_boxes_916(draw, canvas, q_data["boxes"], is_rev, bob)
            elif "word_tiles" in q_data:
                self._draw_word_tiles_916(draw, q_data["word_tiles"], is_rev, bob)
            elif "side_a" in q_data and "side_b" in q_data:
                self._draw_this_or_that_916(draw, q_data["side_a"], q_data["side_b"], bob, t)
            elif "universe" in q_data or "choices" in q_data:
                self._draw_anime_character_916(draw, canvas, q_data, is_rev, is_cd, cd_elapsed, bob, t, ev["rev_start"], mascot_state)
            else:
                clues = q_data.get("clues", [])
                num_clues = len(clues)
                if num_clues >= 1:
                    spacing_y = 740 / max(1, num_clues)
                    start_y = 460 + spacing_y / 2
                    for ci, c in enumerate(clues):
                        cy = int(start_y + ci * spacing_y)
                        c_col = c.get("color", (41, 128, 185))
                        c_lbl = c.get("word", "")
                        card_s = min(340, int(spacing_y * 0.85))
                        
                        c_scaled = c.get("_cached_916")
                        if c_scaled is not None:
                            canvas.paste(c_scaled, (540 - card_s // 2, cy - card_s // 2), c_scaled)
                        else:
                            draw.rounded_rectangle([540 - card_s // 2, cy - card_s // 2, 540 + card_s // 2, cy + card_s // 2], radius=28, fill=c_col, outline=(255, 255, 255), width=6)
                            font_cl = get_font(56, bold=True)
                            draw.text((540, cy), c_lbl, font=font_cl, fill=(255, 255, 255), anchor="mm")
                else:
                    draw.rounded_rectangle([100, int(560 + bob), 980, int(1120 + bob)], radius=32, fill=(41, 128, 185), outline=(255, 255, 255), width=6)
                    font_q = get_font(48, bold=True)
                    draw.text((540, int(840 + bob)), q_data.get("question", ""), font=font_q, fill=(255, 255, 255), anchor="mm")
                
            # In 9:16, Mascot stands in the bottom-left corner for ALL question modes
            mascot = self.mascots[mascot_state]
            target_m_h = 350
            sc = target_m_h / max(1, mascot.height)
            m_scaled = mascot.resize((int(mascot.width * sc), target_m_h), Image.Resampling.LANCZOS)
            mx = 35
            my = int(self.height - m_scaled.height - 35 + bob * 0.5)
            canvas.paste(m_scaled, (mx, my), m_scaled)
            
            if is_rev:
                self._draw_reveal_bar(draw, 265, 1660, 765, 110, q_data.get("answer_text", ""), t, ev["rev_start"])
            else:
                self._draw_timer_bar(draw, canvas, 265, 1680, 765, 80, progress, t)
                
        return canvas

    def _render_riddle_mystra(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float, ev: dict[str, Any], cd_elapsed: float, is_cd: bool, is_rev: bool) -> Image.Image:
        """Full-Screen Cinematic Logic Riddle in QuizMystra style: Supports both 1-Scene Riddle and 4-Cards Comparison."""
        q_data = ev["data"]
        q_idx = ev["idx"]
        w, h = self.width, self.height
        header_h = 140 if w == 1920 else 180

        # Sub-Mode A: 4-Cards Comparison Mode (e.g. WHO IS PREGNANT?, WHO IS GOING ON A DATE?, WHO IS THE KILLER?)
        if "cards" in q_data:
            cards = q_data["cards"][:4]
            n_cards = len(cards)
            card_w = 430 if w == 1920 else 470
            card_h = 740 if w == 1920 else 700
            gap = 40 if w == 1920 else 20
            columns = n_cards if w == 1920 else min(2, n_cards)
            start_x = (w - (columns * card_w + max(0, columns - 1) * gap)) // 2
            y_start = 175 if w == 1920 else 220
            correct_opt = str(q_data.get("correct_option") or "1")

            # Draw 4 cards
            for i, c_info in enumerate(cards):
                cx = start_x + (i % columns) * (card_w + gap)
                cy = y_start + (i // columns) * (card_h + 30)
                cid = str(c_info.get("id") or str(i + 1))
                is_correct = (cid == correct_opt)
                c_bob = 6 * math.sin(t * 3.5 + i)

                # Card Outer Box
                border_col = (46, 204, 113) if (is_rev and is_correct) else (240, 240, 240)
                border_w = 6 if (is_rev and is_correct) else 3
                draw.rounded_rectangle([cx + 4, int(cy + c_bob) + 6, cx + card_w + 4, int(cy + card_h + c_bob) + 6], radius=24, fill=(0, 0, 0, 90))
                draw.rounded_rectangle([cx, int(cy + c_bob), cx + card_w, int(cy + card_h + c_bob)], radius=24, fill=(24, 30, 46), outline=border_col, width=border_w)

                # Photo inside card
                cache_key = f"_cached_c_img_{w}_{h}"
                cached_c_img = c_info.get(cache_key)
                if cached_c_img is None:
                    cp = c_info.get("image_path")
                    if cp and Path(cp).exists():
                        try:
                            with Image.open(cp) as raw_p:
                                im_p = raw_p.convert("RGB")
                                pw, ph = image_slot("card", self.opt.aspect_ratio).size
                                nw, nh = fitted_size(im_p.size, (pw, ph))
                                im_res = im_p.resize((nw, nh), Image.Resampling.LANCZOS)
                                x0 = (pw - nw) // 2
                                y0 = (ph - nh) // 2
                                cached_c_img = Image.new("RGB", (pw, ph), (24, 30, 46))
                                cached_c_img.paste(im_res, (x0, y0))
                                c_info[cache_key] = cached_c_img
                        except Exception:
                            pass

                if cached_c_img is not None:
                    canvas.paste(cached_c_img, (cx + 20, int(cy + 105 + c_bob)))

                # Top-Center Circular Badge (1, 2, 3, 4)
                badge_x = cx + card_w // 2
                badge_y = int(cy + 55 + c_bob)
                badge_r = 38
                b_fill = (46, 204, 113) if (is_rev and is_correct) else (214, 38, 38)
                draw.ellipse([badge_x - badge_r, badge_y - badge_r, badge_x + badge_r, badge_y + badge_r], fill=b_fill, outline=(255, 255, 255), width=4)
                font_num = get_font(44, bold=True)
                draw.text((badge_x, badge_y), cid, font=font_num, fill=(255, 255, 255), anchor="mm")

                # Bottom Detail Label Container
                lbl_y1 = int(cy + card_h - 150 + c_bob)
                lbl_y2 = int(cy + card_h - 20 + c_bob)
                draw.rounded_rectangle([cx + 20, lbl_y1, cx + card_w - 20, lbl_y2], radius=18, fill=(18, 22, 34), outline=(255, 215, 0) if (is_rev and is_correct) else (0, 220, 255), width=2)
                font_lbl = get_font(24, bold=True)
                c_lbl = c_info.get("label", "")
                draw.text((cx + card_w // 2, (lbl_y1 + lbl_y2) // 2), c_lbl, font=font_lbl, fill=(255, 255, 255), anchor="mm")

                # Reveal Pulse Indicator over correct card
                if is_rev and is_correct:
                    pulse_box = int(6 * math.sin(t * 8.0))
                    draw.rounded_rectangle([cx - pulse_box, int(cy + c_bob) - pulse_box, cx + card_w + pulse_box, int(cy + card_h + c_bob) + pulse_box], radius=26, outline=(46, 204, 113), width=4)

            # Bottom Explanation Banner in Reveal
            if is_rev:
                exp_text = q_data.get("explanation_text") or f"ANSWER: CARD {correct_opt}!"
                draw.rounded_rectangle([180 + 4, h - 130 + 5, w - 180 + 4, h - 35 + 5], radius=24, fill=(0, 0, 0, 110))
                draw.rounded_rectangle([180, h - 130, w - 180, h - 35], radius=24, fill=(214, 38, 38), outline=(255, 255, 255), width=3)
                font_exp = get_font(32, bold=True)
                draw.text((w // 2, h - 82), exp_text, font=font_exp, fill=(255, 255, 255), anchor="mm")

        # Sub-Mode B: 1-Scene Clue Anomaly Riddle (e.g. WHO IS THE SLEEPWALKER?)
        else:
            # 1. Background Scene: full-width illustration
            cached_scene = q_data.get("_cached_scene")
            if cached_scene is None:
                scene_p = q_data.get("scene_image")
                if scene_p and Path(scene_p).exists():
                    try:
                        with Image.open(scene_p) as raw_scene:
                            im_sc = raw_scene.convert("RGB")
                            target_w, target_h = image_slot("scene", self.opt.aspect_ratio).size
                            nw, nh = fitted_size(im_sc.size, (target_w, target_h))
                            im_resized = im_sc.resize((nw, nh), Image.Resampling.LANCZOS)
                            x0 = (target_w - nw) // 2
                            y0 = (target_h - nh) // 2
                            cached_scene = Image.new("RGB", (target_w, target_h), (24, 28, 42))
                            cached_scene.paste(im_resized, (x0, y0))
                            q_data["_cached_scene"] = cached_scene
                    except Exception:
                        pass

            if cached_scene is not None:
                canvas.paste(cached_scene, (0, header_h))
            else:
                draw.rectangle([0, header_h, w, h], fill=(24, 28, 42))

            # 2. Numbered Room / Option Badges (e.g. 1, 2, 3, 4)
            options = q_data.get("options") or [1, 2, 3, 4]
            coords = q_data.get("option_coords")
            if not coords:
                n_opt = len(options)
                spacing = w / max(1, n_opt)
                coords = [[int(spacing * (i + 0.5)), header_h + 90] for i in range(n_opt)]

            correct_opt = str(q_data.get("correct_option") or "1")
            for i, opt_label in enumerate(options):
                ox, oy = coords[i]
                font_num = get_font(72, bold=True)
                str_opt = str(opt_label)
                is_correct = (str_opt == correct_opt)
                n_bob = 4 * math.sin(t * 3.0 + i)
                for dx in range(-4, 5, 2):
                    for dy in range(-4, 5, 2):
                        draw.text((ox + dx, int(oy + dy + n_bob)), str_opt, font=font_num, fill=(20, 20, 20), anchor="mm")
                num_fill = (255, 215, 0) if (is_rev and is_correct) else (255, 255, 255)
                draw.text((ox, int(oy + n_bob)), str_opt, font=font_num, fill=num_fill, anchor="mm")

            # 3. Reveal Phase: Animated Red Circle & Arrow
            if is_rev:
                clue = q_data.get("clue_highlight")
                if clue:
                    cx, cy = clue.get("coord", [w // 2, h // 2])
                    cr = clue.get("radius", 65)
                    pulse_r = cr + int(8 * math.sin(t * 8.0))
                    draw.ellipse([cx - pulse_r - 4, cy - pulse_r - 4, cx + pulse_r + 4, cy + pulse_r + 4], outline=(255, 255, 255), width=3)
                    draw.ellipse([cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r], outline=(231, 76, 60), width=6)
                    arrow_from = clue.get("arrow_from")
                    if arrow_from:
                        ax, ay = arrow_from
                        draw.line([(ax, ay), (cx, cy - pulse_r)], fill=(231, 76, 60), width=6)
                        draw.polygon([(cx, cy - pulse_r), (cx - 12, cy - pulse_r - 20), (cx + 12, cy - pulse_r - 20)], fill=(231, 76, 60))

                exp_text = q_data.get("explanation_text") or f"ANSWER: OPTION {correct_opt}"
                draw.rounded_rectangle([180 + 4, h - 130 + 5, w - 180 + 4, h - 35 + 5], radius=24, fill=(0, 0, 0, 110))
                draw.rounded_rectangle([180, h - 130, w - 180, h - 35], radius=24, fill=(214, 38, 38), outline=(255, 255, 255), width=3)
                font_exp = get_font(34, bold=True)
                draw.text((w // 2, h - 82), exp_text, font=font_exp, fill=(255, 255, 255), anchor="mm")

        # 4. Top Header Banner: Solid Crimson Red (#D62626) with Twin-Bell Alarm Clock (Shared)
        draw.rectangle([0, 0, w, header_h], fill=(214, 38, 38))
        
        # Countdown time in seconds
        if t < ev["cd_start"]:
            cd_rem = int(math.ceil(ev["cd_dur"]))
        elif is_cd:
            cd_rem = max(0, int(math.ceil(ev["cd_dur"] - (t - ev["cd_start"]))))
        else:
            cd_rem = 0

        # Alarm Clock Widget on far left
        clock_x = 95
        clock_y = header_h // 2
        clock_r = 46
        draw.ellipse([clock_x - 40, clock_y - 46, clock_x - 16, clock_y - 22], fill=(255, 204, 0), outline=(30, 30, 30), width=3)
        draw.ellipse([clock_x + 16, clock_y - 46, clock_x + 40, clock_y - 22], fill=(255, 204, 0), outline=(30, 30, 30), width=3)
        draw.polygon([(clock_x - 28, clock_y + 32), (clock_x - 38, clock_y + 45), (clock_x - 20, clock_y + 45)], fill=(180, 180, 180))
        draw.polygon([(clock_x + 28, clock_y + 32), (clock_x + 38, clock_y + 45), (clock_x + 20, clock_y + 45)], fill=(180, 180, 180))
        draw.ellipse([clock_x - clock_r, clock_y - clock_r, clock_x + clock_r, clock_y + clock_r], fill=(230, 40, 40), outline=(255, 255, 255), width=4)
        draw.ellipse([clock_x - 34, clock_y - 34, clock_x + 34, clock_y + 34], fill=(255, 255, 255), outline=(30, 30, 30), width=2)
        font_cd = get_font(42, bold=True)
        draw.text((clock_x, clock_y), str(cd_rem), font=font_cd, fill=(20, 20, 20), anchor="mm")

        # Question Title in Header
        q_text = q_data.get("question", "WHO IS PREGNANT?")
        font_title_size = 60
        if len(q_text) > 35:
            font_title_size = 50
        if len(q_text) > 48:
            font_title_size = 42
        font_hdr = get_font(font_title_size, bold=True)
        available_width = w - 210
        while draw.textlength(q_text, font=font_hdr) > available_width and font_title_size > 12:
            font_title_size -= 1
            font_hdr = get_font(font_title_size, bold=True)
        title_x = (170 + w - 40) // 2
        draw.text((title_x + 3, header_h // 2 + 3), q_text, font=font_hdr, fill=(110, 10, 10), anchor="mm")
        draw.text((title_x, header_h // 2), q_text, font=font_hdr, fill=(255, 255, 255), anchor="mm")

        return canvas

    def _draw_mystery_boxes_169(self, draw: ImageDraw.ImageDraw, canvas: Image.Image, boxes: list[dict[str, Any]], is_rev: bool, bob: float):
        xs = [450, 960, 1470]
        for bi, b in enumerate(boxes[:3]):
            bx = xs[bi]
            by = int(320 + bob)
            bw, bh = 420, 420
            col = b.get("color", (46, 204, 113))
            
            # Box shadow & body
            draw.rounded_rectangle([bx - bw//2 + 4, by + 6, bx + bw//2 + 4, by + bh + 6], radius=32, fill=(0, 0, 0, 70))
            draw.rounded_rectangle([bx - bw//2, by, bx + bw//2, by + bh], radius=32, fill=(255, 255, 255), outline=col, width=8)
            
            # Big Ribbon
            draw.rectangle([bx - 30, by, bx + 30, by + bh], fill=col)
            draw.rectangle([bx - bw//2, by + bh//2 - 30, bx + bw//2, by + bh//2 + 30], fill=col)
            
            # Badge ID
            badge_r = 45
            draw.ellipse([bx - badge_r, by + bh//2 - badge_r, bx + badge_r, by + bh//2 + badge_r], fill=col, outline=(255, 255, 255), width=4)
            font_id = get_font(52, bold=True)
            draw.text((bx, by + bh//2), b["id"], font=font_id, fill=(255, 255, 255), anchor="mm")
            
            # If revealed, draw reward popping above box
            if is_rev:
                rw = b.get("reward", "")
                draw.rounded_rectangle([bx - 190, by - 80, bx + 190, by + 10], radius=20, fill=col, outline=(255, 255, 255), width=4)
                font_rw = get_font(34, bold=True)
                draw.text((bx, by - 35), rw, font=font_rw, fill=(255, 255, 255), anchor="mm")

    def _draw_mystery_boxes_916(self, draw: ImageDraw.ImageDraw, canvas: Image.Image, boxes: list[dict[str, Any]], is_rev: bool, bob: float):
        ys = [480, 740, 1000]
        for bi, b in enumerate(boxes[:3]):
            bx = 540
            by = int(ys[bi] + bob)
            bw, bh = 760, 210
            col = b.get("color", (46, 204, 113))
            
            draw.rounded_rectangle([bx - bw//2, by, bx + bw//2, by + bh], radius=24, fill=(255, 255, 255), outline=col, width=6)
            draw.rectangle([bx - 20, by, bx + 20, by + bh], fill=col)
            
            font_id = get_font(42, bold=True)
            txt = f"HỘP {b['id']} ({b.get('color_name', '')})"
            if is_rev:
                txt += f": {b.get('reward', '')}"
            draw.text((bx, by + bh//2), txt, font=font_id, fill=(30, 30, 40) if not is_rev else col, anchor="mm")

    def _draw_word_tiles_169(self, draw: ImageDraw.ImageDraw, rows: list[list[tuple[str, bool]]], is_rev: bool, bob: float):
        base_y = int(360 + bob)
        for ri, row in enumerate(rows):
            n_tiles = len(row)
            tile_s = 140
            gap = 24
            total_w = n_tiles * tile_s + (n_tiles - 1) * gap
            start_x = (self.width - total_w) // 2
            curr_y = base_y + ri * (tile_s + 40)
            
            for ti, (letter, given) in enumerate(row):
                tx = start_x + ti * (tile_s + gap)
                # Tile 3D block
                draw.rounded_rectangle([tx + 4, curr_y + 6, tx + tile_s + 4, curr_y + tile_s + 6], radius=20, fill=(0, 0, 0, 70))
                draw.rounded_rectangle([tx, curr_y, tx + tile_s, curr_y + tile_s], radius=20, fill=(255, 255, 255), outline=(240, 200, 50), width=5)
                
                show_letter = given or is_rev
                if show_letter:
                    font_tile = get_font(72, bold=True)
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), letter, font=font_tile, fill=(30, 30, 40) if given else (46, 204, 113), anchor="mm")
                else:
                    font_q = get_font(60, bold=True)
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), "?", font=font_q, fill=(200, 200, 200), anchor="mm")

    def _draw_word_tiles_916(self, draw: ImageDraw.ImageDraw, rows: list[list[tuple[str, bool]]], is_rev: bool, bob: float):
        base_y = int(580 + bob)
        for ri, row in enumerate(rows):
            n_tiles = len(row)
            tile_s = min(150, (900 - (n_tiles - 1) * 16) // n_tiles)
            gap = 16
            total_w = n_tiles * tile_s + (n_tiles - 1) * gap
            start_x = (self.width - total_w) // 2
            curr_y = base_y + ri * (tile_s + 36)
            
            for ti, (letter, given) in enumerate(row):
                tx = start_x + ti * (tile_s + gap)
                draw.rounded_rectangle([tx, curr_y, tx + tile_s, curr_y + tile_s], radius=18, fill=(255, 255, 255), outline=(240, 200, 50), width=4)
                show_letter = given or is_rev
                if show_letter:
                    font_tile = get_font(int(tile_s * 0.55), bold=True)
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), letter, font=font_tile, fill=(30, 30, 40) if given else (46, 204, 113), anchor="mm")
                else:
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), "?", font=get_font(int(tile_s * 0.5), bold=True), fill=(180, 180, 180), anchor="mm")

    def _draw_this_or_that_169(self, draw: ImageDraw.ImageDraw, a: dict[str, Any], b: dict[str, Any], bob: float, t: float):
        # Left Side A
        draw.rounded_rectangle([220, int(280 + bob), 880, int(720 + bob)], radius=32, fill=a.get("color", (46, 204, 113)), outline=(255, 255, 255), width=6)
        name_a = a["name"]
        fsize_a = 48
        while fsize_a >= 26:
            bbox_a = draw.textbbox((0, 0), name_a, font=get_font(fsize_a, bold=True))
            if (bbox_a[2] - bbox_a[0]) <= 560:
                break
            fsize_a -= 2
        draw.text((550, int(460 + bob)), name_a, font=get_font(fsize_a, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.rounded_rectangle([380, int(570 + bob), 720, int(660 + bob)], radius=24, fill=(255, 255, 255), outline=(30, 30, 30), width=3)
        act_a = a.get("action", "HIT LIKE" if self.is_english else "BẤM LIKE")
        draw.text((550, int(615 + bob)), act_a, font=get_font(36, bold=True), fill=(30, 30, 30), anchor="mm")
        
        # Right Side B
        draw.rounded_rectangle([1040, int(280 - bob), 1700, int(720 - bob)], radius=32, fill=b.get("color", (230, 126, 34)), outline=(255, 255, 255), width=6)
        name_b = b["name"]
        fsize_b = 48
        while fsize_b >= 26:
            bbox_b = draw.textbbox((0, 0), name_b, font=get_font(fsize_b, bold=True))
            if (bbox_b[2] - bbox_b[0]) <= 560:
                break
            fsize_b -= 2
        draw.text((1370, int(460 - bob)), name_b, font=get_font(fsize_b, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.rounded_rectangle([1200, int(570 - bob), 1540, int(660 - bob)], radius=24, fill=(255, 255, 255), outline=(30, 30, 30), width=3)
        act_b = b.get("action", "LEAVE COMMENT" if self.is_english else "BÌNH LUẬN")
        draw.text((1370, int(615 - bob)), act_b, font=get_font(34, bold=True), fill=(30, 30, 30), anchor="mm")
        
        # Center VS Badge with Pulsating Aura
        vs_r = int(75 + 8 * math.sin(t * 6.0))
        draw.ellipse([960 - vs_r, 500 - vs_r, 960 + vs_r, 500 + vs_r], fill=(231, 76, 60), outline=(255, 255, 255), width=6)
        draw.text((960, 500), "VS", font=get_font(60, bold=True), fill=(255, 255, 255), anchor="mm")

    def _draw_this_or_that_916(self, draw: ImageDraw.ImageDraw, a: dict[str, Any], b: dict[str, Any], bob: float, t: float):
        # Top Side A
        draw.rounded_rectangle([100, 480, 980, 800], radius=28, fill=a.get("color", (46, 204, 113)), outline=(255, 255, 255), width=6)
        name_a = a["name"]
        fsize_a = 44
        while fsize_a >= 24:
            bbox_a = draw.textbbox((0, 0), name_a, font=get_font(fsize_a, bold=True))
            if (bbox_a[2] - bbox_a[0]) <= 820:
                break
            fsize_a -= 2
        draw.text((540, 600), name_a, font=get_font(fsize_a, bold=True), fill=(255, 255, 255), anchor="mm")
        act_a = a.get("action", "HIT LIKE" if self.is_english else "BẤM LIKE")
        draw.text((540, 720), act_a, font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")
        
        # Bottom Side B
        draw.rounded_rectangle([100, 880, 980, 1200], radius=28, fill=b.get("color", (230, 126, 34)), outline=(255, 255, 255), width=6)
        name_b = b["name"]
        fsize_b = 44
        while fsize_b >= 24:
            bbox_b = draw.textbbox((0, 0), name_b, font=get_font(fsize_b, bold=True))
            if (bbox_b[2] - bbox_b[0]) <= 820:
                break
            fsize_b -= 2
        draw.text((540, 1000), name_b, font=get_font(fsize_b, bold=True), fill=(255, 255, 255), anchor="mm")
        act_b = b.get("action", "LEAVE COMMENT" if self.is_english else "BÌNH LUẬN")
        draw.text((540, 1120), act_b, font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")
        
        # Center VS
        vs_r = 55
        draw.ellipse([540 - vs_r, 840 - vs_r, 540 + vs_r, 840 + vs_r], fill=(231, 76, 60), outline=(255, 255, 255), width=5)
        draw.text((540, 840), "VS", font=get_font(44, bold=True), fill=(255, 255, 255), anchor="mm")

    def _normalize_choices(self, q_data: dict[str, Any]) -> list[tuple[str, str]]:
        raw_choices = q_data.get("choices") or []
        normalized: list[tuple[str, str]] = []
        for item in raw_choices:
            if isinstance(item, dict):
                cid = str(item.get("id") or "")
                ctext = str(item.get("text") or "")
                normalized.append((cid, ctext))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                normalized.append((str(item[0]), str(item[1])))
            elif isinstance(item, str):
                normalized.append(("", item))
        return normalized

    def _get_correct_id(self, q_data: dict[str, Any]) -> str:
        return str(q_data.get("correct_id") or q_data.get("correct_choice_id") or "A")

    def _draw_anime_character_169(self, draw: ImageDraw.ImageDraw, canvas: Image.Image, q_data: dict[str, Any], is_rev: bool, is_cd: bool, cd_elapsed: float, bob: float, t: float, rev_start: float):
        # Left Side: Clue Card OR Big Hero Illustration / Landmark Photo when revealed
        cached_rev = q_data.get("_cached_rev_169")
        rev_img_p = q_data.get("reveal_image_path")
        if is_rev and (cached_rev is not None or (rev_img_p and Path(rev_img_p).exists())):
            # Elastic Pop Scale Animation for Hero Reveal Illustration
            t_since_rev = max(0.0, t - rev_start)
            scale = max(0.1, min(1.0, t_since_rev * 3.5))

            # Modern Cyber Glass Card for Revealed Illustration / Landmark
            draw.rounded_rectangle([175 + 5, int(205 + bob) + 7, 875 + 5, int(835 + bob) + 7], radius=32, fill=(0, 0, 0, 95))
            draw.rounded_rectangle([175, int(205 + bob), 875, int(835 + bob)], radius=32, fill=(22, 29, 48), outline=(46, 204, 113), width=4)

            # Top Badge: Emerald Tag
            draw.rounded_rectangle([215, int(235 + bob), 485, int(285 + bob)], radius=14, fill=(46, 204, 113), outline=(255, 255, 255), width=2)
            draw.text((350, int(260 + bob)), "CORRECT ANSWER" if self.is_english else "ĐÁP ÁN ĐÚNG", font=get_font(20, bold=True), fill=(255, 255, 255), anchor="mm")

            if rev_img_p and Path(rev_img_p).exists():
                self._paste_reveal_slot(canvas, draw, rev_img_p, "16:9", scale, bob)
            elif cached_rev is not None:
                # Center Photo with Golden Trim & Shadow
                canvas.paste(cached_rev, (525 - cached_rev.width // 2, int(480 + bob - cached_rev.height // 2)), cached_rev)
            else:
                hero_raw = Image.open(rev_img_p).convert("RGBA")
                max_h = 360
                target_h = int(max_h * scale)
                target_w = int(hero_raw.width * (target_h / max(1, hero_raw.height)))
                hero_scaled = hero_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                hx = 525 - target_w // 2
                hy = int(680 + bob - target_h)
                canvas.paste(hero_scaled, (hx, hy), hero_scaled)

            # Bottom Answer Confirmation Tag
            draw.rounded_rectangle([215, int(715 + bob), 835, int(790 + bob)], radius=18, fill=(18, 24, 40), outline=(46, 204, 113), width=2)
            draw.text((525, int(752 + bob)), q_data.get("answer_text", ""), font=get_font(28, bold=True), fill=(255, 215, 0), anchor="mm")
        else:
            # Check if this question has a cached reveal illustration photo when revealed!
            cached_rev = q_data.get("_cached_rev_169")
            if is_rev and cached_rev is not None:
                # Left Hero / Clue Glass Card with Golden Photo Frame
                draw.rounded_rectangle([175 + 5, int(205 + bob) + 7, 875 + 5, int(835 + bob) + 7], radius=32, fill=(0, 0, 0, 95))
                draw.rounded_rectangle([175, int(205 + bob), 875, int(835 + bob)], radius=32, fill=(22, 29, 48), outline=(46, 204, 113), width=4)

                # Correct Tag (Top Left)
                draw.rounded_rectangle([215, int(235 + bob), 465, int(285 + bob)], radius=14, fill=(46, 204, 113), outline=(255, 255, 255), width=2)
                draw.text((340, int(260 + bob)), "CORRECT ANSWER" if self.is_english else "ĐÁP ÁN CHÍNH XÁC", font=get_font(20, bold=True), fill=(255, 255, 255), anchor="mm")

                # Center Photo with Golden Trim & Shadow
                canvas.paste(cached_rev, (525 - cached_rev.width // 2, int(480 + bob - cached_rev.height // 2)), cached_rev)

                # Bottom Answer Pill
                draw.rounded_rectangle([215, int(715 + bob), 835, int(790 + bob)], radius=18, fill=(18, 24, 40), outline=(46, 204, 113), width=2)
                draw.text((525, int(752 + bob)), q_data.get("answer_text", ""), font=get_font(28, bold=True), fill=(255, 215, 0), anchor="mm")
            else:
                # Check if there is a progressive unblur hero image for guessing!
                rev_img_p = q_data.get("reveal_image_path")
                if is_cd and rev_img_p and Path(rev_img_p).exists() and q_data.get("progressive_unblur"):
                    draw.rounded_rectangle([180, int(250 + bob), 880, int(740 + bob)], radius=32, fill=(255, 255, 255), outline=(240, 200, 50), width=6)
                    draw.text((530, int(285 + bob)), "AI ĐÂY NHỈ? (ĐANG RÕ DẦN)", font=get_font(28, bold=True), fill=(230, 126, 34), anchor="mm")
                    
                    blur_r = max(0, int(36 * (1.0 - cd_elapsed)))
                    hero_raw = Image.open(rev_img_p).convert("RGBA")
                    target_h = 390
                    target_w = int(hero_raw.width * (target_h / max(1, hero_raw.height)))
                    hero_scaled = hero_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                    if blur_r > 0:
                        hero_scaled = hero_scaled.filter(ImageFilter.GaussianBlur(radius=blur_r))
                    
                    hx = 530 - target_w // 2
                    hy = int(725 + bob - target_h)
                    canvas.paste(hero_scaled, (hx, hy), hero_scaled)
                else:
                    # Left Hero / Clue Glass Card (700x630px) - Cyber Dark Glassmorphism
                    draw.rounded_rectangle([175 + 5, int(205 + bob) + 7, 875 + 5, int(835 + bob) + 7], radius=32, fill=(0, 0, 0, 95))
                    draw.rounded_rectangle([175, int(205 + bob), 875, int(835 + bob)], radius=32, fill=(22, 29, 48), outline=(0, 220, 255), width=4)

                    # Category Tag (Top Left)
                    draw.rounded_rectangle([215, int(235 + bob), 485, int(290 + bob)], radius=16, fill=(231, 76, 60), outline=(255, 255, 255), width=2)
                    draw.text((350, int(262 + bob)), q_data.get("universe", "GENERAL KNOWLEDGE" if self.is_english else "ĐỐ VUI KIẾN THỨC"), font=get_font(22, bold=True), fill=(255, 255, 255), anchor="mm")

                    clues = q_data.get("clues", [])
                    if clues:
                        num_clues = len(clues[:3])
                        if num_clues == 1:
                            c = clues[0]
                            c_img = c.get("_cached_169")
                            if c_img is not None:
                                c_y = int(480 + bob - c_img.height // 2)
                                canvas.paste(c_img, (525 - c_img.width // 2, c_y), c_img)
                                draw.rounded_rectangle([215, int(670 + bob), 835, int(750 + bob)], radius=18, fill=(18, 24, 40), outline=(0, 220, 255), width=2)
                                paste_icon_with_text(canvas, draw, (525, int(710 + bob)), c.get("prompt", "WHICH COUNTRY IS THIS?"), get_font(24, bold=True), "point_right", icon_size=32, icon_side="right", fill=(0, 230, 255))
                            else:
                                # Glowing 3D Vector Quiz Crest (Question Orb)
                                orb_cx, orb_cy = 525, int(425 + bob)
                                for gr in range(110, 50, -10):
                                    draw.ellipse([orb_cx - gr, orb_cy - gr, orb_cx + gr, orb_cy + gr], fill=(0, 220, 255, 6))
                                draw.ellipse([orb_cx - 70, orb_cy - 70, orb_cx + 70, orb_cy + 70], fill=(30, 42, 70), outline=(255, 215, 0), width=4)
                                draw_comic_text(draw, (orb_cx, orb_cy), "?", font=get_font(80, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=4)

                                # Golden Clue Banner
                                draw.rounded_rectangle([215, int(545 + bob), 835, int(655 + bob)], radius=22, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                                draw_comic_text(draw, (525, int(600 + bob)), f"GỢI Ý: {c.get('word', '')}", font=get_font(40, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=3)

                                # Clean Guide Tag at Bottom with 3D pointing right icon!
                                draw.rounded_rectangle([215, int(690 + bob), 835, int(765 + bob)], radius=18, fill=(18, 24, 40), outline=(0, 220, 255), width=2)
                                guide_r = "CHOOSE THE ANSWER ON RIGHT" if self.is_english else "CHỌN ĐÁP ÁN BÊN PHẢI"
                                paste_icon_with_text(canvas, draw, (525, int(727 + bob)), guide_r, get_font(22 if self.is_english else 24, bold=True), "point_right", icon_size=32, icon_side="right", fill=(0, 230, 255))
                        elif num_clues == 2:
                            for ci, c in enumerate(clues[:2]):
                                cy = int(340 + ci * 140 + bob)
                                draw.rounded_rectangle([215, cy, 835, cy + 110], radius=22, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                                clue_lbl2 = f"HINT {ci+1}: " if self.is_english else f"GỢI Ý {ci+1}: "
                                draw_comic_text(draw, (525, cy + 55), f"{clue_lbl2}{c.get('word', '')}", font=get_font(38, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=3)
                            draw.rounded_rectangle([215, int(670 + bob), 835, int(745 + bob)], radius=18, fill=(18, 24, 40), outline=(0, 220, 255), width=2)
                            guide_r2 = "[ CHOOSE THE ANSWER ON RIGHT ]" if self.is_english else "[ CHỌN PHƯƠNG ÁN ĐÚNG BÊN PHẢI ]"
                            draw.text((525, int(707 + bob)), guide_r2, font=get_font(24, bold=True), fill=(0, 230, 255), anchor="mm")
                        else:
                            for ci, c in enumerate(clues[:3]):
                                cy = int(325 + ci * 130 + bob)
                                draw.rounded_rectangle([215, cy, 835, cy + 105], radius=20, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                                clue_lbl3 = f"HINT {ci+1}: " if self.is_english else f"GỢI Ý {ci+1}: "
                                draw_comic_text(draw, (525, cy + 52), f"{clue_lbl3}{c.get('word', '')}", font=get_font(34, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=3)
                    else:
                        orb_cx, orb_cy = 525, int(420 + bob)
                        for gr in range(110, 50, -10):
                            draw.ellipse([orb_cx - gr, orb_cy - gr, orb_cx + gr, orb_cy + gr], fill=(0, 220, 255, 6))
                        draw.ellipse([orb_cx - 70, orb_cy - 70, orb_cx + 70, orb_cy + 70], fill=(30, 42, 70), outline=(255, 215, 0), width=4)
                        draw_comic_text(draw, (orb_cx, orb_cy), "?", font=get_font(80, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=4)
                        draw.rounded_rectangle([215, int(550 + bob), 835, int(740 + bob)], radius=24, fill=(35, 46, 75), outline=(0, 220, 255), width=3)
                        no_clue_t = "CHOOSE THE CORRECT ANSWER" if self.is_english else "CHỌN ĐÁP ÁN ĐÚNG"
                        draw_comic_text(draw, (525, int(645 + bob)), no_clue_t, font=get_font(34 if self.is_english else 38, bold=True), fill=(255, 255, 255), stroke_color=(15, 18, 25), stroke_width=3)

        # Right Side: Multiple Choice Pills (eSports Cyber Capsules)
        choices = self._normalize_choices(q_data)
        correct_id = self._get_correct_id(q_data)
        num_c = len(choices)
        if num_c >= 4:
            py_start = 205
            gap_c = 158
            pill_h = 122
            font_t_size = 42
        else:
            py_start = 245
            gap_c = 180
            pill_h = 135
            font_t_size = 46

        for i, (cid, ctext) in enumerate(choices):
            cy = int(py_start + i * gap_c + bob)
            is_correct = (cid == correct_id)

            if is_rev:
                fill_c = (46, 204, 113) if is_correct else (34, 40, 56)
                outline_c = (255, 255, 255) if is_correct else (55, 65, 85)
                text_c = (255, 255, 255) if is_correct else (160, 170, 185)
            else:
                fill_c = (26, 34, 56)
                outline_c = (255, 215, 0)
                text_c = (255, 255, 255)

            draw.rounded_rectangle([925 + 5, cy + 6, 1865 + 5, cy + pill_h + 6], radius=26, fill=(0, 0, 0, 95))
            draw.rounded_rectangle([925, cy, 1865, cy + pill_h], radius=26, fill=fill_c, outline=outline_c, width=3)

            badge_cx = 995
            badge_cy = cy + pill_h // 2
            badge_fill = (46, 204, 113) if (is_rev and is_correct) else (231, 76, 60)
            draw.ellipse([badge_cx - 40, badge_cy - 40, badge_cx + 40, badge_cy + 40], fill=badge_fill, outline=(255, 255, 255), width=3)
            font_b = get_font(40, bold=True)
            if is_rev and is_correct:
                draw.line([(badge_cx - 15, badge_cy), (badge_cx - 4, badge_cy + 12), (badge_cx + 17, badge_cy - 11)], fill=(255, 255, 255), width=6)
            else:
                draw.text((badge_cx, badge_cy), cid, font=font_b, fill=(255, 255, 255), anchor="mm")

            font_t = get_font(font_t_size, bold=True)
            draw.text((1075, badge_cy), ctext, font=font_t, fill=text_c, anchor="lm")

    def _paste_reveal_slot(self, canvas, draw, path, aspect, scale=1.0, bob=0, blur=0):
        slot = image_slot("reveal", aspect)
        with Image.open(path) as source:
            raw = source.convert("RGBA")
        full_w, full_h = fitted_size(raw.size, slot.size)
        target_w, target_h = fitted_size(raw.size, slot.size, scale)
        x0, y0, x1, y1 = slot.box
        center_x = (x0 + x1) // 2
        center_y = (y0 + y1) // 2 + int(bob)
        # Legacy portrait/cutout: frame follows content, never a large white mat.
        # The full-size frame stays stable during the reveal animation.
        if aspect == "9:16":
            frame_w = max(360, full_w + 40)
            draw.rounded_rectangle([center_x - frame_w // 2, 440,
                                    center_x + frame_w // 2, y1 + 15], radius=24,
                                   fill=(22, 29, 48), outline=(46, 204, 113), width=4)
        hero = raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
        if blur:
            hero = hero.filter(ImageFilter.GaussianBlur(radius=blur))
        canvas.paste(hero, (center_x - target_w // 2, center_y - target_h // 2), hero)

    def _draw_anime_character_916(self, draw: ImageDraw.ImageDraw, canvas: Image.Image, q_data: dict[str, Any], is_rev: bool, is_cd: bool, cd_elapsed: float, bob: float, t: float, rev_start: float, mascot_state: str = "WELCOME"):
        rev_img_p = q_data.get("reveal_image_path")
        if is_rev and rev_img_p and Path(rev_img_p).exists():
            t_since_rev = max(0.0, t - rev_start)
            scale = max(0.1, min(1.0, t_since_rev * 3.5))
            
            self._paste_reveal_slot(canvas, draw, rev_img_p, "9:16", scale, 0)
            rev_header_916 = "CORRECT!" if self.is_english else "CHÍNH XÁC!"
            draw.text((540, 475), rev_header_916, font=get_font(30, bold=True), fill=(46, 204, 113), anchor="mm")
            

        elif is_cd and rev_img_p and Path(rev_img_p).exists() and q_data.get("progressive_unblur"):
            self._paste_reveal_slot(canvas, draw, rev_img_p, "9:16", 1, 0,
                                    blur=max(0, int(36 * (1.0 - cd_elapsed))))
            unblur_txt = "WHO IS THIS? (REVEALING)" if self.is_english else "AI ĐÂY NHỈ? (ĐANG RÕ DẦN)"
            draw.text((540, 475), unblur_txt, font=get_font(26 if self.is_english else 28, bold=True), fill=(230, 126, 34), anchor="mm")
            

        else:
            cached_rev_916 = q_data.get("_cached_rev_916")
            if is_rev and cached_rev_916 is not None:
                draw.rounded_rectangle([60 + 4, int(430 + bob) + 6, 1020 + 4, int(820 + bob) + 6], radius=30, fill=(0, 0, 0, 95))
                draw.rounded_rectangle([60, int(430 + bob), 1020, int(820 + bob)], radius=30, fill=(22, 29, 48), outline=(46, 204, 113), width=4)

                # Correct Tag
                draw.rounded_rectangle([100, int(455 + bob), 360, int(505 + bob)], radius=14, fill=(46, 204, 113), outline=(255, 255, 255), width=2)
                draw.text((230, int(480 + bob)), "CORRECT ANSWER" if self.is_english else "ĐÁP ÁN ĐÚNG", font=get_font(20, bold=True), fill=(255, 255, 255), anchor="mm")

                # Center Photo
                canvas.paste(cached_rev_916, (540 - cached_rev_916.width // 2, int(615 + bob - cached_rev_916.height // 2)), cached_rev_916)

                # Bottom Answer Pill
                draw.rounded_rectangle([100, int(730 + bob), 980, int(795 + bob)], radius=16, fill=(18, 24, 40), outline=(46, 204, 113), width=2)
                draw.text((540, int(762 + bob)), q_data.get("answer_text", ""), font=get_font(26, bold=True), fill=(255, 215, 0), anchor="mm")
            else:
                clues = q_data.get("clues", [])
                if clues:
                    num_clues = len(clues[:3])
                    if num_clues == 1:
                        c = clues[0]
                        c_img = c.get("_cached_916")
                        if c_img is not None:
                            draw.rounded_rectangle([60 + 4, int(430 + bob) + 6, 1020 + 4, int(820 + bob) + 6], radius=30, fill=(0, 0, 0, 95))
                            draw.rounded_rectangle([60, int(430 + bob), 1020, int(820 + bob)], radius=30, fill=(22, 29, 48), outline=(0, 220, 255), width=4)
                            c_y = int(585 + bob - c_img.height // 2)
                            canvas.paste(c_img, (540 - c_img.width // 2, c_y), c_img)
                            draw.rounded_rectangle([120, int(725 + bob), 960, int(795 + bob)], radius=16, fill=(18, 24, 40), outline=(0, 220, 255), width=2)
                            paste_icon_with_text(canvas, draw, (540, int(760 + bob)), c.get("prompt", "WHICH COUNTRY IS THIS?"), get_font(22, bold=True), "point_down", icon_size=28, icon_side="right", fill=(0, 230, 255))
                        else:
                            draw.rounded_rectangle([60 + 4, int(430 + bob) + 6, 1020 + 4, int(820 + bob) + 6], radius=30, fill=(0, 0, 0, 95))
                            draw.rounded_rectangle([60, int(430 + bob), 1020, int(820 + bob)], radius=30, fill=(22, 29, 48), outline=(0, 220, 255), width=4)

                            orb_cx, orb_cy = 540, int(545 + bob)
                            for gr in range(100, 50, -10):
                                draw.ellipse([orb_cx - gr, orb_cy - gr, orb_cx + gr, orb_cy + gr], fill=(0, 220, 255, 7))
                            draw.ellipse([orb_cx - 65, orb_cy - 65, orb_cx + 65, orb_cy + 65], fill=(30, 42, 70), outline=(255, 215, 0), width=4)
                            draw_comic_text(draw, (orb_cx, orb_cy), "?", font=get_font(72, bold=True), fill=(255, 215, 0), stroke_width=3)

                            draw.rounded_rectangle([120, int(655 + bob), 960, int(755 + bob)], radius=20, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                            clue_pfx = "HINT: " if self.is_english else "GỢI Ý: "
                            draw_comic_text(draw, (540, int(705 + bob)), f"{clue_pfx}{c.get('word', '')}", font=get_font(40, bold=True), fill=(255, 215, 0), stroke_width=3)
                    elif num_clues == 2:
                        for ci, c in enumerate(clues[:2]):
                            cy = int(460 + ci * 135 + bob)
                            draw.rounded_rectangle([60, cy, 1020, cy + 110], radius=22, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                            clue_pfx2 = f"HINT {ci+1}: " if self.is_english else f"GỢI Ý {ci+1}: "
                            draw_comic_text(draw, (540, cy + 55), f"{clue_pfx2}{c.get('word', '')}", font=get_font(38, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=3)
                        draw.rounded_rectangle([100, int(740 + bob), 980, int(810 + bob)], radius=16, fill=(18, 24, 40), outline=(0, 220, 255), width=2)
                        guide_d = "CHOOSE THE ANSWER BELOW" if self.is_english else "CHỌN PHƯƠNG ÁN ĐÚNG DƯỚI ĐÂY"
                        paste_icon_with_text(canvas, draw, (540, int(775 + bob)), guide_d, get_font(22 if self.is_english else 24, bold=True), "point_down", icon_size=32, icon_side="right", fill=(0, 230, 255))
                    else:
                        for ci, c in enumerate(clues[:3]):
                            cy = int(440 + ci * 115 + bob)
                            draw.rounded_rectangle([60, cy, 1020, cy + 95], radius=20, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                            clue_pfx3 = f"HINT {ci+1}: " if self.is_english else f"GỢI Ý {ci+1}: "
                            draw_comic_text(draw, (540, cy + 47), f"{clue_pfx3}{c.get('word', '')}", font=get_font(34, bold=True), fill=(255, 215, 0), stroke_color=(15, 18, 25), stroke_width=3)
                else:
                    draw.rounded_rectangle([60 + 4, int(430 + bob) + 6, 1020 + 4, int(820 + bob) + 6], radius=30, fill=(0, 0, 0, 95))
                draw.rounded_rectangle([60, int(430 + bob), 1020, int(820 + bob)], radius=30, fill=(22, 29, 48), outline=(0, 220, 255), width=4)

                orb_cx, orb_cy = 540, int(545 + bob)
                for gr in range(100, 50, -10):
                    draw.ellipse([orb_cx - gr, orb_cy - gr, orb_cx + gr, orb_cy + gr], fill=(0, 220, 255, 7))
                draw.ellipse([orb_cx - 65, orb_cy - 65, orb_cx + 65, orb_cy + 65], fill=(30, 42, 70), outline=(255, 215, 0), width=4)
                draw_comic_text(draw, (orb_cx, orb_cy), "?", font=get_font(72, bold=True), fill=(255, 215, 0), stroke_width=3)

                draw.rounded_rectangle([120, int(655 + bob), 960, int(755 + bob)], radius=20, fill=(35, 46, 75), outline=(255, 215, 0), width=3)
                no_clue_916 = "CHOOSE THE CORRECT ANSWER" if self.is_english else "CHỌN ĐÁP ÁN ĐÚNG"
                draw_comic_text(draw, (540, int(705 + bob)), no_clue_916, font=get_font(36 if self.is_english else 38, bold=True), fill=(255, 255, 255), stroke_width=3)

        # Bottom: Choices (Cyber Capsules in 9:16)
        choices = self._normalize_choices(q_data)
        correct_id = self._get_correct_id(q_data)
        num_c = len(choices)
        if num_c >= 4:
            py_start = 855
            gap_c = 125
            pill_h = 100
            font_size_t = 38
        else:
            py_start = 880
            gap_c = 145
            pill_h = 115
            font_size_t = 42

        if rev_img_p and Path(rev_img_p).exists() and (is_rev or (is_cd and q_data.get("progressive_unblur"))):
            py_start = image_slot("reveal", "9:16").box[3] + 50
            gap_c = 120
            pill_h = 100

        for i, (cid, ctext) in enumerate(choices):
            cy = int(py_start + i * gap_c + bob)
            is_correct = (cid == correct_id)
            if is_rev:
                fill_c = (46, 204, 113) if is_correct else (34, 40, 56)
                outline_c = (255, 255, 255) if is_correct else (55, 65, 85)
                text_c = (255, 255, 255) if is_correct else (160, 170, 185)
            else:
                fill_c = (26, 34, 56)
                outline_c = (255, 215, 0)
                text_c = (255, 255, 255)

            draw.rounded_rectangle([60 + 4, cy + 5, 1020 + 4, cy + pill_h + 5], radius=24, fill=(0, 0, 0, 95))
            draw.rounded_rectangle([60, cy, 1020, cy + pill_h], radius=24, fill=fill_c, outline=outline_c, width=3)

            badge_cx = 135
            badge_cy = cy + pill_h // 2
            badge_fill = (46, 204, 113) if (is_rev and is_correct) else (231, 76, 60)
            draw.ellipse([badge_cx - 36, badge_cy - 36, badge_cx + 36, badge_cy + 36], fill=badge_fill, outline=(255, 255, 255), width=3)
            if is_rev and is_correct:
                draw.line([(badge_cx - 14, badge_cy), (badge_cx - 3, badge_cy + 11), (badge_cx + 15, badge_cy - 10)], fill=(255, 255, 255), width=5)
            else:
                draw.text((badge_cx, badge_cy), cid, font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")
            draw.text((210, badge_cy), ctext, font=get_font(font_size_t, bold=True), fill=text_c, anchor="lm")

    def _draw_timer_bar(self, draw: ImageDraw.ImageDraw, canvas: Image.Image, x: int, y: int, w: int, h: int, progress: float, t: float):
        # Cyber Dark Glass Track
        draw.rounded_rectangle([x + 4, y + 5, x + w + 4, y + h + 5], radius=36, fill=(0, 0, 0, 95))
        draw.rounded_rectangle([x, y, x + w, y + h], radius=36, fill=(18, 24, 38), outline=(0, 220, 255), width=3)

        elapsed = max(0.01, min(1.0, 1.0 - progress))
        fill_w = int(w * elapsed)

        # Color shifts dynamically: Neon Green -> Gold -> Red when urgency < 1.5s
        if progress < 0.25:
            bar_color = (231, 76, 60)
        elif progress < 0.5:
            bar_color = (241, 196, 15)
        else:
            bar_color = (0, 230, 118)

        r_bar = min(36, (h - 2) // 2)
        if fill_w >= 2 * r_bar + 2:
            draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=r_bar, fill=bar_color)
        elif fill_w > 0:
            draw.rectangle([x, y, x + fill_w, y + h], fill=bar_color)

        clock_paste = self.clock_icon
        if progress < 0.4:
            wobble = 14 * math.sin(t * 25.0)
            clock_paste = self.clock_icon.rotate(wobble, resample=Image.Resampling.BICUBIC, expand=True)

        clock_cx = x + fill_w
        clock_x = int(clock_cx - clock_paste.width / 2)
        clock_y = int(y + (h - clock_paste.height) / 2)
        canvas.paste(clock_paste, (clock_x, clock_y), clock_paste)

    def _draw_reveal_bar(self, draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, text: str, t: float, rev_start: float):
        t_rev = max(0.0, t - rev_start)
        scale = max(0.1, min(1.0, t_rev * 4.0))
        cur_w = max(100, int(w * scale))
        cur_h = max(50, int(h * scale))
        cur_x = x + (w - cur_w) // 2
        cur_y = y + (h - cur_h) // 2
        r_rev = min(24, max(1, min(cur_w, cur_h) // 2))
        
        draw.rounded_rectangle([cur_x + 4, cur_y + 6, cur_x + cur_w + 4, cur_y + cur_h + 6], radius=r_rev, fill=(0, 0, 0, 75))
        draw.rounded_rectangle([cur_x, cur_y, cur_x + cur_w, cur_y + cur_h], radius=r_rev, fill=(46, 204, 113), outline=(255, 255, 255), width=5)
        
        cx = cur_x + (45 if self.opt.aspect_ratio == "9:16" else 65)
        cy = cur_y + cur_h // 2
        draw.line([(cx - 14, cy + 2), (cx - 4, cy + 12), (cx + 18, cy - 10)], fill=(255, 255, 255), width=6)
        
        ans_prefix = "ANSWER: " if self.is_english else "ĐÁP ÁN: "
        full_ans_txt = f"{ans_prefix}{text}"
        max_text_w = max(50, cur_w - 130)
        base_size = 34 if self.opt.aspect_ratio == "9:16" else 46
        font_size = base_size
        while font_size >= 18:
            font_cand = get_font(font_size, bold=True)
            bbox = draw.textbbox((0, 0), full_ans_txt, font=font_cand)
            if (bbox[2] - bbox[0]) <= max_text_w:
                break
            font_size -= 2
        font_rev = get_font(font_size, bold=True)
        bbox = draw.textbbox((0, 0), full_ans_txt, font=font_rev)
        if (bbox[2] - bbox[0]) > max_text_w:
            while len(full_ans_txt) > 8 and draw.textbbox((0, 0), full_ans_txt + "...", font=font_rev)[2] > max_text_w:
                full_ans_txt = full_ans_txt[:-1]
            full_ans_txt = full_ans_txt + "..."
        draw.text((cx + 35, cy), full_ans_txt, font=font_rev, fill=(255, 255, 255), anchor="lm")

    def _mux_audio_and_video(self, video_file: Path, voice_files: dict[str, Path], sfx_files: dict[str, Path], total_dur: float, events: list[dict[str, Any]], output_file: Path):
        sr = 48000
        n_samples = int(math.ceil(total_dur * sr)) + sr
        voice_track = np.zeros((n_samples, 2), dtype=np.float32)
        sfx_track = np.zeros((n_samples, 2), dtype=np.float32)

        def _load_wav_to_stereo(path: Path) -> np.ndarray:
            try:
                with wave.open(str(path), "rb") as wf:
                    n_ch = wf.getnchannels()
                    sw = wf.getsampwidth()
                    orig_sr = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                if sw == 2:
                    raw = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                elif sw == 1:
                    raw = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128.0
                else:
                    raw = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0

                if n_ch == 1:
                    stereo = np.column_stack([raw, raw])
                else:
                    stereo = raw.reshape(-1, n_ch)
                    if n_ch > 2:
                        stereo = stereo[:, :2]

                if orig_sr != sr and len(stereo) > 0:
                    num_target = int(len(stereo) * (sr / orig_sr))
                    t_orig = np.linspace(0, 1, len(stereo))
                    t_target = np.linspace(0, 1, num_target)
                    ch0 = np.interp(t_target, t_orig, stereo[:, 0])
                    ch1 = np.interp(t_target, t_orig, stereo[:, 1])
                    stereo = np.column_stack([ch0, ch1])
                return stereo.astype(np.float32)
            except Exception:
                return np.zeros((0, 2), dtype=np.float32)

        def _paste_audio(target_track: np.ndarray, path: Path, time_s: float, vol: float = 1.0):
            clip = _load_wav_to_stereo(path)
            if len(clip) == 0:
                return
            start_idx = max(0, int(round(time_s * sr)))
            end_idx = min(len(target_track), start_idx + len(clip))
            if start_idx < len(target_track):
                clip_slice = clip[: end_idx - start_idx] * vol
                target_track[start_idx:end_idx] += clip_slice

        # 1. Fast Assembly of Voice and SFX
        _paste_audio(voice_track, voice_files["intro"], 0.0, vol=1.0)
        for i in range(1, len(events) - 1):
            ev = events[i]
            _paste_audio(voice_track, voice_files[f"q{i}_q"], ev["q_start"], vol=1.0)
            _paste_audio(sfx_track, sfx_files["countdown"], ev["cd_start"], vol=0.85)
            _paste_audio(sfx_track, sfx_files["ding"], ev["rev_start"], vol=0.95)
            _paste_audio(voice_track, voice_files[f"q{i}_a"], ev["rev_start"] + 0.1, vol=1.0)
        _paste_audio(voice_track, voice_files["outro"], events[-1]["start"], vol=1.0)

        # 2. BGM track with smart ducking
        bgm_clip = _load_wav_to_stereo(sfx_files["bgm"])
        bgm_track = np.zeros((n_samples, 2), dtype=np.float32)
        if len(bgm_clip) > 0:
            repeats = int(math.ceil(n_samples / len(bgm_clip)))
            tiled = np.tile(bgm_clip, (repeats, 1))[:n_samples]
            voice_mag = np.abs(voice_track[:, 0]) + np.abs(voice_track[:, 1])
            win_size = int(sr * 0.25)
            if len(voice_mag) > win_size:
                kernel = np.ones(win_size, dtype=np.float32) / win_size
                voice_env = np.convolve(voice_mag, kernel, mode="same")
            else:
                voice_env = voice_mag
            duck_factor = np.clip(1.0 - (voice_env * 4.0), 0.15, 0.40)
            bgm_track = tiled * duck_factor[:, np.newaxis]

        # 3. Normalized Master Audio Mix
        final_audio = voice_track * 1.0 + sfx_track * 0.95 + bgm_track
        max_val = float(np.max(np.abs(final_audio))) if len(final_audio) > 0 else 0.0
        if max_val > 0.98:
            final_audio = final_audio * (0.95 / max_val)

        master_wav_p = output_file.parent / f"master_audio_cache_{output_file.stem}.wav"
        int16_audio = (np.clip(final_audio, -0.98, 0.98) * 32767.0).astype(np.int16)
        with wave.open(str(master_wav_p), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(int16_audio.tobytes())

        # 4. Instant Remux via FFmpeg copy (takes ~2s)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_file),
            "-i", str(master_wav_p),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_file)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if master_wav_p.exists():
            try:
                master_wav_p.unlink()
            except Exception:
                pass

        if res.returncode != 0:
            print("Audio Mux Error:", res.stderr[-1000:])
            raise RuntimeError(f"Audio Mux Error (exit {res.returncode}): {res.stderr[-500:]}")


# -------------------------------------------------------------
# 7. CLI ENTRYPOINT
# -------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quiz Video Engine 2.0 Enterprise Stack")
    parser.add_argument("--preset", choices=["onepiece_theme", "emoji_rebus", "mystery_box", "this_or_that", "gameshow_arena"], default=None, help="Smart 1-Click Production Preset")
    parser.add_argument("--source", choices=["bank", "ai_cliproxy"], default="bank", help="Script & Asset source")
    parser.add_argument("--type", choices=list(REBUS_BANK.keys()) + ["all"], default="emoji_rebus", help="Question archetype")
    parser.add_argument("--topic", default="Ẩm thực đường phố Việt Nam", help="Topic for AI generation")
    parser.add_argument("--count", type=int, default=3, help="Number of questions to generate")
    parser.add_argument("--aspect", choices=["16:9", "9:16", "both"], default="both", help="Output aspect ratio")
    parser.add_argument("--llm_model", default="gemini-3.6-flash-high", help="CLIProxy LLM Model")
    parser.add_argument("--image_model", default="gpt-image-2", help="CLIProxy Image Model (gpt-image-2 / gemini-3.1-flash-image)")
    parser.add_argument("--tts", choices=["vieneu", "piper", "edge"], default="vieneu", help="TTS Engine (vieneu neural, piper offline or edge-tts)")
    parser.add_argument("--vieneu_voice", default="Ngọc Huyền", help="VieNeu voice name (Ngọc Huyền, Thanh Bình, Trúc Ly...)")
    parser.add_argument("--piper_voice", choices=["minh_khang", "ngoc_huyen_moi", "ngocngan3701", "manh_dung", "nguyet_nga"], default="minh_khang", help="Piper voice model name")
    parser.add_argument("--piper_speed", type=float, default=1.05, help="Piper speech speed multiplier")
    parser.add_argument("--voice", default="vi-VN-HoaiMyNeural", help="Edge-TTS voice name")
    parser.add_argument("--mascot", choices=["loc", "my", "rabbit"], default="loc", help="Channel Host Mascot (loc / my from Hoat-Hinh or classic rabbit)")
    parser.add_argument("--bg_image", default=None, help="Path to custom image background (e.g. Wano, Pirate Island, Anime Room)")
    parser.add_argument("--bg_theme", choices=["auto", "orange", "blue", "purple", "forest", "dark_gold"], default="auto", help="Procedural background color theme")
    parser.add_argument("--output_dir", default="output/quiz_v2_enterprise", help="Target output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ai_assets_dir = out_dir / "ai_assets"
    ai_assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Handle Smart 1-Click Production Presets
    if args.preset == "gameshow_arena":
        print("[Smart Preset] Launching 'ĐẤU TRƯỜNG TRÍ TUỆ' (Gameshow Multi-Round Masterpiece)...")
        from render_masterpiece_full_pipeline import MasterpieceVideoRenderer
        from produce_masterpiece_video import MASTERPIECE_QUESTIONS
        aspects = ["16:9", "9:16"] if args.aspect == "both" else [args.aspect]
        for aspect in aspects:
            aspect_clean = aspect.replace(":", "_")
            out_f = out_dir / f"gameshow_arena_{aspect_clean}.mp4"
            renderer = MasterpieceVideoRenderer(aspect_ratio=aspect, fps=30)
            renderer.render_masterpiece(MASTERPIECE_QUESTIONS, out_f)
        return

    if args.preset == "onepiece_theme":
        args.type = "anime_character"
        args.mascot = "loc"
        args.tts = "vieneu"
        args.vieneu_voice = "Thanh Bình"
        if not args.bg_image:
            args.bg_image = "assets/backgrounds_custom/bg_onepiece_wano.png"
    elif args.preset == "mystery_box":
        args.type = "mystery_box"
        args.mascot = "loc"
        args.tts = "vieneu"
        args.vieneu_voice = "Thanh Bình"
        if not args.bg_image:
            args.bg_image = "D:/ALL AI/TestProjects/Hoat-Hinh/assets/backgrounds/voxel_islands/island_cozy_sunset_cafe_deck.png"
    elif args.preset == "this_or_that":
        args.type = "this_or_that"
        args.mascot = "my"
        args.tts = "vieneu"
        args.vieneu_voice = "Ngọc Huyền"
        if not args.bg_image:
            args.bg_image = "D:/ALL AI/TestProjects/Hoat-Hinh/assets/backgrounds/voxel_islands/island_vietnam_night_market.png"
    elif args.preset == "emoji_rebus":
        args.type = "emoji_rebus"
        args.mascot = "my"
        args.tts = "vieneu"
        args.vieneu_voice = "Ngọc Huyền"

    if args.source == "ai_cliproxy":
        print(f"[AI Mode] Generating {args.count} quiz questions via LLM ({args.llm_model})...")
        units = asyncio.run(generate_ai_quiz_script(topic=args.topic, count=args.count, archetype=args.type, model=args.llm_model))
        print(f"[AI Mode] Generating 3D Sticker Clues via AI Image ({args.image_model}) in parallel...")
        
        import hashlib
        async def fetch_all_clues():
            tasks = []
            for q in units:
                for ci, c in enumerate(q.get("clues", [])):
                    h = hashlib.md5(c["image_prompt"].encode()).hexdigest()[:10]
                    p_out = ai_assets_dir / f"clue_{h}.png"
                    c["image_path"] = str(p_out)
                    tasks.append(generate_ai_image_asset(c["image_prompt"], p_out, model=args.image_model))
            await asyncio.gather(*tasks)
            
        asyncio.run(fetch_all_clues())
    else:
        if args.type == "all":
            units = []
            for k, v in REBUS_BANK.items():
                units.extend(v)
            units = units[:args.count]
        else:
            units = REBUS_BANK[args.type][:args.count]

    aspects = ["16:9", "9:16"] if args.aspect == "both" else [args.aspect]
    
    for aspect in aspects:
        aspect_clean = aspect.replace(":", "_")
        out_file = out_dir / f"quiz_{args.type}_{aspect_clean}.mp4"
        options = QuizRenderOptions(
            aspect_ratio=aspect,
            fps=30,
            tts_engine=args.tts,
            vieneu_voice=args.vieneu_voice,
            piper_voice=args.piper_voice,
            piper_speed=args.piper_speed,
            voice_name=args.voice,
            mascot_type=args.mascot,
            bg_image=args.bg_image,
            bg_theme=args.bg_theme,
            output_path=out_file,
            image_model=args.image_model
        )
        engine = QuizVideoEngineV2(options)
        engine.render_quiz_video(units)


if __name__ == "__main__":
    main()
