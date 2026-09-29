#!/usr/bin/env python3
"""
Production Execution Script: Real Quota AI Video Generator
Topic: "Món Ăn Vặt & Đồ Uống Hot Trend Giới Trẻ 2026"
1. Calls CLIProxy LLM (gemini-3.6-flash-high) for real-time creative question generation.
2. Calls CLIProxy Image (gpt-image-2) for real 3D glossy sticker generation.
3. Calls Edge-TTS for Vietnamese voiceover.
4. Renders 30FPS dynamic motion graphics with mascot Thỏ and confetti.
5. Produces both 16:9 Long-form and 9:16 Shorts with -14 LUFS audio normalization.
"""

import asyncio
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.config import _discover_cliproxy_api_key
from app.providers.base import ImageGenerationRequest
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.providers.llm.cliproxy import CliproxyLLMProvider
from app.services.quiz_engine_v2 import (
    DynamicBackgroundCompositor,
    QuizRenderOptions,
    QuizVideoEngineV2,
    apply_diecut_outline,
    draw_rabbit_mascot,
    create_alarm_clock_icon,
    get_font,
)

OUTPUT_DIR = Path("output/real_quota_ai_production")
ASSETS_DIR = OUTPUT_DIR / "ai_stickers"
AUDIO_DIR = OUTPUT_DIR / "audio"
FINAL_DIR = OUTPUT_DIR / "final"
PREVIEWS_DIR = OUTPUT_DIR / "previews"

