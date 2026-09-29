#!/usr/bin/env python3
"""
Produce Master QuizMystra-Style Visual Riddle Video:
- 100% Matching https://www.youtube.com/watch?v=7YBR03r0qMg (QuizMystra)
- Full-Screen Atmospheric Storytelling Scenes (1920x940)
- Crimson Red Header Banner (#D62626) with Impact Bold drop-shadow text
- Twin-Bell Alarm Clock countdown widget ticking down (10 -> 0)
- Animated Red Circle / Arrow Callout pointing at the exact visual clue upon reveal
- Voiceover explaining the logic breakdown
- Fast, high-energy render
"""

import sys
import time
from pathlib import Path

from app.services.quiz_engine_v2 import (
    QuizVideoEngineV2,
    QuizRenderOptions,
)

# -------------------------------------------------------------
# 5 MASTER VISUAL LOGIC RIDDLES (QuizMystra Format)
# -------------------------------------------------------------

QUIZMYSTRA_RIDDLES = [
    {
        "id": "riddle_01",
        "question": "WHO IS THE SLEEPWALKER?",
        "scene_image": "assets/riddles/riddle_01_study.jpg",
        "options": ["1", "2", "3", "4"],
        "option_coords": [
            [280, 240],   # Person 1 (Study)
            [720, 240],   # Person 2 (Kitchen)
            [1200, 240],  # Person 3 (Staircase)
            [1650, 240],  # Person 4 (Living Room)
        ],
        "correct_option": "3",
        "clue_highlight": {
            "coord": [1200, 840],     # Feet of Person 3
            "radius": 80,
            "arrow_from": [1200, 720],
        },
        "explanation_text": "ANSWER: PERSON 3! HE PUT ON TWO DIFFERENT SLIPPERS IN HIS SLEEP!",
        "voice_q": "Riddle 1: Look closely at these four rooms late at night. One of these people is sleepwalking! Can you spot who it is?",
        "voice_a": "Time's up! The sleepwalker is number 3! Look at his feet: he unconsciously put on two completely different slippers, including the pink one!",
        "countdown_seconds": 8.0,
    },
    {
        "id": "riddle_02",
        "question": "WHICH LAB HAS A DANGEROUS CHEMICAL LEAK?",
        "scene_image": "assets/riddles/riddle_02_laboratory.jpg",
        "options": ["A", "B", "C"],
        "option_coords": [
            [380, 250],   # Station A
            [960, 250],   # Station B
            [1540, 250],  # Station C
        ],
        "correct_option": "B",
        "clue_highlight": {
            "coord": [960, 680],     # Vapor rising from beaker in Station B
            "radius": 90,
            "arrow_from": [960, 520],
        },
        "explanation_text": "ANSWER: STATION B! ACID VAPOR IS MELTING THE TABLETOP SENSOR!",
        "voice_q": "Riddle 2: Safety inspection! In this high-tech facility, one workstation has an active chemical breach. Which station is it?",
        "voice_a": "Station B! Look at the green acid vapor dissolving the digital sensor on the workbench!",
        "countdown_seconds": 8.0,
    },
    {
        "id": "riddle_03",
        "question": "WHO IS THE SNEAKY THIEF AT THE MANSION?",
        "scene_image": "assets/riddles/riddle_03_mansion.jpg",
        "options": ["1", "2", "3", "4"],
        "option_coords": [
            [260, 250],
            [710, 250],
            [1190, 250],
            [1660, 250],
        ],
        "correct_option": "2",
        "clue_highlight": {
            "coord": [710, 780],     # Bulging pocket with diamond necklace hanging out
            "radius": 75,
            "arrow_from": [710, 630],
        },
        "explanation_text": "ANSWER: GUEST #2! THE DIAMOND NECKLACE IS FALLING OUT OF HIS COAT!",
        "voice_q": "Riddle 3: A priceless diamond necklace vanished during the party. One of these four suspects has it! Who is the thief?",
        "voice_a": "Number 2 is the thief! Look at the sparkling diamond necklace dangling right out of his right coat pocket!",
        "countdown_seconds": 8.0,
    },
    {
        "id": "riddle_04",
        "question": "WHICH PAINTING IS A FORGERY?",
        "scene_image": "assets/riddles/riddle_04_gallery.jpg",
        "options": ["A", "B", "C"],
        "option_coords": [
            [380, 260],
            [960, 260],
            [1540, 260],
        ],
        "correct_option": "C",
        "clue_highlight": {
            "coord": [1540, 620],    # Modern wristwatch in a 16th century renaissance portrait
            "radius": 85,
            "arrow_from": [1540, 480],
        },
        "explanation_text": "ANSWER: PAINTING C! THE RENAISSANCE KNIGHT IS WEARING A DIGITAL WATCH!",
        "voice_q": "Riddle 4: Art gallery mystery! One of these three classical masterpieces is an obvious fake. Can your eyes spot the flaw?",
        "voice_a": "Painting C is a fake! The medieval knight from the sixteenth century is wearing a modern digital wristwatch!",
        "countdown_seconds": 8.0,
    },
    {
        "id": "riddle_05",
        "question": "WHICH GLASS CONTAINS THE DEADLY POISON?",
        "scene_image": "assets/riddles/riddle_05_potions.jpg",
        "options": ["1", "2", "3"],
        "option_coords": [
            [420, 260],
            [960, 260],
            [1500, 260],
        ],
        "correct_option": "1",
        "clue_highlight": {
            "coord": [420, 720],     # Ice cubes sinking instead of floating
            "radius": 85,
            "arrow_from": [420, 560],
        },
        "explanation_text": "ANSWER: GLASS #1! THE ICE CUBES ARE SINKING TO THE BOTTOM!",
        "voice_q": "Riddle 5, The Final Logic Test! Three glasses of iced drink, but one was poisoned with heavy toxic liquid. Which glass is lethal?",
        "voice_a": "Glass number 1! Ice normally floats in water, but the poison is so dense that the ice cubes sank straight to the bottom!",
        "countdown_seconds": 8.0,
    },
]

