#!/usr/bin/env python3
"""
Production Script: "THỬ THÁCH FAN CỨNG DORAEMON 2026"
Featuring:
- New Mascot: "Tí Nhỏ" (Vietnam-Box, áo cam sao trắng, răng thỏ lém lỉnh, tay giơ chữ V)
- Context Backgrounds: Bãi Đất Trống 3 Ống Cống Kinh Điển & Góc Phố Tokyo Anime
- 5 Iconic Doraemon Questions with Progressive Unblur & 3D AI Cutouts:
  1. Doraemon (Chuông vàng, bánh rán, túi thần kỳ -> Unblur Doraemon 3D)
  2. Nobita (Kính tròn, điểm 0, hậu đậu khóc nhè -> Hero Reveal Nobita 3D)
  3. Shizuka (Váy hồng, bím tóc, thích tắm nước nóng & ăn khoai nướng -> Hero Reveal Shizuka 3D)
  4. Suneo (Mỏ nhọn, nhà giàu khoe của, chuyên gia nịnh bợ -> Hero Reveal Suneo 3D)
  5. Jaian (Áo cam sọc vàng, hát dở mê ca hát, rốn lồi -> Hero Reveal Jaian 3D)
- Voice: VieNeuTTS (Ngọc Huyền) - Chuẩn phát âm tiếng Nhật/Anh tự nhiên, không đánh vần.
"""

from __future__ import annotations

import os
import sys
import math
import time
import subprocess
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter

VOICE_BACKEND = Path("D:/ALL AI/TestProjects/Voice/backend")
if str(VOICE_BACKEND) not in sys.path:
    sys.path.insert(0, str(VOICE_BACKEND))

from engines.vieneu_engine import synthesize_vieneu
from app.services.quiz_engine_v2 import (
    DynamicBackgroundCompositor,
    get_font,
    apply_diecut_outline,
    create_alarm_clock_icon
)

OUTPUT_DIR = Path("output/quiz_doraemon_fancung_2026")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR = OUTPUT_DIR / "audio_cache"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
FINAL_DIR = OUTPUT_DIR / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

