#!/usr/bin/env python3
"""
Produce Master 4-Cards Comparison Riddle Video (QuizMystra Style):
- 3 Highly Viral Social Riddles:
  1. WHO IS PREGNANT? (Wine vs Espresso vs Pickles/Ice Cream vs Sushi)
  2. WHO IS GOING ON A DATE? (Studying vs Perfume/Dress vs Gym Barbell vs Sleeping)
  3. WHO IS THE MURDERER / KILLER? (Chef vs Doctor vs Bloodstain Cuff vs Gardener)
- Full-Screen 4-Cards Layout with High-Resolution Photography
- Circular Top-Center Number Badges (1, 2, 3, 4)
- Crimson Red Header Banner (#D62626) with Twin-Bell Alarm Clock Countdown (8s -> 0s)
- Winning Card highlights with Emerald Green Glow & Pulsating Border
- Bottom Answer & Logic Explanation Banner
"""

import sys
import time
from pathlib import Path

from app.services.quiz_engine_v2 import (
    QuizVideoEngineV2,
    QuizRenderOptions,
)

MYSTRA_4CARDS_RIDDLES = [
    {
        "id": "card_riddle_01",
        "question": "WHO IS PREGNANT?",
        "cards": [
            {"id": "1", "label": "DRINKING WINE", "image_path": "assets/quizmystra_4cards/p1_wine.jpg"},
            {"id": "2", "label": "ESPRESSO SHOTS", "image_path": "assets/quizmystra_4cards/p2_coffee.jpg"},
            {"id": "3", "label": "PICKLES & ICE CREAM", "image_path": "assets/quizmystra_4cards/p3_cravings.jpg"},
            {"id": "4", "label": "RAW SUSHIS", "image_path": "assets/quizmystra_4cards/p4_sushi.jpg"},
        ],
        "correct_option": "3",
        "explanation_text": "ANSWER: PERSON #3! SHE HAS STRANGE PREGNANCY CRAVINGS (PICKLES & SWEETS)!",
        "voice_q": "Riddle 1: Look closely at these four women. Only one of them is pregnant! Can you spot who it is in 8 seconds?",
        "voice_a": "Number 3 is pregnant! Alcohol, heavy caffeine, and raw fish are avoided during pregnancy, while pickles and ice cream is a classic craving!",
        "countdown_seconds": 8.0,
    },
    {
        "id": "card_riddle_02",
        "question": "WHO IS GOING ON A DATE?",
        "cards": [
            {"id": "1", "label": "LATE NIGHT STUDY", "image_path": "assets/quizmystra_4cards/date_a_study.jpg"},
            {"id": "2", "label": "PERFUME & DRESS", "image_path": "assets/quizmystra_4cards/date_b_ready.jpg"},
            {"id": "3", "label": "HEAVY WORKOUT", "image_path": "assets/quizmystra_4cards/date_c_gym.jpg"},
            {"id": "4", "label": "PAJAMAS IN BED", "image_path": "assets/quizmystra_4cards/date_d_pajamas.jpg"},
        ],
        "correct_option": "2",
        "explanation_text": "ANSWER: GIRL #2! SHE PUT ON PERFUME, RED LIPSTICK, AND A FANCY DRESS!",
        "voice_q": "Riddle 2: Four girls getting ready for the evening. Who is about to head out for a romantic date?",
        "voice_a": "Number 2 is going on a date! Look at her elegant red dress, perfume bottle, and fresh flowers on the table!",
        "countdown_seconds": 8.0,
    },
    {
        "id": "card_riddle_03",
        "question": "WHO IS THE DANGEROUS KILLER?",
        "cards": [
            {"id": "1", "label": "CHEF IN APRON", "image_path": "assets/quizmystra_4cards/killer_a_chef.jpg"},
            {"id": "2", "label": "DOCTOR IN SCRUBS", "image_path": "assets/quizmystra_4cards/killer_b_doctor.jpg"},
            {"id": "3", "label": "NERVOUS SUSPECT", "image_path": "assets/quizmystra_4cards/killer_c_suspect.jpg"},
            {"id": "4", "label": "OFFICE ASSISTANT", "image_path": "assets/quizmystra_4cards/killer_d_gardener.jpg"},
        ],
        "correct_option": "3",
        "explanation_text": "ANSWER: SUSPECT #3! HE GIVES A GUILTY LOOK AND HAS NO WORKING ALIBI!",
        "voice_q": "Riddle 3, Final Investigation! A crime occurred in the building. One of these four suspects is the killer! Who is it?",
        "voice_a": "Number 3 is the killer! Notice his intense guilty stare and nervous expression compared to everyone else working peacefully!",
        "countdown_seconds": 8.0,
    },
]

def main():
    print("=" * 70)
    print("  PRODUCING QUIZMYSTRA-STYLE 4-CARDS RIDDLE VIDEO (FULL PRODUCTION)")
    print("=" * 70)

    out_dir = Path("output/quizmystra_4cards_production")
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / "quizmystra_4cards_riddles_16_9.mp4"

    opt = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        language="en",
        pacing="standard",
        archetype="riddle_mystra",
        countdown_seconds=8.0,
        tts_engine="piper",
        piper_voice="en_US-ryan-high",
        piper_speed=1.02,
        piper_model_dir=Path("D:/ALL AI/TestProjects/Voice/assets/models/piper"),
        piper_exe=Path("D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe"),
        output_path=mp4_path,
        bgm_path=Path("assets/bgm/bgm_cyber_trap.wav"),
    )

    engine = QuizVideoEngineV2(opt)

    print(f"\n[1/2] Rendering 4-Cards Comparison Riddle Video: {mp4_path.name}")
    t0 = time.time()
    rendered_mp4 = engine.render_quiz_video(
        MYSTRA_4CARDS_RIDDLES,
        title="WHO IS WHO? 4-OPTIONS TRICKY RIDDLES"
    )
    elapsed = time.time() - t0

    file_size_mb = rendered_mp4.stat().st_size / (1024 * 1024)
    print(f"\n[2/2] COMPILATION FINISHED!")
    print(f"   -> Output File: {rendered_mp4.resolve()}")
    print(f"   -> File Size:   {file_size_mb:.2f} MB")
    print(f"   -> Render Time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

    import subprocess
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(rendered_mp4)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    dur = float(res.stdout.strip() or 0)
    print(f"   -> Exact Video Duration: {dur:.2f}s ({dur/60:.2f}m)")

    prev_dir = out_dir / "previews"
    prev_dir.mkdir(parents=True, exist_ok=True)

    # Let's extract frames
    probes = [
        ("riddle1_pregnant_guessing.jpg", 15.0),
        ("riddle1_pregnant_reveal.jpg", 23.0),
        ("riddle2_date_guessing.jpg", 40.0),
        ("riddle2_date_reveal.jpg", 48.0),
        ("riddle3_killer_guessing.jpg", 65.0),
        ("riddle3_killer_reveal.jpg", 73.0),
    ]
    for fname, t_sec in probes:
        p = prev_dir / fname
        subprocess.run(["ffmpeg", "-y", "-ss", str(t_sec), "-i", str(rendered_mp4), "-vframes", "1", "-q:v", "2", str(p)], capture_output=True)
        print(f"   Saved preview: {fname} (t={t_sec}s): {p.exists()}")

    print("\n✅ QUIZMYSTRA 4-CARDS RIDDLE VIDEO COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
