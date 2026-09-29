#!/usr/bin/env python3
"""
Produce comparison test videos demonstrating the fixed & optimized Quiz rendering engines:
1. 4-choice Multiple Choice Questions (A, B, C, D) using dict format {"id": ..., "text": ...}
2. Long answer text reveal bar auto-fitting without clipping
3. Both 16:9 Landscape and 9:16 Vertical Shorts
4. Deterministic V1 Offline Renderer 4-choice validation
"""

import os
import sys
import time
import subprocess
from pathlib import Path

from app.services.quiz_engine_v2 import QuizVideoEngineV2, QuizRenderOptions
from app.services.quiz_renderer import QuizOfflineRenderer
from app.services.quiz_timeline import QuizTimelineCompiler

OUT_DIR = Path("output/test_optimized_comparison").resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)
PREVIEWS_DIR = OUT_DIR / "previews"
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

TEST_QUESTIONS = [
    {
        "id": "opt_01",
        "question": "Thủ đô của Việt Nam là thành phố nào?",
        "voice_q": "Câu hỏi số 1: Thủ đô ngàn năm văn hiến của Việt Nam là thành phố nào?",
        "voice_a": "Chính xác rồi! Thủ đô của Việt Nam chính là Hà Nội!",
        "choices": [
            {"id": "A", "text": "Hà Nội"},
            {"id": "B", "text": "Huế"},
            {"id": "C", "text": "Đà Nẵng"},
            {"id": "D", "text": "TP Hồ Chí Minh"},
        ],
        "correct_id": "A",
        "answer_text": "A: HÀ NỘI (Thủ đô ngàn năm văn hiến)",
        "clues": [
            {"word": "THỦ ĐÔ", "color": (231, 76, 60)}
        ],
    },
    {
        "id": "opt_02",
        "question": "CHỌN HỘP QUÀ MAY MẮN: BẠN CHỌN HỘP NÀO?",
        "voice_q": "Câu số 2: Chọn một hộp quà may mắn, cùng mở quà xem nhân phẩm của bạn nhé!",
        "voice_a": "Hết giờ rồi! Hộp Xanh cộng 100 triệu, Hộp Đỏ nợ 50 triệu, Hộp Vàng cộng 10 nghìn đồng!",
        "boxes": [
            {"id": "A", "color_name": "Xanh", "reward": "+100 TRIỆU", "color": (46, 204, 113)},
            {"id": "B", "color_name": "Đỏ", "reward": "NỢ 50 TRIỆU", "color": (231, 76, 60)},
            {"id": "C", "color_name": "Vàng", "reward": "+10 NGHÌN", "color": (241, 196, 15)},
        ],
        "answer_text": "HỘP XANH: +100 TRIỆU ĐỒNG • HỘP ĐỎ: NỢ 50 TRIỆU • HỘP VÀNG: +10 NGHÌN ĐỒNG",
    },
    {
        "id": "opt_03",
        "question": "ĐỐ VUI TÍNH NHANH: 90 CHIA 9 CỘNG 5 BẰNG MẤY?",
        "voice_q": "Câu số 3 thử thách tính nhanh: 90 chia 9 cộng 5 bằng bao nhiêu?",
        "voice_a": "Quá chuẩn luôn bạn ơi! 90 chia 9 bằng 10, cộng 5 bằng 15!",
        "choices": [
            {"id": "A", "text": "10"},
            {"id": "B", "text": "15"},
            {"id": "C", "text": "20"},
            {"id": "D", "text": "25"},
        ],
        "correct_id": "B",
        "answer_text": "B: 15 (90 / 9 + 5 = 15)",
        "clues": [
            {"word": "TOÁN", "color": (39, 174, 96)}
        ],
    },
]