DORAEMON_QUESTIONS = [
    # Question 1: Progressive Unblur Doraemon
    {
        "id": "q1_doraemon",
        "question": "ĐOÁN TÊN MÈO MÁY QUA ẢNH MỜ RÕ DẦN (DORAEMON)",
        "mode": "anime_unblur",
        "universe": "DORAEMON",
        "choices": [("A", "Dorami"), ("B", "Doraemon"), ("C", "Mini-Dora")],
        "correct_id": "B",
        "answer_text": "B: DORAEMON",
        "reveal_image_path": "assets/doraemon_assets/doraemon_clean.png",
        "bg_image": "assets/doraemon_assets/bg_doraemon_open_lot.png",
        "mascot": "tin_nho",
        "voice_q": "Câu số 1: Nhìn bức ảnh đang rõ dần này, đố bạn đây là chú mèo máy thần kỳ nào đến từ thế kỷ 22?",
        "voice_a": "Quá xuất sắc! Đó chính là chú mèo máy thông minh Doraemon mê bánh rán!",
        "trivia": "Doraemon sinh ngày 3 tháng 9 năm 2112 và sợ nhất là loài chuột!"
    },
    # Question 2: 3-Clues to Hero Reveal Nobita
    {
        "id": "q2_nobita",
        "question": "ĐOÁN TÊN CẬU BÉ QUA 3 GỢI Ý ĐẶC TRƯNG (DORAEMON)",
        "mode": "anime_clues",
        "universe": "DORAEMON",
        "clues": [
            {"word": "KÍNH TRÒN TO", "color": (52, 73, 94)},
            {"word": "ĐIỂM 0 TRÒN TRĨNH", "color": (231, 76, 60)},
            {"word": "KHÓC NHÈ", "color": (41, 128, 185)},
        ],
        "choices": [("A", "Nobi Nobita"), ("B", "Honekawa Suneo"), ("C", "Goda Takeshi")],
        "correct_id": "A",
        "answer_text": "A: NOBI NOBITA",
        "reveal_image_path": "assets/doraemon_assets/nobita_clean.png",
        "bg_image": "assets/doraemon_assets/bg_doraemon_open_lot.png",
        "mascot": "tin_nho",
        "voice_q": "Câu số 2: Kính tròn to đùng, bài thi bị điểm không và hay khóc nhè tìm Doraemon cầu cứu, đây là ai?",
        "voice_a": "Chuẩn xác 100%! Đó chính là cậu bạn hậu đậu nhưng rất tốt bụng Nobi Nobita!",
        "trivia": "Nobita giữ kỷ lục thế giới về tốc độ ngủ say chỉ mất đúng 0.93 giây!"
    },
    # Question 3: 3-Clues to Hero Reveal Shizuka
    {
        "id": "q3_shizuka",
        "question": "ĐOÁN TÊN CÔ BẠN DỄ THƯƠNG QUA 3 GỢI Ý",
        "mode": "anime_clues",
        "universe": "DORAEMON",
        "clues": [
            {"word": "HAI BÍM TÓC", "color": (155, 89, 182)},
            {"word": "THÍCH TẮM BỒN", "color": (52, 152, 219)},
            {"word": "KHOAI LANG NƯỚNG", "color": (230, 126, 34)},
        ],
        "choices": [("A", "Jaiko"), ("B", "Dorami"), ("C", "Minamoto Shizuka")],
        "correct_id": "C",
        "answer_text": "C: MINAMOTO SHIZUKA",
        "reveal_image_path": "assets/doraemon_assets/shizuka_clean.png",
        "bg_image": "assets/doraemon_assets/bg_doraemon_open_lot.png",
        "mascot": "tin_nho",
        "voice_q": "Câu số 3: Hai bím tóc xinh xắn, thích tắm bồn nước nóng và mê ăn khoai lang nướng, đây là cô bạn nào?",
        "voice_a": "Chính xác luôn bạn ơi! Đó chính là cô bé hiền lành Minamoto Shizuka!",
        "trivia": "Shizuka học đàn piano rất giỏi nhưng lại thích chơi đàn violin dù kéo phát ra tiếng kêu thất thanh!"
    },
    # Question 4: 3-Clues to Hero Reveal Suneo
    {
        "id": "q4_suneo",
        "question": "ĐOÁN TÊN CÔNG TỬ NHÀ GIÀU QUA 3 GỢI Ý",
        "mode": "anime_clues",
        "universe": "DORAEMON",
        "clues": [
            {"word": "MIỆNG NHỌN", "color": (241, 196, 15)},
            {"word": "NHÀ GIÀU KHOE CỦA", "color": (46, 204, 113)},
            {"word": "ĐỒ CHƠI ĐIỀU KHIỂN", "color": (231, 76, 60)},
        ],
        "choices": [("A", "Honekawa Suneo"), ("B", "Dekisugi Hidetoshi"), ("C", "Goda Takeshi")],
        "correct_id": "A",
        "answer_text": "A: HONEKAWA SUNEO",
        "reveal_image_path": "assets/doraemon_assets/suneo_clean.png",
        "bg_image": "assets/doraemon_assets/bg_doraemon_open_lot.png",
        "mascot": "tin_nho",
        "voice_q": "Câu số 4: Mái tóc và miệng nhọn hoắt, con nhà đại gia thích khoe đồ chơi điều khiển từ xa, đây là nhân vật nào?",
        "voice_a": "Quá chuẩn luôn! Đó chính là công tử nhà giàu Honekawa Suneo mỏ nhọn!",
        "trivia": "Suneo rất có năng khiếu vẽ tranh và ước mơ lớn lên trở thành một nhà thiết kế thời trang!"
    },
    # Question 5: 3-Clues to Hero Reveal Jaian
    {
        "id": "q5_jaian",
        "question": "ĐOÁN TÊN CA SĨ GIỌNG HÁT CHAIEN QUA 3 GỢI Ý",
        "mode": "anime_clues",
        "universe": "DORAEMON",
        "clues": [
            {"word": "GIỌNG HÁT THẢM HỌA", "color": (231, 76, 60)},
            {"word": "ÁO CAM SỌC VÀNG", "color": (230, 126, 34)},
            {"word": "BẮT NẠT BẠN BÈ", "color": (52, 73, 94)},
        ],
        "choices": [("A", "Honekawa Suneo"), ("B", "Goda Takeshi (Jaian)"), ("C", "Dekisugi")],
        "correct_id": "B",
        "answer_text": "B: GODA TAKESHI (JAIAN)",
        "reveal_image_path": "assets/doraemon_assets/jaian_clean.png",
        "bg_image": "assets/doraemon_assets/bg_doraemon_open_lot.png",
        "mascot": "tin_nho",
        "voice_q": "Câu số 5: Chiếc áo cam sọc vàng, thích bắt nạt bạn bè và có giọng hát thảm họa làm ai nghe cũng ngất xỉu, đây là ai?",
        "voice_a": "Xuất sắc! Đó chính là lồi rốn Goda Takeshi, hay còn gọi là Chaien dũng mãnh!",
        "trivia": "Mặc dù tính tình thô bạo nhưng Jaian là người cực kỳ yêu quý mẹ và em gái Jaiko!"
    },
]