def main():
    print("=" * 70)
    print("  PRODUCING QUIZMYSTRA-STYLE CINEMATIC RIDDLE VIDEO")
    print("=" * 70)

    out_dir = Path("output/quizmystra_style_production")
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / "quizmystra_master_riddles_16_9.mp4"

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

    print(f"\n[1/2] Rendering QuizMystra Riddle Video: {mp4_path.name}")
    t0 = time.time()
    rendered_mp4 = engine.render_quiz_video(
        QUIZMYSTRA_RIDDLES,
        title="15 TRICKY RIDDLES TO TEST YOUR LOGIC"
    )
    elapsed = time.time() - t0

    file_size_mb = rendered_mp4.stat().st_size / (1024 * 1024)
    print(f"\n[2/2] COMPILATION FINISHED!")
    print(f"   -> Output File: {rendered_mp4.resolve()}")
    print(f"   -> File Size:   {file_size_mb:.2f} MB")
    print(f"   -> Render Time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

    # Extract preview frames
    import subprocess
    prev_dir = out_dir / "previews"
    prev_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(rendered_mp4)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    dur = float(res.stdout.strip() or 0)
    print(f"   -> Exact Video Duration: {dur:.2f}s ({dur/60:.2f}m)")

    # Extract frames during guessing and during reveal
    probes = [
        ("riddle1_sleepwalker_guessing.jpg", 14.0),
        ("riddle1_sleepwalker_reveal_circle.jpg", 22.0),
        ("riddle2_lab_guessing.jpg", 38.0),
        ("riddle2_lab_reveal_circle.jpg", 48.0),
        ("riddle3_thief_reveal_circle.jpg", 75.0),
        ("riddle4_fake_painting_reveal.jpg", 100.0),
        ("riddle5_poison_reveal_circle.jpg", 125.0),
    ]
    for fname, t_sec in probes:
        p = prev_dir / fname
        subprocess.run(["ffmpeg", "-y", "-ss", str(t_sec), "-i", str(rendered_mp4), "-vframes", "1", "-q:v", "2", str(p)], capture_output=True)
        print(f"   Saved preview: {fname} (t={t_sec}s): {p.exists()}")

    print("\n✅ QUIZMYSTRA-STYLE CINEMATIC RIDDLE VIDEO COMPLETED!")

if __name__ == "__main__":
    main()
