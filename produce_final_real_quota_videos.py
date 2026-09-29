#!/usr/bin/env python3
"""
Master Production Exporter for Real-Quota AI Quiz Video
Topic: Món Ăn Vặt & Đồ Uống Hot Trend Giới Trẻ 2026
Using Real AI-Generated 3D Stickers from gpt-image-2 & Scripts from gemini-3.6-flash-high.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

from app.services.quiz_engine_v2 import (
    QuizRenderOptions,
    QuizVideoEngineV2,
)

OUTPUT_DIR = Path("output/real_quota_ai_production")
ASSETS_DIR = OUTPUT_DIR / "ai_stickers"
FINAL_DIR = OUTPUT_DIR / "final"
PREVIEWS_DIR = OUTPUT_DIR / "previews"

for d in [OUTPUT_DIR, ASSETS_DIR, FINAL_DIR, PREVIEWS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 3 Real AI Questions generated via gemini-3.6-flash-high & gpt-image-2
REAL_AI_QUESTIONS = [
    {
        "id": "ai_tra_sua",
        "question": "ĐOÁN TÊN THỨC UỐNG QUEN THUỘC CỦA GIỚI TRẺ",
        "clues": [
            {
                "word": "TRÀ",
                "image_path": str(ASSETS_DIR / "sticker_trà_08cf095404.png"),
                "color": (46, 204, 113)
            },
            {
                "word": "SỮA",
                "image_path": str(ASSETS_DIR / "sticker_sữa_949d6a2e20.png"),
                "color": (241, 196, 15)
            }
        ],
        "answer_text": "TRÀ SỮA",
        "voice_q": "Câu hỏi số 1: Tách trà xanh thơm lừng ghép với hộp sữa tươi béo ngậy, đây là thức uống ruột nào của giới trẻ?",
        "voice_a": "Chính xác rồi! Đó chính là món Trà Sữa thơm ngon giải khát!",
    },
    {
        "id": "ai_banh_mi",
        "question": "MÓN ĂN ĐƯỜNG PHỐ VIỆT NAM NỔI TIẾNG THẾ GIỚI",
        "clues": [
            {
                "word": "BÁNH",
                "image_path": str(ASSETS_DIR / "sticker_bánh_a6c1786afd.png"),
                "color": (230, 126, 34)
            },
            {
                "word": "MÌ",
                "image_path": str(ASSETS_DIR / "sticker_mì_d34b7e9621.png"),
                "color": (231, 76, 60)
            }
        ],
        "answer_text": "BÁNH MÌ",
        "voice_q": "Câu đố số 2: Một chiếc bánh ngọt kết hợp với bát mì sợi vàng óng, ra ngay món ăn sáng huyền thoại nào?",
        "voice_a": "Chuẩn luôn bạn ơi! Bánh cộng Mì chính là Bánh Mì Việt Nam!",
    },
    {
        "id": "ai_bap_bo",
        "question": "MÓN ĂN VẶT XEM PHIM KHÔNG THỂ THIẾU",
        "clues": [
            {
                "word": "BẮP",
                "image_path": str(ASSETS_DIR / "sticker_bắp_ba5e0a870c.png"),
                "color": (241, 196, 15)
            },
            {
                "word": "BƠ",
                "image_path": str(ASSETS_DIR / "sticker_bơ_1b121e5463.png"),
                "color": (243, 156, 18)
            }
        ],
        "answer_text": "BẮP RANG BƠ",
        "voice_q": "Câu số 3: Bắp ngô vàng ngọt ngào kết hợp với miếng bơ thơm lừng béo ngậy, đố bạn đây là món gì?",
        "voice_a": "Quá xuất sắc! Đó chính là món Bắp Rang Bơ giòn tan thơm phức!",
    }
]


def main():
    print("================================================================")
    print("🎬 BẮT ĐẦU XUẤT BẢN VIDEO THỰC TẾ GỌI QUOTA AI CHO BOSS")
    print("================================================================")
    
    # 1. Render 16:9 Long-Form Master Video (Piper Voice: Minh Khang)
    t0 = time.time()
    mp4_16_9 = FINAL_DIR / "quiz_mon_an_vat_2026_16_9.mp4"
    print("\n[1/2] Đang render bản Master 16:9 (1920x1080 @ 30fps, Piper: Minh Khang)...")
    opt_16_9 = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        tts_engine="piper",
        piper_voice="minh_khang",
        piper_speed=1.05,
        output_path=mp4_16_9
    )
    engine_16_9 = QuizVideoEngineV2(opt_16_9)
    engine_16_9.render_quiz_video(REAL_AI_QUESTIONS)
    print(f"-> Hoàn tất 16:9 trong {time.time()-t0:.2f}s! Kích thước: {mp4_16_9.stat().st_size / (1024*1024):.2f} MB")

    # 2. Render 9:16 Shorts/TikTok Master Video (Piper Voice: Ngọc Huyền)
    t1 = time.time()
    mp4_9_16 = FINAL_DIR / "quiz_mon_an_vat_2026_9_16_shorts.mp4"
    print("\n[2/2] Đang render bản Shorts 9:16 (1080x1920 @ 30fps, Piper: Ngọc Huyền)...")
    opt_9_16 = QuizRenderOptions(
        aspect_ratio="9:16",
        fps=30,
        tts_engine="piper",
        piper_voice="ngoc_huyen_moi",
        piper_speed=1.05,
        output_path=mp4_9_16
    )
    engine_9_16 = QuizVideoEngineV2(opt_9_16)
    engine_9_16.render_quiz_video(REAL_AI_QUESTIONS)
    print(f"-> Hoàn tất 9:16 trong {time.time()-t1:.2f}s! Kích thước: {mp4_9_16.stat().st_size / (1024*1024):.2f} MB")

    # 3. Trích xuất Preview Frames
    print("\n[3/3] Trích xuất Preview Frames kiểm tra chất lượng pixel...")
    previews = [
        ("preview_16_9_q1_tra_sua.jpg", mp4_16_9, 14),
        ("preview_16_9_q1_reveal.jpg", mp4_16_9, 21),
        ("preview_16_9_q2_banh_mi.jpg", mp4_16_9, 32),
        ("preview_9_16_q1_tra_sua.jpg", mp4_9_16, 14),
        ("preview_9_16_q1_reveal.jpg", mp4_9_16, 21),
        ("preview_9_16_q2_banh_mi.jpg", mp4_9_16, 32),
    ]
    for fname, src_mp4, sec in previews:
        out_p = PREVIEWS_DIR / fname
        cmd = ["ffmpeg", "-y", "-ss", str(sec), "-i", str(src_mp4), "-vframes", "1", "-q:v", "2", str(out_p)]
        subprocess.run(cmd, capture_output=True)
        print(f"   ✓ Preview: {fname}")

    print("\n================================================================")
    print("🎉 TOÀN BỘ VIDEO GỌI QUOTA AI THẬT ĐÃ HOÀN THÀNH XUẤT SẮC!")
    print(f"📺 File 16:9 Long-form: {mp4_16_9.resolve()}")
    print(f"📱 File 9:16 Shorts/TikTok: {mp4_9_16.resolve()}")
    print("================================================================")


if __name__ == "__main__":
    main()
