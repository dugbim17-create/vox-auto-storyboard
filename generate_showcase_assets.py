import os
import sys
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import numpy as np
import wave

OUTPUT_DIR = Path("output/rabbit_game_8archetypes_showcase")
ASSETS_DIR = OUTPUT_DIR / "assets"
AUDIO_DIR = OUTPUT_DIR / "audio"
FRAMES_DIR = OUTPUT_DIR / "frames"

for d in [OUTPUT_DIR, ASSETS_DIR, AUDIO_DIR, FRAMES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

sr = 48000

def write_wav(path, data, sample_rate=48000):
    data = np.clip(data, -1.0, 1.0)
    int_data = (data * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(int_data.tobytes())

# 1. Answer Ding / Chime (C6 Major Triad)
dur = 2.0
t = np.linspace(0, dur, int(sr * dur), endpoint=False)
ding = (
    0.45 * np.sin(2 * np.pi * 1046.5 * t) * np.exp(-t * 3.5) +
    0.35 * np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 4.0) +
    0.30 * np.sin(2 * np.pi * 1568.0 * t) * np.exp(-t * 4.5) +
    0.20 * np.sin(2 * np.pi * 2093.0 * t) * np.exp(-t * 6.0)
)
write_wav(AUDIO_DIR / "sfx_ding.wav", ding)

# 2. Countdown Clock Ticks
dur_cd = 4.5
t_cd = np.linspace(0, dur_cd, int(sr * dur_cd), endpoint=False)
ticks = np.zeros_like(t_cd)
for click_t in np.arange(0.0, dur_cd, 0.5):
    idx = int(click_t * sr)
    click_len = int(0.08 * sr)
    if idx + click_len <= len(t_cd):
        t_sub = np.linspace(0, 0.08, click_len, endpoint=False)
        freq = 1400 if int(click_t * 2) % 2 == 0 else 900
        click = 0.65 * np.sin(2 * np.pi * freq * t_sub) * np.exp(-t_sub * 85)
        ticks[idx:idx + click_len] += click
write_wav(AUDIO_DIR / "sfx_countdown.wav", ticks)

# 3. Buzzer SFX
dur_bz = 1.2
t_bz = np.linspace(0, dur_bz, int(sr * dur_bz), endpoint=False)
buzzer = 0.5 * (np.sin(2 * np.pi * 220.0 * t_bz) + 0.5 * np.sin(2 * np.pi * 440.0 * t_bz)) * np.exp(-t_bz * 3.0)
write_wav(AUDIO_DIR / "sfx_buzzer.wav", buzzer)

# 4. Cheerful BGM loop (16 seconds clean loopable)
bpm = 120
beat_s = 60.0 / bpm
bgm_dur = 16.0
t_bgm = np.linspace(0, bgm_dur, int(sr * bgm_dur), endpoint=False)
bgm = np.zeros_like(t_bgm)
notes = [261.63, 329.63, 392.00, 440.00, 523.25, 392.00, 329.63, 293.66, 349.23, 440.00, 523.25, 587.33]
bass_notes = [130.81, 130.81, 164.81, 164.81, 174.61, 174.61, 196.00, 196.00]

for i, step_t in enumerate(np.arange(0.0, bgm_dur, beat_s / 2)):
    idx = int(step_t * sr)
    n_len = int(0.22 * sr)
    if idx + n_len <= len(t_bgm):
        t_sub = np.linspace(0, 0.22, n_len, endpoint=False)
        freq = notes[i % len(notes)]
        marimba = 0.22 * np.sin(2 * np.pi * freq * t_sub) * np.exp(-t_sub * 16) + \
                  0.10 * np.sin(2 * np.pi * freq * 2 * t_sub) * np.exp(-t_sub * 24)
        bgm[idx:idx + n_len] += marimba

for i, step_t in enumerate(np.arange(0.0, bgm_dur, beat_s)):
    idx = int(step_t * sr)
    n_len = int(0.4 * sr)
    if idx + n_len <= len(t_bgm):
        t_sub = np.linspace(0, 0.4, n_len, endpoint=False)
        freq = bass_notes[i % len(bass_notes)]
        bass = 0.32 * np.sin(2 * np.pi * freq * t_sub) * np.exp(-t_sub * 8)
        bgm[idx:idx + n_len] += bass

write_wav(AUDIO_DIR / "bgm_quiz.wav", bgm * 0.7)
print("Procedural audio files synthesized in milliseconds!")

# 5. Generate Voiceovers using Edge-TTS
voice_lines = [
    ("intro.mp3", "Chào mừng các bạn đến với Thế Giới Trò Chơi và thử thách Rabbit Game! Hôm nay chúng mình cùng tham gia 8 thể loại câu đố siêu đỉnh nhé. Sẵn sàng chưa nào? Bắt đầu thôi!"),
    ("q1_q.mp3", "Câu số 1: Nhìn hai emoji này bạn đoán được từ ghép quen thuộc nào không?"),
    ("q1_a.mp3", "Chính xác rồi! Đáp án đúng là Áo Mưa nha bạn ơi!"),
    ("q2_q.mp3", "Câu số 2: Đây là trò chơi dân gian truyền thống nào của Việt Nam?"),
    ("q2_a.mp3", "Chuẩn luôn bạn yêu! Đó chính là trò chơi Ô Ăn Quan."),
    ("q3_q.mp3", "Câu số 3: Nhìn hình ảnh này, bạn có nhận ra đây là logo câu lạc bộ bóng đá nào không?"),
    ("q3_a.mp3", "Chính xác! Đó là logo câu lạc bộ FC Barcelona."),
    ("q4_q.mp3", "Câu số 4: Thử thách đừng nói giống tôi! Kể tên một môn học, nói trùng với video là thua nha!"),
    ("q4_a.mp3", "Đáp án bí mật là Môn Toán! Ai vừa nói môn Toán là đã bị loại rồi nha."),
    ("q5_q.mp3", "Câu số 5: Messi đã cùng đội tuyển quốc gia nào nâng cao chiếc cúp vô địch World Cup 2022?"),
    ("q5_a.mp3", "Xuất sắc! Đáp án chính xác là B: Đội tuyển Argentina."),
    ("q6_q.mp3", "Câu số 6: Sầu riêng nướng phô mai béo ngậy — Bạn là người chọn Ăn hay Bỏ Qua?"),
    ("q6_a.mp3", "Bạn chọn Ăn hay Bỏ Qua? Hãy để lại bình luận cho chúng mình biết với nhé!"),
    ("q7_q.mp3", "Câu số 7: Thử thách tính nhẩm 5 giây: 90 chia 9 cộng 5 bằng bao nhiêu?"),
    ("q7_a.mp3", "Đáp án chính xác là B: 15. Bạn tính có nhanh không nào?"),
    ("q8_q.mp3", "Câu số 8: Tên tiếng Anh của Con Cáo là gì nhỉ?"),
    ("q8_a.mp3", "Chuẩn luôn! Con cáo trong tiếng Anh là Fox."),
    ("outro.mp3", "Xin chúc mừng bạn đã vượt qua 8 thử thách! Hãy bình luận số câu bạn trả lời đúng và nhớ bấm Like, Đăng ký kênh để đón xem video tiếp theo nhé!"),
]

for filename, text in voice_lines:
    target_path = AUDIO_DIR / filename
    if not target_path.exists():
        cmd = ["python", "-m", "edge_tts", "--text", text, "--voice", "vi-VN-HoaiMyNeural", "--write-media", str(target_path)]
        subprocess.run(cmd, capture_output=True)
        print(f"Synthesized TTS: {filename} ({target_path.exists()})")

print("All audio and voice tracks ready!")
