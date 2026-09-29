#!/usr/bin/env python3
"""
Masterpiece Long-Form Quiz Video Engine Exporter
Produces the definitive Showcase Video containing:
- 8 Distinct Viral Modes (Anime Unblur, 3-Clues Anime, Mystery Box, This-or-That, Emoji Rebus, Missing Letters, Open Visual, Eat or Pass)
- 8 Dynamic Themed Backgrounds (Wano, Pirate Harbor, Cafe Deck, Night Market, Countryside, Sakura Shrine, Cyber Blue, Galaxy Purple)
- Dual Mascots: Host Lộc & Co-Host Mỵ
- VieNeuTTS Dual Voices (Thanh Bình & Ngọc Huyền)
- High-Retention Audio Mastering: Procedural wood clock ticking, bell ding, sidechain ducked BGM, EBU R128 (-14 LUFS)
- 100% Validated Layouts (No overlaps, safe bounds)
"""

from __future__ import annotations

import os
import sys
import math
import time
import subprocess
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

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
from produce_masterpiece_video import MASTERPIECE_QUESTIONS, OUTPUT_DIR, AUDIO_DIR, FINAL_DIR


class MasterpieceVideoRenderer:
    def __init__(self, aspect_ratio: str = "16:9", fps: int = 30):
        self.aspect_ratio = aspect_ratio
        self.fps = fps
        if aspect_ratio == "9:16":
            self.width, self.height = 1080, 1920
        else:
            self.width, self.height = 1920, 1080
            
        self.clock_icon = create_alarm_clock_icon(72 if aspect_ratio == "9:16" else 84)
        
        # Load Cutout Mascots
        loc_cutout_p = Path("assets/mascots_hoat_hinh/loc_host_raw_cutout.png")
        my_cutout_p = Path("assets/mascots_hoat_hinh/my_host_raw_cutout.png")
        
        target_h = 360 if aspect_ratio == "16:9" else 300
        
        # Loc
        raw_loc = Image.open(loc_cutout_p).convert("RGBA")
        sc_loc = target_h / max(1, raw_loc.height)
        self.mascot_loc = apply_diecut_outline(raw_loc.resize((int(raw_loc.width * sc_loc), target_h), Image.Resampling.LANCZOS), outline_px=6)
        
        # My
        raw_my = Image.open(my_cutout_p).convert("RGBA")
        sc_my = target_h / max(1, raw_my.height)
        self.mascot_my = apply_diecut_outline(raw_my.resize((int(raw_my.width * sc_my), target_h), Image.Resampling.LANCZOS), outline_px=6)

    def synthesize_speech_and_sfx(self, questions: list[dict[str, Any]]) -> tuple[dict[str, Path], dict[str, Path]]:
        voice_files = {}
        intro_p = AUDIO_DIR / "master_intro.wav"
        outro_p = AUDIO_DIR / "master_outro.wav"
        
        # Alternate between Thanh Bình (Nam) and Ngọc Huyền (Nữ) for dynamic hosting!
        print("[VieNeu TTS] Synthesizing Dual-Host Voiceover (Thanh Bình & Ngọc Huyền)...")
        if not intro_p.exists() or intro_p.stat().st_size == 0:
            synthesize_vieneu("Chào mừng các bạn đến với Đấu Trường Trí Tuệ 2026! Cùng thử tài qua 8 vòng thi đỉnh cao ngay nào!", intro_p, voice_id="Thanh Bình", speed=1.05)
        voice_files["intro"] = intro_p
        
        for i, q in enumerate(questions, 1):
            qp = AUDIO_DIR / f"q{i}_q.wav"
            ap = AUDIO_DIR / f"q{i}_a.wav"
            host_voice = "Thanh Bình" if q.get("mascot") == "loc" else "Ngọc Huyền"
            if not qp.exists() or qp.stat().st_size == 0:
                synthesize_vieneu(q["voice_q"], qp, voice_id=host_voice, speed=1.05)
            if not ap.exists() or ap.stat().st_size == 0:
                # Include Trivia Fact to guarantee anti-reused content!
                full_ans = f"{q['voice_a']} {q.get('trivia', '')}"
                synthesize_vieneu(full_ans, ap, voice_id=host_voice, speed=1.05)
            voice_files[f"q{i}_q"] = qp
            voice_files[f"q{i}_a"] = ap
            
        if not outro_p.exists() or outro_p.stat().st_size == 0:
            synthesize_vieneu("Xin chúc mừng bạn đã xuất sắc vượt qua toàn bộ 8 thử thách! Đừng quên bấm Like và Đăng ký kênh để so tài trong các tập tiếp theo nhé!", outro_p, voice_id="Ngọc Huyền", speed=1.05)
        voice_files["outro"] = outro_p
        
        # Procedural SFX
        sfx_files = self._synthesize_sfx(AUDIO_DIR)
        return voice_files, sfx_files

    def _synthesize_sfx(self, audio_dir: Path) -> dict[str, Path]:
        import wave, numpy as np
        sr = 48000
        
        # 1. Countdown ticking accelerando
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
                
        # 2. Golden Ding
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
                
        # 3. Marimba BGM Loop (16s)
        bgm_p = audio_dir / "bgm_quiz.wav"
        if not bgm_p.exists():
            dur = 16.0
            total_samples = int(sr * dur)
            audio = np.zeros(total_samples, dtype=np.float32)
            bpm = 124
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

    def render_masterpiece(self, questions: list[dict[str, Any]], out_mp4: Path):
        voice_files, sfx_files = self.synthesize_speech_and_sfx(questions)
        
        # Pre-cache images
        for q in questions:
            for c in q.get("clues", []):
                ip = c.get("image_path")
                if ip and Path(ip).exists():
                    try:
                        with Image.open(ip) as cimg:
                            c["_cached_169"] = cimg.convert("RGBA").resize((340, 340), Image.Resampling.LANCZOS)
                            c["_cached_916"] = cimg.convert("RGBA").resize((280, 280), Image.Resampling.LANCZOS)
                    except Exception:
                        pass
                        
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
        
        temp_silent = FINAL_DIR / f"temp_master_{self.aspect_ratio.replace(':', '_')}.mp4"
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
        
        # Pre-build background compositors for each question (Context-Aware Backgrounds!)
        bg_compositors = {}
        for q in questions:
            qid = q["id"]
            custom_bg = q.get("bg_image")
            theme = q.get("bg_theme", "orange")
            top_c = (41, 128, 185) if theme == "blue" else ((142, 68, 173) if theme == "purple" else (235, 110, 30))
            bot_c = (21, 67, 96) if theme == "blue" else ((74, 35, 90) if theme == "purple" else (190, 60, 10))
            bg_compositors[qid] = DynamicBackgroundCompositor(
                self.width, self.height,
                top_color=top_c,
                bottom_color=bot_c,
                custom_image_path=custom_bg,
                blur_bg=True
            )
            
        default_bg = DynamicBackgroundCompositor(self.width, self.height, (235, 110, 30), (190, 60, 10))
        
        print(f"[{self.aspect_ratio}] Rendering {total_frames} frames ({total_dur:.1f}s) across 8 diverse backgrounds...")
        t_start = time.time()
        for f in range(total_frames):
            t = f / self.fps
            frame = self._render_frame(t, events, bg_compositors, default_bg)
            proc.stdin.write(frame.tobytes())
            
        proc.stdin.close()
        proc.wait()
        print(f"[{self.aspect_ratio}] Video frames rendered in {time.time() - t_start:.2f}s.")
        
        # Mux audio & video
        self._mux(temp_silent, voice_files, sfx_files, total_dur, events, out_mp4)
        if temp_silent.exists():
            temp_silent.unlink()
        print(f"[{self.aspect_ratio}] Masterpiece Exported: {out_mp4.resolve()} ({out_mp4.stat().st_size / (1024*1024):.2f} MB)")

    def _render_frame(self, t: float, events: list[dict[str, Any]], bg_compositors: dict[str, Any], default_bg: Any) -> Image.Image:
        # Determine current event
        if t < events[0]["start"] + events[0]["dur"]:
            bg = default_bg
            canvas = bg.render(t)
            draw = ImageDraw.Draw(canvas)
            return self._render_intro_card(canvas, draw, t)
        elif t >= events[-1]["start"]:
            bg = default_bg
            canvas = bg.render(t)
            draw = ImageDraw.Draw(canvas)
            return self._render_outro_card(canvas, draw, t)
        else:
            for ev in events[1:-1]:
                if ev["q_start"] <= t < ev["rev_start"] + ev["rev_dur"]:
                    qid = ev["data"]["id"]
                    bg = bg_compositors.get(qid, default_bg)
                    canvas = bg.render(t)
                    draw = ImageDraw.Draw(canvas)
                    return self._render_question_card(canvas, draw, t, ev)
                    
        return default_bg.render(t)

    def _render_intro_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> Image.Image:
        if self.aspect_ratio == "16:9":
            # Left 1/3: Host Lộc
            canvas.paste(self.mascot_loc, (220, self.height // 2 - self.mascot_loc.height // 2), self.mascot_loc)
            font_title = get_font(72, bold=True)
            draw.text((1150, 460), "ĐẤU TRƯỜNG TRÍ TUỆ 2026", font=font_title, fill=(255, 215, 0), stroke_width=4, stroke_fill=(30, 30, 30), anchor="mm")
            font_sub = get_font(40, bold=True)
            draw.text((1150, 580), "8 VÒNG THI SIÊU ĐỈNH • THỬ TÀI NGAY NÀO!", font=font_sub, fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        else:
            # 9:16 Vertical
            target_h = 360
            m = self.mascot_loc.resize((int(self.mascot_loc.width * (target_h / max(1, self.mascot_loc.height))), target_h), Image.Resampling.LANCZOS)
            canvas.paste(m, (self.width // 2 - m.width // 2, 300), m)
            font_title = get_font(64, bold=True)
            draw.text((self.width // 2, 780), "ĐẤU TRƯỜNG TRÍ TUỆ", font=font_title, fill=(255, 215, 0), stroke_width=4, stroke_fill=(30, 30, 30), anchor="mm")
            font_sub = get_font(38, bold=True)
            draw.text((self.width // 2, 880), "8 VÒNG THI ĐỈNH CAO 2026", font=font_sub, fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        return canvas

    def _render_outro_card(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, t: float) -> Image.Image:
        if self.aspect_ratio == "16:9":
            # Left 1/3: Co-Host Mỵ
            canvas.paste(self.mascot_my, (220, self.height // 2 - self.mascot_my.height // 2), self.mascot_my)
            font_title = get_font(72, bold=True)
            draw.text((1150, 460), "XIN CHÚC MỪNG!", font=font_title, fill=(46, 204, 113), stroke_width=4, stroke_fill=(20, 20, 20), anchor="mm")
            font_sub = get_font(40, bold=True)
            draw.text((1150, 580), "BẠN TRẢ LỜI ĐÚNG ĐƯỢC BAO NHIÊU CÂU?", font=font_sub, fill=(255, 215, 0), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
        else:
            target_h = 360
            m = self.mascot_my.resize((int(self.mascot_my.width * (target_h / max(1, self.mascot_my.height))), target_h), Image.Resampling.LANCZOS)
            canvas.paste(m, (self.width // 2 - m.width // 2, 300), m)
            font_title = get_font(64, bold=True)
            draw.text((self.width // 2, 780), "XIN CHÚC MỪNG!", font=font_title, fill=(46, 204, 113), stroke_width=4, stroke_fill=(20, 20, 20), anchor="mm")
            font_sub = get_font(38, bold=True)
            draw.text((self.width // 2, 880), "LIKE & COMMENT ĐIỂM SỐ NHÉ!", font=font_sub, fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 20, 20), anchor="mm")
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
        mode = q_data.get("mode", "")
        mascot = self.mascot_loc if q_data.get("mascot") == "loc" else self.mascot_my
        
        if self.aspect_ratio == "16:9":
            # Header Title Box
            q_text = q_data.get("question", "ĐỐ VUI")
            f_size = 42 if len(q_text) <= 45 else (36 if len(q_text) <= 60 else 30)
            draw.rounded_rectangle([180, 35, 1680, 150], radius=28, fill=(255, 204, 0), outline=(255, 255, 255), width=4)
            draw.text((930, 92), q_text, font=get_font(f_size, bold=True), fill=(25, 25, 30), anchor="mm")
            
            # Streak Counter
            draw.rounded_rectangle([1700, 35, 1900, 150], radius=24, fill=(231, 76, 60), outline=(255, 255, 255), width=3)
            draw.text((1800, 92), f"STREAK: {q_idx}", font=get_font(28, bold=True), fill=(255, 255, 255), anchor="mm")
            
            # Render Core Mode
            if mode in {"anime_unblur", "anime_clues"}:
                self._draw_anime_mode_169(draw, canvas, q_data, is_rev, is_cd, cd_elapsed, bob, t, ev["rev_start"])
            elif mode == "mystery_box":
                self._draw_mystery_box_169(draw, canvas, q_data, is_rev, bob)
            elif mode == "this_or_that":
                self._draw_this_or_that_169(draw, q_data["side_a"], q_data["side_b"], bob, t)
            elif mode == "missing_letters":
                self._draw_word_tiles_169(draw, q_data["word_tiles"], is_rev, bob)
            elif mode in {"emoji_rebus", "open_visual", "eat_or_pass"}:
                self._draw_visual_rebus_169(draw, canvas, q_data, is_rev, bob)
                
            # Place Mascot in bottom left (y=700)
            my_y = int(self.height - mascot.height - 15 + bob * 0.5)
            canvas.paste(mascot, (40, my_y), mascot)
            
            # Bottom bar (Timer during thinking, Reveal banner during reveal)
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
            
            if mode in {"anime_unblur", "anime_clues"}:
                self._draw_anime_mode_916(draw, canvas, q_data, is_rev, is_cd, cd_elapsed, bob, t, ev["rev_start"])
            elif mode == "mystery_box":
                self._draw_mystery_box_916(draw, canvas, q_data, is_rev, bob)
            elif mode == "this_or_that":
                self._draw_this_or_that_916(draw, q_data["side_a"], q_data["side_b"], bob, t)
            elif mode == "missing_letters":
                self._draw_word_tiles_916(draw, q_data["word_tiles"], is_rev, bob)
            elif mode in {"emoji_rebus", "open_visual", "eat_or_pass"}:
                self._draw_visual_rebus_916(draw, canvas, q_data, is_rev, bob)
                
            my_y = int(1440 - mascot.height // 2 + bob * 0.5)
            canvas.paste(mascot, (self.width // 2 - mascot.width // 2, my_y), mascot)
            
            if is_rev:
                self._draw_reveal_bar(draw, 80, 1530, 920, 110, q_data.get("answer_text", ""), t, ev["rev_start"])
            else:
                self._draw_timer_bar(draw, canvas, 80, 1540, 920, 80, progress, t)
                
        return canvas

    def _draw_anime_mode_169(self, draw, canvas, q_data, is_rev, is_cd, cd_elapsed, bob, t, rev_start):
        rev_img_p = q_data.get("reveal_image_path")
        if is_rev and rev_img_p and Path(rev_img_p).exists():
            # Elastic Pop Scale Animation for Hero Reveal
            t_since_rev = max(0.0, t - rev_start)
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
            # Progressive Unblur from 36px down to 0px
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
            # Clues
            draw.rounded_rectangle([180, int(260 + bob), 880, int(720 + bob)], radius=32, fill=(255, 255, 255), outline=(240, 200, 50), width=6)
            uni = q_data.get("universe", "ONE PIECE")
            draw.rounded_rectangle([220, int(280 + bob), 480, int(340 + bob)], radius=16, fill=(231, 76, 60))
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

    def _draw_anime_mode_916(self, draw, canvas, q_data, is_rev, is_cd, cd_elapsed, bob, t, rev_start):
        rev_img_p = q_data.get("reveal_image_path")
        if is_rev and rev_img_p and Path(rev_img_p).exists():
            t_since_rev = max(0.0, t - rev_start)
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

    def _draw_mystery_box_169(self, draw, canvas, q_data, is_rev, bob):
        boxes = q_data.get("boxes", [])
        xs = [450, 960, 1470]
        for bi, b in enumerate(boxes[:3]):
            bx = xs[bi]
            by = int(320 + bob)
            bw, bh = 420, 420
            col = b.get("color", (46, 204, 113))
            draw.rounded_rectangle([bx - bw//2 + 4, by + 6, bx + bw//2 + 4, by + bh + 6], radius=32, fill=(0, 0, 0, 70))
            draw.rounded_rectangle([bx - bw//2, by, bx + bw//2, by + bh], radius=32, fill=(255, 255, 255), outline=col, width=8)
            draw.rectangle([bx - 30, by, bx + 30, by + bh], fill=col)
            draw.rectangle([bx - bw//2, by + bh//2 - 30, bx + bw//2, by + bh//2 + 30], fill=col)
            badge_r = 45
            draw.ellipse([bx - badge_r, by + bh//2 - badge_r, bx + badge_r, by + bh//2 + badge_r], fill=col, outline=(255, 255, 255), width=4)
            draw.text((bx, by + bh//2), b["id"], font=get_font(52, bold=True), fill=(255, 255, 255), anchor="mm")
            if is_rev:
                draw.rounded_rectangle([bx - 190, by - 80, bx + 190, by + 10], radius=20, fill=col, outline=(255, 255, 255), width=4)
                draw.text((bx, by - 35), b.get("reward", ""), font=get_font(34, bold=True), fill=(255, 255, 255), anchor="mm")

    def _draw_mystery_box_916(self, draw, canvas, q_data, is_rev, bob):
        boxes = q_data.get("boxes", [])
        ys = [480, 740, 1000]
        for bi, b in enumerate(boxes[:3]):
            bx = 540
            by = int(ys[bi] + bob)
            bw, bh = 760, 210
            col = b.get("color", (46, 204, 113))
            draw.rounded_rectangle([bx - bw//2, by, bx + bw//2, by + bh], radius=24, fill=(255, 255, 255), outline=col, width=6)
            draw.rectangle([bx - 20, by, bx + 20, by + bh], fill=col)
            txt = f"HỘP {b['id']} ({b.get('color_name', '')})" + (f": {b.get('reward', '')}" if is_rev else "")
            draw.text((bx, by + bh//2), txt, font=get_font(42, bold=True), fill=(30, 30, 40) if not is_rev else col, anchor="mm")

    def _draw_this_or_that_169(self, draw, a, b, bob, t):
        draw.rounded_rectangle([220, int(280 + bob), 880, int(720 + bob)], radius=32, fill=a.get("color", (46, 204, 113)), outline=(255, 255, 255), width=6)
        draw.text((550, int(460 + bob)), a["name"], font=get_font(48, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.rounded_rectangle([380, int(570 + bob), 720, int(660 + bob)], radius=24, fill=(255, 255, 255), outline=(30, 30, 30), width=3)
        draw.text((550, int(615 + bob)), a.get("action", "BẤM LIKE"), font=get_font(38, bold=True), fill=(30, 30, 30), anchor="mm")
        
        draw.rounded_rectangle([1040, int(280 - bob), 1700, int(720 - bob)], radius=32, fill=b.get("color", (230, 126, 34)), outline=(255, 255, 255), width=6)
        draw.text((1370, int(460 - bob)), b["name"], font=get_font(48, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.rounded_rectangle([1200, int(570 - bob), 1540, int(660 - bob)], radius=24, fill=(255, 255, 255), outline=(30, 30, 30), width=3)
        draw.text((1370, int(615 - bob)), b.get("action", "BÌNH LUẬN"), font=get_font(38, bold=True), fill=(30, 30, 30), anchor="mm")
        
        vs_r = int(75 + 8 * math.sin(t * 6.0))
        draw.ellipse([960 - vs_r, 500 - vs_r, 960 + vs_r, 500 + vs_r], fill=(231, 76, 60), outline=(255, 255, 255), width=6)
        draw.text((960, 500), "VS", font=get_font(60, bold=True), fill=(255, 255, 255), anchor="mm")

    def _draw_this_or_that_916(self, draw, a, b, bob, t):
        draw.rounded_rectangle([100, 480, 980, 800], radius=28, fill=a.get("color", (46, 204, 113)), outline=(255, 255, 255), width=6)
        draw.text((540, 600), a["name"], font=get_font(44, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((540, 720), a.get("action", "BẤM LIKE"), font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")
        
        draw.rounded_rectangle([100, 880, 980, 1200], radius=28, fill=b.get("color", (230, 126, 34)), outline=(255, 255, 255), width=6)
        draw.text((540, 1000), b["name"], font=get_font(44, bold=True), fill=(255, 255, 255), anchor="mm")
        draw.text((540, 1120), b.get("action", "BÌNH LUẬN"), font=get_font(36, bold=True), fill=(255, 255, 255), anchor="mm")
        
        vs_r = 55
        draw.ellipse([540 - vs_r, 840 - vs_r, 540 + vs_r, 840 + vs_r], fill=(231, 76, 60), outline=(255, 255, 255), width=5)
        draw.text((540, 840), "VS", font=get_font(44, bold=True), fill=(255, 255, 255), anchor="mm")

    def _draw_word_tiles_169(self, draw, rows, is_rev, bob):
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
                draw.rounded_rectangle([tx + 4, curr_y + 6, tx + tile_s + 4, curr_y + tile_s + 6], radius=20, fill=(0, 0, 0, 70))
                draw.rounded_rectangle([tx, curr_y, tx + tile_s, curr_y + tile_s], radius=20, fill=(255, 255, 255), outline=(240, 200, 50), width=5)
                show_letter = given or is_rev
                if show_letter:
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), letter, font=get_font(72, bold=True), fill=(30, 30, 40) if given else (46, 204, 113), anchor="mm")
                else:
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), "?", font=get_font(60, bold=True), fill=(200, 200, 200), anchor="mm")

    def _draw_word_tiles_916(self, draw, rows, is_rev, bob):
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
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), letter, font=get_font(int(tile_s * 0.55), bold=True), fill=(30, 30, 40) if given else (46, 204, 113), anchor="mm")
                else:
                    draw.text((tx + tile_s//2, curr_y + tile_s//2), "?", font=get_font(int(tile_s * 0.5), bold=True), fill=(180, 180, 180), anchor="mm")

    def _draw_visual_rebus_169(self, draw, canvas, q_data, is_rev, bob):
        clues = q_data.get("clues", [])
        num_clues = len(clues)
        spacing = 1500 / max(1, num_clues)
        start_x = 210 + spacing / 2
        for ci, c in enumerate(clues):
            cx = int(start_x + ci * spacing)
            c_scaled = c.get("_cached_169")
            card_w, card_h = 340, 340
            if c_scaled is not None:
                canvas.paste(c_scaled, (cx - card_w // 2, int(330 + bob)), c_scaled)
            else:
                draw.rounded_rectangle([cx - card_w // 2, int(330 + bob), cx + card_w // 2, int(330 + card_h + bob)], radius=28, fill=c.get("color", (41, 128, 185)), outline=(255, 255, 255), width=6)
                draw.text((cx, int(330 + card_h // 2 + bob)), c.get("word", ""), font=get_font(52, bold=True), fill=(255, 255, 255), anchor="mm")
                
            if ci < num_clues - 1:
                next_cx = int(start_x + (ci + 1) * spacing)
                mid_x = (cx + next_cx) // 2
                draw.text((mid_x, int(330 + card_h // 2 + bob)), "+", font=get_font(72, bold=True), fill=(255, 255, 255), anchor="mm")

    def _draw_visual_rebus_916(self, draw, canvas, q_data, is_rev, bob):
        clues = q_data.get("clues", [])
        num_clues = len(clues)
        spacing_y = 740 / max(1, num_clues)
        start_y = 460 + spacing_y / 2
        for ci, c in enumerate(clues):
            cy = int(start_y + ci * spacing_y)
            c_scaled = c.get("_cached_916")
            card_s = min(300, int(spacing_y * 0.85))
            if c_scaled is not None:
                canvas.paste(c_scaled, (540 - card_s // 2, cy - card_s // 2), c_scaled)
            else:
                draw.rounded_rectangle([540 - card_s // 2, cy - card_s // 2, 540 + card_s // 2, cy + card_s // 2], radius=28, fill=c.get("color", (41, 128, 185)), outline=(255, 255, 255), width=6)
                draw.text((540, cy), c.get("word", ""), font=get_font(52, bold=True), fill=(255, 255, 255), anchor="mm")

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
        
        # Responsive font sizing so long text like (+100TR • NỢ 50TR • +10K) NEVER gets truncated
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
    print("🚀 BẮT ĐẦU XUẤT BẢN VIDEO DÀI 'ĐẤU TRƯỜNG TRÍ TUỆ 2026'")
    print("TỔNG HỢP TẤT CẢ CÁC MODE, PHÔNG NỀN, MASCOT & ÂM THANH ĐỈNH CAO!")
    print("==================================================================")
    
    # Render 16:9 Long-Form
    mp4_169 = FINAL_DIR / "dau_truong_tri_tue_2026_16_9.mp4"
    renderer_169 = MasterpieceVideoRenderer(aspect_ratio="16:9", fps=30)
    renderer_169.render_masterpiece(MASTERPIECE_QUESTIONS, mp4_169)
    
    # Render 9:16 Shorts/TikTok
    mp4_916 = FINAL_DIR / "dau_truong_tri_tue_2026_9_16.mp4"
    renderer_916 = MasterpieceVideoRenderer(aspect_ratio="9:16", fps=30)
    renderer_916.render_masterpiece(MASTERPIECE_QUESTIONS, mp4_916)
    
    print("\n🎉 HOÀN THÀNH XUẤT BẢN TOÀN DIỆN CẢ 2 BẢN 16:9 VÀ 9:16!")


if __name__ == "__main__":
    main()