def render_v1_offline_test():
    print("\n--- [V1 Offline Renderer] Kiểm tra 4 lựa chọn không crash IndexError ---")
    renderer = QuizOfflineRenderer(width=1280, height=720, fps=30)
    quiz_doc = {
        "schema_version": "quiz_project_v1",
        "title": "Test 4 choices V1",
        "language": "vi",
        "question_count": 1,
        "target_question_count": 1,
        "seconds_per_question": 2,
        "theme_id": "vox_quiz_01",
        "questions": [
            {
                "question_id": "q001",
                "order": 1,
                "type": "multiple_choice_text",
                "template_id": "text_mcq",
                "question": "90 : 9 + 5 = ?",
                "choices": [
                    {"id": "A", "text": "10"},
                    {"id": "B", "text": "15"},
                    {"id": "C", "text": "20"},
                    {"id": "D", "text": "25"},
                ],
                "correct_choice_id": "B",
                "answer_text": "15",
                "question_voice": "90 chia 9 cộng 5 bằng bao nhiêu?",
                "answer_voice": "Đáp án đúng là 15.",
                "fact_sources": ["verified_math"],
                "countdown_seconds": 2,
            }
        ],
    }
    v1_out_dir = OUT_DIR / "v1_offline"
    v1_out_dir.mkdir(parents=True, exist_ok=True)
    res = renderer.render(quiz_doc, v1_out_dir)
    print(f"-> V1 Output MP4: {res.output_path} ({res.output_path.stat().st_size / 1024:.1f} KB)")
    return res.output_path


def render_v2_comparison_videos():
    print("\n--- [V2 Dynamic Engine] Render Video 16:9 Ngang & 9:16 Dọc ---")
    
    # 1. 16:9 Landscape
    t0 = time.time()
    mp4_16_9 = OUT_DIR / "quiz_optimized_16_9.mp4"
    print(f"\n[1/2] Đang render bản 16:9 Master ({mp4_16_9.name})...")
    opt_16_9 = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        pacing="fast",
        tts_engine="piper",
        piper_voice="minh_khang",
        piper_speed=1.05,
        output_path=mp4_16_9,
    )
    engine_16_9 = QuizVideoEngineV2(opt_16_9)
    engine_16_9.render_quiz_video(TEST_QUESTIONS, title="THỬ THÁCH ĐỐ VUI TỐI ƯU")
    d0 = time.time() - t0
    print(f"-> Hoàn tất 16:9 trong {d0:.2f}s! Kích thước: {mp4_16_9.stat().st_size / (1024*1024):.2f} MB")

    # 2. 9:16 Vertical Shorts
    t1 = time.time()
    mp4_9_16 = OUT_DIR / "quiz_optimized_9_16.mp4"
    print(f"\n[2/2] Đang render bản 9:16 Shorts ({mp4_9_16.name})...")
    opt_9_16 = QuizRenderOptions(
        aspect_ratio="9:16",
        fps=30,
        pacing="fast",
        tts_engine="piper",
        piper_voice="ngoc_huyen_moi",
        piper_speed=1.05,
        output_path=mp4_9_16,
    )
    engine_9_16 = QuizVideoEngineV2(opt_9_16)
    engine_9_16.render_quiz_video(TEST_QUESTIONS, title="THỬ THÁCH ĐỐ VUI TỐI ƯU")
    d1 = time.time() - t1
    print(f"-> Hoàn tất 9:16 trong {d1:.2f}s! Kích thước: {mp4_9_16.stat().st_size / (1024*1024):.2f} MB")

    # 3. Extract Preview Frames
    print("\n[3/3] Trích xuất preview frames để thẩm định pixel...")
    previews = [
        ("preview_16_9_q1_4choices.jpg", mp4_16_9, 5),
        ("preview_16_9_q1_reveal.jpg", mp4_16_9, 9),
        ("preview_16_9_q2_boxes.jpg", mp4_16_9, 14),
        ("preview_16_9_q2_reveal_longtext.jpg", mp4_16_9, 21),
        ("preview_9_16_q1_4choices.jpg", mp4_9_16, 5),
        ("preview_9_16_q1_reveal.jpg", mp4_9_16, 9),
        ("preview_9_16_q2_reveal_longtext.jpg", mp4_9_16, 21),
    ]
    for fname, src_mp4, sec in previews:
        out_p = PREVIEWS_DIR / fname
        cmd = ["ffmpeg", "-y", "-ss", str(sec), "-i", str(src_mp4), "-vframes", "1", "-q:v", "2", str(out_p)]
        subprocess.run(cmd, capture_output=True)
        if out_p.exists():
            print(f"   Saved: {out_p.name} ({out_p.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    render_v1_offline_test()
    render_v2_comparison_videos()
    print("\n✅ HOÀN TẤT TOÀN BỘ CÁC BẢN VIDEO TEST VÀ KHUNG HÌNH THẨM ĐỊNH!")