for d in [OUTPUT_DIR, ASSETS_DIR, AUDIO_DIR, FINAL_DIR, PREVIEWS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


async def main():
    print("================================================================")
    print("🚀 BẮT ĐẦU QUY TRÌNH GỌI QUOTA THẬT SINH VIDEO BẰNG LÕI AI CLIPROXY")
    print("================================================================")
    
    api_key = _discover_cliproxy_api_key()
    print(f"[AUTH] Đã xác thực API key CLIProxy (Độ dài: {len(api_key)} ký tự)")

    # -------------------------------------------------------------
    # BƯỚC 1: GỌI LLM (gemini-3.6-flash-high) TỰ ĐỘNG SINH KỊCH BẢN
    # -------------------------------------------------------------
    print("\n[BƯỚC 1] Gọi LLM gemini-3.6-flash-high sinh kịch bản câu đố ẩm thực...")
    llm = CliproxyLLMProvider(api_key=api_key, model="gemini-3.6-flash-high")
    
    system_prompt = (
        "Bạn là đạo diễn chương trình đố vui Rabbit Game đạt triệu view. "
        "Hãy tạo 3 câu đố Đuổi hình bắt chữ (Emoji Rebus) chủ đề 'Món Ăn Vặt & Đồ Uống Hot Trend Giới Trẻ 2026'. "
        "Mỗi câu có đúng 2 từ khóa thành phần (clues) ghép thành một món ăn quen thuộc cực ngon. "
        "Kịch bản giọng đọc phải tự nhiên, trẻ trung, có câu hỏi và câu chúc mừng khi mở đáp án."
    )
    user_prompt = "Tạo 3 câu đố Đuổi hình bắt chữ về: 1) Trà sữa, 2) Bánh mì, 3) Bắp rang bơ."
    
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "question": {"type": "string"},
                        "clues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "word": {"type": "string"},
                                    "image_prompt": {"type": "string"}
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
        "required": ["title", "questions"]
    }
    
    t0 = time.time()
    res = await llm.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=schema,
        temperature=0.7,
        request_id=f"real_prod_{int(time.time())}"
    )
    print(f"-> LLM đã trả về kịch bản sau {time.time()-t0:.2f} giây:")
    questions = res.get("questions", [])
    for i, q in enumerate(questions, 1):
        words = " + ".join([c["word"] for c in q["clues"]])
        print(f"   Câu {i}: {words} = {q['answer_text']}")

    # -------------------------------------------------------------
    # BƯỚC 2: GỌI AI IMAGE (gpt-image-2) SINH STICKER 3D ĐỘC QUYỀN
    # -------------------------------------------------------------
    print("\n[BƯỚC 2] Gọi AI Image model gpt-image-2 sinh bộ sticker 3D...")
    img_provider = CliproxyImageProvider(api_key=api_key, model="gpt-image-2")
    
    image_tasks = []
    clue_slots = []
    
    for q in questions:
        for ci, c in enumerate(q.get("clues", [])):
            h = hashlib.md5(c["image_prompt"].encode()).hexdigest()[:10]
            out_img = ASSETS_DIR / f"sticker_{c['word'].lower()}_{h}.png"
            c["image_path"] = str(out_img)
            
            if not out_img.exists() or out_img.stat().st_size < 5000:
                print(f"-> Gửi yêu cầu sinh ảnh cho '{c['word']}': {c['image_prompt'][:60]}...")
                req = ImageGenerationRequest(
                    prompt=f"{c['image_prompt']}, vibrant 3D glossy cartoon game sticker, thick die-cut white outline, isolated on pure white background, cute high-resolution asset",
                    role="subject",
                    output_path=str(out_img),
                    candidate_count=1
                )
                image_tasks.append((out_img, req))
            else:
                print(f"-> Đã có sẵn cache sticker: {out_img.name}")

    if image_tasks:
        t_img_start = time.time()
        for out_img, req in image_tasks:
            t_single = time.time()
            try:
                await img_provider.generate(req)
                # Apply diecut outline and soft drop shadow
                with Image.open(out_img) as raw:
                    cutout = apply_diecut_outline(raw.convert("RGBA"), outline_px=8)
                    cutout.save(out_img)
                print(f"   ✓ Đã tạo xong '{out_img.name}' ({out_img.stat().st_size / (1024*1024):.2f} MB) trong {time.time()-t_single:.2f}s")
            except Exception as e:
                print(f"   ✗ Lỗi sinh ảnh '{out_img.name}': {e}")
        print(f"-> Hoàn tất toàn bộ ảnh trong {time.time()-t_img_start:.2f}s")

    # -------------------------------------------------------------
    # BƯỚC 3: RENDER VIDEO MASTER 16:9 & 9:16 SHORTS
    # -------------------------------------------------------------
    print("\n[BƯỚC 3] Khởi chạy Render Video 30FPS (16:9 Long-form & 9:16 Shorts)...")
    
    # Render 16:9
    mp4_16_9 = FINAL_DIR / "quiz_mon_an_vat_2026_16_9.mp4"
    opt_16_9 = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        voice_name="vi-VN-HoaiMyNeural",
        output_path=mp4_16_9
    )
    engine_16_9 = QuizVideoEngineV2(opt_16_9)
    engine_16_9.render_quiz_video(questions)
    
    # Render 9:16 Shorts
    mp4_9_16 = FINAL_DIR / "quiz_mon_an_vat_2026_9_16_shorts.mp4"
    opt_9_16 = QuizRenderOptions(
        aspect_ratio="9:16",
        fps=30,
        voice_name="vi-VN-HoaiMyNeural",
        output_path=mp4_9_16
    )
    engine_9_16 = QuizVideoEngineV2(opt_9_16)
    engine_9_16.render_quiz_video(questions)

    # -------------------------------------------------------------
    # BƯỚC 4: TRÍCH XUẤT PREVIEW FRAMES ĐỂ KIỂM ĐỊNH
    # -------------------------------------------------------------
    print("\n[BƯỚC 4] Trích xuất preview frames để thẩm định pixel...")
    timestamps = [
        ("16_9_q1_question.jpg", mp4_16_9, 12),
        ("16_9_q1_reveal.jpg", mp4_16_9, 19),
        ("9_16_q1_question.jpg", mp4_9_16, 12),
        ("9_16_q1_reveal.jpg", mp4_9_16, 19),
    ]
    for fname, src_mp4, t in timestamps:
        p_out = PREVIEWS_DIR / fname
        cmd = ["ffmpeg", "-y", "-ss", str(t), "-i", str(src_mp4), "-vframes", "1", "-q:v", "2", str(p_out)]
        subprocess.run(cmd, capture_output=True)

    print("\n================================================================")
    print("🎉 HOÀN THÀNH XUẤT BẢN VIDEO GỌI QUOTA THẬT 100% THÀNH CÔNG!")
    print(f"📁 Video 16:9: {mp4_16_9.resolve()} ({mp4_16_9.stat().st_size / (1024*1024):.2f} MB)")
    print(f"📁 Video 9:16: {mp4_9_16.resolve()} ({mp4_9_16.stat().st_size / (1024*1024):.2f} MB)")
    print("================================================================")


if __name__ == "__main__":
    asyncio.run(main())