class DoraemonQuizRenderer:
    def __init__(self, aspect_ratio: str = "16:9", fps: int = 30):
        self.aspect_ratio = aspect_ratio
        self.fps = fps
        if aspect_ratio == "9:16":
            self.width, self.height = 1080, 1920
        else:
            self.width, self.height = 1920, 1080
            
        self.clock_icon = create_alarm_clock_icon(72 if aspect_ratio == "9:16" else 84)
        
        # Load New Mascot "Tí Nhỏ"
        tin_nho_p = Path("assets/mascots_hoat_hinh/tin_nho_grabcut_perfect.png")
        raw_m = Image.open(tin_nho_p).convert("RGBA")
        target_h = 360 if aspect_ratio == "16:9" else 300
        sc = target_h / max(1, raw_m.height)
        self.mascot = apply_diecut_outline(raw_m.resize((int(raw_m.width * sc), target_h), Image.Resampling.LANCZOS), outline_px=6)

    def synthesize_audio(self, questions: list[dict[str, Any]]) -> tuple[dict[str, Path], dict[str, Path]]:
        voice_files = {}
        intro_p = AUDIO_DIR / "intro_doraemon.wav"
        outro_p = AUDIO_DIR / "outro_doraemon.wav"
        
        print("[VieNeu TTS] Synthesizing Voiceover (Ngọc Huyền)...")
        if not intro_p.exists() or intro_p.stat().st_size == 0:
            synthesize_vieneu("Chào mừng các bạn đến với Thử Thách Fan Cứng Doraemon 2026! Cùng trở về tuổi thơ và kiểm tra trí nhớ ngay nào!", intro_p, voice_id="Ngọc Huyền", speed=1.05)
        voice_files["intro"] = intro_p
        
        for i, q in enumerate(questions, 1):
            qp = AUDIO_DIR / f"q{i}_q.wav"
            ap = AUDIO_DIR / f"q{i}_a.wav"
            if not qp.exists() or qp.stat().st_size == 0:
                synthesize_vieneu(q["voice_q"], qp, voice_id="Ngọc Huyền", speed=1.05)
            if not ap.exists() or ap.stat().st_size == 0:
                full_ans = f"{q['voice_a']} {q.get('trivia', '')}"
                synthesize_vieneu(full_ans, ap, voice_id="Ngọc Huyền", speed=1.05)
            voice_files[f"q{i}_q"] = qp
            voice_files[f"q{i}_a"] = ap
            
        if not outro_p.exists() or outro_p.stat().st_size == 0:
            synthesize_vieneu("Xin chúc mừng bạn đã vượt qua tất cả câu đố Doraemon! Hãy bấm Like và Đăng ký kênh để đón xem những tập đố vui tiếp theo nhé!", outro_p, voice_id="Ngọc Huyền", speed=1.05)
        voice_files["outro"] = outro_p
        
        # SFX
        sfx_files = self._synthesize_sfx(AUDIO_DIR)
        return voice_files, sfx_files

    def _synthesize_sfx(self, audio_dir: Path) -> dict[str, Path]:
        import wave, numpy as np
        sr = 48000
        
        # 1. Countdown ticking
        cd_p = audio_dir / "sfx_countdown.wav"
        if not cd_p.exists():
            dur = 4.5
            total_samples = int(sr * dur)
            audio = np.zeros(total_samples, dtype=np.float32)
            tick_times = [0.0, 0.9, 1.8, 2.5, 3.1, 3.6, 4.0, 4.3]
            for t_hit in tick_times:
                idx = int(t_hit * sr)
                tk_len = int(sr * 0.08)
                t_arr = np.linspace(0, 0.08, tk_len, False)
                tone = np.sin(2 * np.pi * 950 * t_arr) * np.exp(-t_arr * 45)
                end_i = min(total_samples, idx + tk_len)
                audio[idx:end_i] += tone[:end_i - idx] * 0.65
            with wave.open(str(cd_p), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
                
        # 2. Ding
        ding_p = audio_dir / "sfx_ding.wav"
        if not ding_p.exists():
            dur = 2.0
            total_samples = int(sr * dur)
            t_arr = np.linspace(0, dur, total_samples, False)
            audio = (0.7 * np.sin(2 * np.pi * 1760 * t_arr) + 0.3 * np.sin(2 * np.pi * 3520 * t_arr)) * np.exp(-t_arr * 4.0)
            with wave.open(str(ding_p), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
                
        # 3. BGM Loop
        bgm_p = audio_dir / "bgm_doraemon.wav"
        if not bgm_p.exists():
            dur = 16.0
            total_samples = int(sr * dur)
            audio = np.zeros(total_samples, dtype=np.float32)
            bpm = 126
            beat_dur = 60.0 / bpm
            notes = [523.25, 659.25, 783.99, 1046.50, 880.00, 783.99, 659.25, 587.33]
            curr_t = 0.0
            idx = 0
            while curr_t < dur:
                s_i = int(curr_t * sr)
                freq = notes[idx % len(notes)]
                n_len = int(sr * 0.15)
                t_seg = np.linspace(0, 0.15, n_len, False)
                pluck = (0.7 * np.sin(2 * np.pi * freq * t_seg) + 0.3 * np.sin(4 * np.pi * freq * t_seg)) * np.exp(-t_seg * 18.0)
                e_i = min(total_samples, s_i + n_len)
                audio[s_i:e_i] += pluck[:e_i - s_i] * 0.40
                curr_t += beat_dur / 2.0
                idx += 1
            with wave.open(str(bgm_p), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
                
        return {"countdown": cd_p, "ding": ding_p, "bgm": bgm_p}

    def render_doraemon_video(self, questions: list[dict[str, Any]], out_mp4: Path):
        voice_files, sfx_files = self.synthesize_audio(questions)
        
        cur_t = 0.0
        events = []
        intro_dur = self._probe_dur(voice_files["intro"]) + 0.5
        events.append({"type": "intro", "start": cur_t, "dur": intro_dur})
        cur_t += intro_dur
        
        for i, q in enumerate(questions, 1):
            q_dur = self._probe_dur(voice_files[f"q{i}_q"]) + 0.3
            cd_dur = 4.0
            a_dur = self._probe_dur(voice_files[f"q{i}_a"]) + 0.8
            events.append({
                "type": "question",
                "idx": i,
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
        total_frames = int(total_dur * self.fps)
        
        temp_silent = FINAL_DIR / f"temp_doraemon_{self.aspect_ratio.replace(':', '_')}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            str(temp_silent)
        ]
        
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Background Compositor with Doraemon Open Lot Background
        bg_comp = DynamicBackgroundCompositor(
            self.width, self.height,
            top_color=(0, 159, 227),  # Doraemon Blue
            bottom_color=(0, 102, 178),
            custom_image_path="assets/doraemon_assets/bg_doraemon_open_lot.png",
            blur_bg=True
        )
        
        print(f"[{self.aspect_ratio}] Rendering Doraemon Quiz ({total_frames} frames, {total_dur:.1f}s)...")
        t_start = time.time()
        for f in range(total_frames):
            t = f / self.fps
            frame = self._render_frame(t, events, bg_comp)
            proc.stdin.write(frame.tobytes())
            
        proc.stdin.close()
        proc.wait()
        print(f"[{self.aspect_ratio}] Video frames rendered in {time.time() - t_start:.2f}s.")
        
        # Mux
        self._mux(temp_silent, voice_files, sfx_files, total_dur, events, out_mp4)
        if temp_silent.exists():
            temp_silent.unlink()
        print(f"[{self.aspect_ratio}] Finished! Saved to: {out_mp4.resolve()} ({out_mp4.stat().st_size / (1024*1024):.2f} MB)")

    def _render_frame(self, t: float, events: list[dict[str, Any]], bg_comp: Any) -> Image.Image:
        canvas = bg_comp.render(t)
        draw = ImageDraw.Draw(canvas)
        
        if t < events[0]["start"] + events[0]["dur"]:
            return self._render_intro_card(canvas, draw, t)
        elif t >= events[-1]["start"]:
            return self._render_outro_card(canvas, draw, t)
        else:
            for ev in events[1:-1]:
                if ev["q_start"] <= t < ev["rev_start"] + ev["rev_dur"]:
                    return self._render_question_card(canvas, draw, t, ev)
                    
        return canvas

    def _render_intro_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> Image.Image:
        if self.aspect_ratio == "16:9":
            # Left 1/3: Mascot Tí Nhỏ (V-Sign, Áo cam sao trắng)
            canvas.paste(self.mascot, (220, self.height // 2 - self.mascot.height // 2), self.mascot)
            font_title = get_font(68, bold=True)
            draw.text((1150, 460), "THỬ THÁCH FAN CỨNG DORAEMON", font=font_title, fill=(255, 215, 0), stroke_width=4, stroke_fill=(30, 30, 30), anchor="mm")
            font_sub = get_font(40, bold=True)
            draw.text((1150, 580), "BẠN TRẢ LỜI ĐÚNG ĐƯỢC BAO NHIÊU CÂU?", font=font_sub, fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        else:
            target_h = 360
            m = self.mascot.resize((int(self.mascot.width * (target_h / max(1, self.mascot.height))), target_h), Image.Resampling.LANCZOS)
            canvas.paste(m, (self.width // 2 - m.width // 2, 300), m)
            font_title = get_font(64, bold=True)
            draw.text((self.width // 2, 780), "FAN CỨNG DORAEMON", font=font_title, fill=(255, 215, 0), stroke_width=4, stroke_fill=(30, 30, 30), anchor="mm")
            font_sub = get_font(38, bold=True)
            draw.text((self.width // 2, 880), "THỬ TÀI TRÍ NHỚ TUỔI THƠ", font=font_sub, fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        return canvas

    def _render_outro_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> Image.Image:
        if self.aspect_ratio == "16:9":
            canvas.paste(self.mascot, (220, self.height // 2 - self.mascot.height // 2), self.mascot)
            font_title = get_font(72, bold=True)
            draw.text((1150, 460), "XIN CHÚC MỪNG!", font=font_title, fill=(46, 204, 113), stroke_width=4, stroke_fill=(20, 20, 20), anchor="mm")
            font_sub = get_font(40, bold=True)
            draw.text((1150, 580), "BẠN ĐẠT ĐƯỢC BAO NHIÊU ĐIỂM?", font=font_sub, fill=(255, 215, 0), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        else:
            target_h = 360
            m = self.mascot.resize((int(self.mascot.width * (target_h / max(1, self.mascot.height))), target_h), Image.Resampling.LANCZOS)
            canvas.paste(m, (self.width // 2 - m.width // 2, 300), m)
            font_title = get_font(64, bold=True)
            draw.text((self.width // 2, 780), "XIN CHÚC MỪNG!", font=font_title, fill=(46, 204, 113), stroke_width=4, stroke_fill=(20, 20, 20), anchor="mm")
            font_sub = get_font(38, bold=True)
            draw.text((self.width // 2, 880), "LIKE & BÌNH LUẬN ĐIỂM SỐ NHÉ!", font=font_sub, fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        return canvas

    def _render_question_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float, ev: dict[str, Any]) -> Image.Image:
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
            
        bob = 10 * math.sin(t * 3.0)
        
        if self.aspect_ratio == "16:9":
            # Question Header Box
            q_text = q_data.get("question", "ĐỐ VUI")
            f_size = 42 if len(q_text) <= 45 else (36 if len(q_text) <= 60 else 30)
            draw.rounded_rectangle([180, 35, 1680, 150], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
            draw.text((930, 92), q_text, font=get_font(f_size, bold=True), fill=(25, 25, 30), anchor="mm")
            
            # Streak Counter
            draw.rounded_rectangle([1700, 35, 1900, 150], radius=24, fill=(231, 76, 60), outline=(255, 255, 255), width=3)
            draw.text((1800, 92), f"STREAK: {q_idx}", font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
            
            # Left Card: Clues OR Hero Reveal
            rev_img_p = q_data.get("reveal_image_path")
            if is_rev and rev_img_p and Path(rev_img_p).exists():
                t_since_rev = max(0.0, t - ev["rev_start"])
                scale = max(0.1, min(1.0, t_since_rev * 3.5))
                draw.rounded_rectangle([180, int(250 + bob), 880, int(740 + bob)], radius=32, fill=(255, 255, 255), outline=(46, 204, 113), width=6)
                draw.text((530, int(285 + bob)), "CHÍNH XÁC!", font=get_font(32, bold=True), fill=(46, 204, 113), anchor="mm")
                max_h = 390
                hero_raw = Image.open(rev_img_p).convert("RGBA")
                target_h = int(max_h * scale)
                target_w = int(hero_raw.width * (target_h / max(1, hero_raw.height)))
                hero_scaled = hero_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                hx = 530 - target_w // 2
                hy = int(725 + bob - target_h)
                canvas.paste(hero_scaled, (hx, hy), hero_scaled)
            elif is_cd and q_data.get("mode") == "anime_unblur" and rev_img_p and Path(rev_img_p).exists():
                draw.rounded_rectangle([180, int(250 + bob), 880, int(740 + bob)], radius=32, fill=(255, 255, 255), outline=(240, 200, 50), width=6)
                draw.text((530, int(285 + bob)), "AI ĐÂY NHỈ? (ĐANG RÕ DẦN)", font=get_font(28, bold=True), fill=(230, 126, 34), anchor="mm")
                blur_r = max(0, int(36 * (1.0 - cd_elapsed)))
                hero_raw = Image.open(rev_img_p).convert("RGBA")
                max_h = 390
                target_h = max_h
                target_w = int(hero_raw.width * (target_h / max(1, hero_raw.height)))
                hero_scaled = hero_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                if blur_r > 0:
                    hero_scaled = hero_scaled.filter(ImageFilter.GaussianBlur(radius=blur_r))
                hx = 530 - target_w // 2
                hy = int(725 + bob - target_h)
                canvas.paste(hero_scaled, (hx, hy), hero_scaled)
            else:
                draw.rounded_rectangle([180, int(260 + bob), 880, int(720 + bob)], radius=32, fill=(255, 255, 255), outline=(240, 200, 50), width=6)
                uni = q_data.get("universe", "DORAEMON")
                draw.rounded_rectangle([220, int(280 + bob), 480, int(340 + bob)], radius=16, fill=(0, 159, 227))
                draw.text((350, int(310 + bob)), uni, font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
                clues = q_data.get("clues", [])
                for ci, c in enumerate(clues[:3]):
                    cy = int(370 + ci * 110 + bob)
                    draw.rounded_rectangle([220, cy, 840, cy + 90], radius=20, fill=c.get("color", (41, 128, 185)), outline=(255, 255, 255), width=3)
                    draw.text((530, cy + 45), f"GỢI Ý {ci+1}: {c.get('word', '')}", font=get_font(34, bold=True), fill=(255, 255, 255), anchor="mm")
                    
            # Right Side Choices
            choices = q_data.get("choices", [])
            correct_id = q_data.get("correct_id", "A")
            py_start = 260
            for i, (cid, ctext) in enumerate(choices):
                cy = int(py_start + i * 155 + bob)
                is_correct = (cid == correct_id)
                fill_c = (46, 204, 113) if (is_rev and is_correct) else ((120, 130, 140) if is_rev else (255, 255, 255))
                text_c = (255, 255, 255) if is_rev else (30, 30, 40)
                draw.rounded_rectangle([960, cy, 1820, cy + 125], radius=24, fill=fill_c, outline=(255, 215, 0) if not is_rev else (255, 255, 255), width=4)
                badge_fill = (46, 204, 113) if is_rev and is_correct else (231, 76, 60)
                draw.ellipse([980, cy + 22, 1060, cy + 102], fill=badge_fill)
                font_b = get_font(42, bold=True)
                if is_rev and is_correct:
                    draw.line([(1005, cy + 62), (1016, cy + 73), (1035, cy + 50)], fill=(255, 255, 255), width=5)
                else:
                    draw.text((1020, cy + 62), cid, font=font_b, fill=(255, 255, 255), anchor="mm")
                draw.text((1100, cy + 62), ctext, font=get_font(46, bold=True), fill=text_c, anchor="lm")
                
            # Place Mascot Tí Nhỏ in bottom left
            my_y = int(self.height - self.mascot.height - 15 + bob * 0.5)
            canvas.paste(self.mascot, (40, my_y), self.mascot)
            
            if is_rev:
                self._draw_reveal_bar(draw, 340, 880, 1500, 110, q_data.get("answer_text", ""), t, ev["rev_start"])
            else:
                self._draw_timer_bar(draw, canvas, 340, 890, 1500, 80, progress, t)
                
        else:
            # 9:16 Vertical
            q_text = q_data.get("question", "ĐỐ VUI")
            words = q_text.split()
            if len(words) > 6 and len(q_text) > 30:
                mid = len(words) // 2
                draw.rounded_rectangle([60, 140, 1020, 310], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
                draw.text((540, 195), " ".join(words[:mid]), font=get_font(30, bold=True), fill=(25, 25, 30), anchor="mm")
                draw.text((540, 250), " ".join(words[mid:]), font=get_font(30, bold=True), fill=(25, 25, 30), anchor="mm")
            else:
                draw.rounded_rectangle([60, 150, 1020, 285], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
                draw.text((540, 218), q_text, font=get_font(34, bold=True), fill=(25, 25, 30), anchor="mm")
                
            draw.rounded_rectangle([340, 320, 740, 390], radius=20, fill=(231, 76, 60), outline=(255, 255, 255), width=3)
            draw.text((540, 355), f"STREAK: {q_idx}", font=get_font(30, bold=True), fill=(255, 255, 255), anchor="mm")
            
            rev_img_p = q_data.get("reveal_image_path")
            if is_rev and rev_img_p and Path(rev_img_p).exists():
                t_since_rev = max(0.0, t - ev["rev_start"])
                scale = max(0.1, min(1.0, t_since_rev * 3.5))
                draw.rounded_rectangle([100, 440, 980, 810], radius=24, fill=(255, 255, 255), outline=(46, 204, 113), width=6)
                draw.text((540, 475), "CHÍNH XÁC!", font=get_font(30, bold=True), fill=(46, 204, 113), anchor="mm")
                max_h = 295
                hero_raw = Image.open(rev_img_p).convert("RGBA")
                target_h = int(max_h * scale)
                target_w = int(hero_raw.width * (target_h / max(1, hero_raw.height)))
                hero_scaled = hero_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                hx = 540 - target_w // 2
                hy = int(795 + bob - target_h)
                canvas.paste(hero_scaled, (hx, hy), hero_scaled)
            elif is_cd and q_data.get("mode") == "anime_unblur" and rev_img_p and Path(rev_img_p).exists():
                draw.rounded_rectangle([100, 440, 980, 810], radius=24, fill=(255, 255, 255), outline=(240, 200, 50), width=6)
                draw.text((540, 475), "AI ĐÂY NHỈ? (ĐANG RÕ DẦN)", font=get_font(28, bold=True), fill=(230, 126, 34), anchor="mm")
                blur_r = max(0, int(36 * (1.0 - cd_elapsed)))
                hero_raw = Image.open(rev_img_p).convert("RGBA")
                max_h = 295
                target_h = max_h
                target_w = int(hero_raw.width * (target_h / max(1, hero_raw.height)))
                hero_scaled = hero_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                if blur_r > 0:
                    hero_scaled = hero_scaled.filter(ImageFilter.GaussianBlur(radius=blur_r))
                hx = 540 - target_w // 2
                hy = int(795 + bob - target_h)
                canvas.paste(hero_scaled, (hx, hy), hero_scaled)
            else:
                clues = q_data.get("clues", [])
                for ci, c in enumerate(clues[:3]):
                    cy = int(480 + ci * 110 + bob)
                    draw.rounded_rectangle([100, cy, 980, cy + 90], radius=20, fill=c.get("color", (41, 128, 185)), outline=(255, 255, 255), width=3)
                    draw.text((540, cy + 45), f"GỢI Ý {ci+1}: {c.get('word', '')}", font=get_font(34, bold=True), fill=(255, 255, 255), anchor="mm")
                    
            choices = q_data.get("choices", [])
            correct_id = q_data.get("correct_id", "A")
            py_start = 830
            for i, (cid, ctext) in enumerate(choices):
                cy = int(py_start + i * 135 + bob)
                is_correct = (cid == correct_id)
                fill_c = (46, 204, 113) if (is_rev and is_correct) else ((120, 130, 140) if is_rev else (255, 255, 255))
                text_c = (255, 255, 255) if is_rev else (30, 30, 40)
                draw.rounded_rectangle([100, cy, 980, cy + 110], radius=22, fill=fill_c, outline=(255, 215, 0) if not is_rev else (255, 255, 255), width=4)
                badge_fill = (46, 204, 113) if is_rev and is_correct else (231, 76, 60)
                draw.ellipse([120, cy + 18, 190, cy + 88], fill=badge_fill)
                draw.text((155, cy + 53), cid if not (is_rev and is_correct) else "V", font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")
                draw.text((220, cy + 53), ctext, font=get_font(38, bold=True), fill=text_c, anchor="lm")
                
            my_y = int(1440 - self.mascot.height // 2 + bob * 0.5)
            canvas.paste(self.mascot, (self.width // 2 - self.mascot.width // 2, my_y), self.mascot)
            
            if is_rev:
                self._draw_reveal_bar(draw, 80, 1530, 920, 110, q_data.get("answer_text", ""), t, ev["rev_start"])
            else:
                self._draw_timer_bar(draw, canvas, 80, 1540, 920, 80, progress, t)
                
        return canvas

    def _draw_timer_bar(self, draw, canvas, x: int, y: int, w: int, h: int, progress: float, t: float):
        draw.rounded_rectangle([x + 3, y + 4, x + w + 3, y + h + 4], radius=36, fill=(0, 0, 0, 65))
        draw.rounded_rectangle([x, y, x + w, y + h], radius=36, fill=(245, 248, 250), outline=(210, 215, 220), width=3)
        elapsed = max(0.01, min(1.0, 1.0 - progress))
        fill_w = int(w * elapsed)
        if fill_w >= 100:
            draw.rounded_rectangle([x, y, x + fill_w, y + h], radius=36, fill=(0, 230, 118))
        elif fill_w > 0:
            draw.rectangle([x, y, x + fill_w, y + h], fill=(0, 230, 118))
        clock_paste = self.clock_icon
        if progress < 0.4:
            wobble = 14 * math.sin(t * 25.0)
            clock_paste = self.clock_icon.rotate(wobble, resample=Image.Resampling.BICUBIC, expand=True)
        clock_cx = x + fill_w
        clock_x = int(clock_cx - clock_paste.width / 2)
        clock_y = int(y + (h - clock_paste.height) / 2)
        canvas.paste(clock_paste, (clock_x, clock_y), clock_paste)

    def _draw_reveal_bar(self, draw, x: int, y: int, w: int, h: int, text: str, t: float, rev_start: float):
        t_rev = max(0.0, t - rev_start)
        scale = max(0.1, min(1.0, t_rev * 4.0))
        cur_w = max(100, int(w * scale))
        cur_h = max(50, int(h * scale))
        cur_x = x + (w - cur_w) // 2
        cur_y = y + (h - cur_h) // 2
        r_rev = min(24, max(1, min(cur_w, cur_h) // 2))
        draw.rounded_rectangle([cur_x + 4, cur_y + 6, cur_x + cur_w + 4, cur_y + cur_h + 6], radius=r_rev, fill=(0, 0, 0, 75))
        draw.rounded_rectangle([cur_x, cur_y, cur_x + cur_w, cur_y + cur_h], radius=r_rev, fill=(46, 204, 113), outline=(255, 255, 255), width=5)
        cx = cur_x + (45 if self.aspect_ratio == "9:16" else 65)
        cy = cur_y + cur_h // 2
        draw.line([(cx - 14, cy + 2), (cx - 4, cy + 12), (cx + 18, cy - 10)], fill=(255, 255, 255), width=6)
        
        full_ans_txt = f"ĐÁP ÁN: {text}"
        f_size = 46 if self.aspect_ratio == "16:9" else 34
        if len(full_ans_txt) > 42:
            f_size = 38 if self.aspect_ratio == "16:9" else 28
        if len(full_ans_txt) > 55:
            f_size = 32 if self.aspect_ratio == "16:9" else 24
            
        font_rev = get_font(f_size, bold=True)
        draw.text((cx + 35, cy), full_ans_txt, font=font_rev, fill=(255, 255, 255), anchor="lm")

    def _probe_dur(self, p: Path) -> float:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(res.stdout.strip())
        except Exception:
            return 3.0

    def _mux(self, video_file: Path, voice_files: dict[str, Path], sfx_files: dict[str, Path], total_dur: float, events: list[dict[str, Any]], output_file: Path):
        voice_inputs = []
        voice_delays = []
        cur_t = 0.0
        voice_inputs.append(str(voice_files["intro"]))
        voice_delays.append(int(cur_t * 1000))
        cur_t += self._probe_dur(voice_files["intro"]) + 0.5
        sfx_cd_delays = []
        sfx_ding_delays = []
        for i in range(1, len(events) - 1):
            ev = events[i]
            voice_inputs.append(str(voice_files[f"q{i}_q"]))
            voice_delays.append(int(ev["q_start"] * 1000))
            sfx_cd_delays.append(int(ev["cd_start"] * 1000))
            sfx_ding_delays.append(int(ev["rev_start"] * 1000))
            voice_inputs.append(str(voice_files[f"q{i}_a"]))
            voice_delays.append(int((ev["rev_start"] + 0.1) * 1000))
        voice_inputs.append(str(voice_files["outro"]))
        voice_delays.append(int(events[-1]["start"] * 1000))
        
        input_args = ["ffmpeg", "-y", "-i", str(video_file)]
        for vp in voice_inputs:
            input_args.extend(["-i", vp])
            
        cd_sfx_idx = len(voice_inputs) + 1
        ding_sfx_idx = len(voice_inputs) + 2
        bgm_idx = len(voice_inputs) + 3
        input_args.extend(["-i", str(sfx_files["countdown"])])
        input_args.extend(["-i", str(sfx_files["ding"])])
        input_args.extend(["-i", str(sfx_files["bgm"])])
        
        filter_parts = []
        v_labels = []
        for vi, dms in enumerate(voice_delays):
            filter_parts.append(f"[{vi+1}:a]adelay={dms}|{dms}[v_{vi}]")
            v_labels.append(f"[v_{vi}]")
        filter_parts.append(f"{''.join(v_labels)}amix=inputs={len(v_labels)}:duration=longest:normalize=0[voice_main]")
        
        cd_labels = []
        for ci, dms in enumerate(sfx_cd_delays):
            filter_parts.append(f"[{cd_sfx_idx}:a]adelay={dms}|{dms}[cd_{ci}]")
            cd_labels.append(f"[cd_{ci}]")
        filter_parts.append(f"{''.join(cd_labels)}amix=inputs={len(cd_labels)}:duration=longest:normalize=0[cd_main]")
        
        ding_labels = []
        for di, dms in enumerate(sfx_ding_delays):
            filter_parts.append(f"[{ding_sfx_idx}:a]adelay={dms}|{dms}[ding_{di}]")
            ding_labels.append(f"[ding_{di}]")
        filter_parts.append(f"{''.join(ding_labels)}amix=inputs={len(ding_labels)}:duration=longest:normalize=0[ding_main]")
        
        filter_parts.append("[cd_main][ding_main]amix=inputs=2:duration=longest:normalize=0,volume=1.2[sfx_main]")
        filter_parts.append(f"[{bgm_idx}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_dur:.2f},volume=-18dB,aresample=48000[bgm_raw]")
        filter_parts.append("[voice_main]asplit=2[v_play][v_sc]")
        filter_parts.append("[bgm_raw][v_sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=350[bgm_ducked]")
        filter_parts.append("[v_play][sfx_main][bgm_ducked]amix=inputs=3:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-14:LRA=7:TP=-1.5[final_audio]")
        
        cmd = input_args + [
            "-filter_complex", ";".join(filter_parts),
            "-map", "0:v",
            "-map", "[final_audio]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_file)
        ]
        subprocess.run(cmd, capture_output=True)


def main():
    print("==================================================================")
    print("🚀 BẮT ĐẦU XUẤT BẢN VIDEO DORAEMON: 'THỬ THÁCH FAN CỨNG 2026'")
    print("MASCOT MỚI TÍ NHỎ + NỀN BÃI ĐẤT TRỐNG 3 ỐNG CỐNG + VIENEUTTS")
    print("==================================================================")
    
    mp4_169 = FINAL_DIR / "quiz_doraemon_fancung_16_9.mp4"
    renderer_169 = DoraemonQuizRenderer(aspect_ratio="16:9", fps=30)
    renderer_169.render_doraemon_video(DORAEMON_QUESTIONS, mp4_169)
    
    mp4_916 = FINAL_DIR / "quiz_doraemon_fancung_9_16.mp4"
    renderer_916 = DoraemonQuizRenderer(aspect_ratio="9:16", fps=30)
    renderer_916.render_doraemon_video(DORAEMON_QUESTIONS, mp4_916)
    
    print("\n🎉 HOÀN THÀNH TOÀN DIỆN VIDEO DORAEMON CHO BOSS!")


if __name__ == "__main__":
    main()
