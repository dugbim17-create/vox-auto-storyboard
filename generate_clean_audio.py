import numpy as np
import wave
from pathlib import Path

out_dir = Path("tmp/clean_audio")
out_dir.mkdir(parents=True, exist_ok=True)
sr = 48000

def write_wav(path, data, sample_rate=48000):
    data = np.clip(data, -1.0, 1.0)
    int_data = (data * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(int_data.tobytes())

# 1. Answer Ding / Bell (C6 Major Triad with Bell envelope) - 100% clean
dur = 1.8
t = np.linspace(0, dur, int(sr * dur), endpoint=False)
ding = (
    0.45 * np.sin(2 * np.pi * 1046.5 * t) * np.exp(-t * 3.5) +
    0.35 * np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 4.0) +
    0.30 * np.sin(2 * np.pi * 1568.0 * t) * np.exp(-t * 4.5) +
    0.20 * np.sin(2 * np.pi * 2093.0 * t) * np.exp(-t * 6.0)
)
write_wav(out_dir / "sfx_ding_clean.wav", ding)

# 2. Countdown Tick-Tock (Clock tick every 1.0s and wooden click every 0.5s) - 100% clean
dur_cd = 4.0
t_cd = np.linspace(0, dur_cd, int(sr * dur_cd), endpoint=False)
ticks = np.zeros_like(t_cd)
for click_t in np.arange(0.0, dur_cd, 0.5):
    idx = int(click_t * sr)
    click_len = int(0.08 * sr)
    if idx + click_len <= len(t_cd):
        t_sub = np.linspace(0, 0.08, click_len, endpoint=False)
        freq = 1400 if int(click_t * 2) % 2 == 0 else 900
        click = 0.6 * np.sin(2 * np.pi * freq * t_sub) * np.exp(-t_sub * 80)
        ticks[idx:idx + click_len] += click
write_wav(out_dir / "sfx_countdown_clean.wav", ticks)

# 3. Clean BGM (Playful Quiz Music: Marimba and Bass groove, 120 BPM) - 100% clean
bpm = 120
beat_s = 60.0 / bpm
bgm_dur = 65.0
t_bgm = np.linspace(0, bgm_dur, int(sr * bgm_dur), endpoint=False)
bgm = np.zeros_like(t_bgm)

notes = [261.63, 329.63, 392.00, 440.00, 523.25, 392.00, 329.63, 293.66]
bass_notes = [130.81, 130.81, 164.81, 164.81, 174.61, 174.61, 196.00, 196.00]

note_idx = 0
for step_t in np.arange(0.0, bgm_dur, beat_s / 2):
    idx = int(step_t * sr)
    n_len = int(0.22 * sr)
    if idx + n_len <= len(t_bgm):
        t_sub = np.linspace(0, 0.22, n_len, endpoint=False)
        freq = notes[note_idx % len(notes)]
        marimba = 0.22 * np.sin(2 * np.pi * freq * t_sub) * np.exp(-t_sub * 16) + \
                  0.10 * np.sin(2 * np.pi * freq * 2 * t_sub) * np.exp(-t_sub * 24)
        bgm[idx:idx + n_len] += marimba
        note_idx += 1

bass_idx = 0
for step_t in np.arange(0.0, bgm_dur, beat_s):
    idx = int(step_t * sr)
    n_len = int(0.4 * sr)
    if idx + n_len <= len(t_bgm):
        t_sub = np.linspace(0, 0.4, n_len, endpoint=False)
        freq = bass_notes[bass_idx % len(bass_notes)]
        bass = 0.30 * np.sin(2 * np.pi * freq * t_sub) * np.exp(-t_sub * 8)
        bgm[idx:idx + n_len] += bass
        bass_idx += 1

for step_t in np.arange(0.0, bgm_dur, beat_s / 4):
    idx = int(step_t * sr)
    n_len = int(0.03 * sr)
    if idx + n_len <= len(t_bgm):
        noise = np.random.uniform(-0.04, 0.04, n_len)
        bgm[idx:idx + n_len] += noise

write_wav(out_dir / "bgm_clean.wav", bgm * 0.7)
print("Synthesized 100% clean, pure SFX and BGM without any voice bleed!")
