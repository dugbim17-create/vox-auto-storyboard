#!/usr/bin/env python3
"""
Test 3 Distinct, Non-Overlapping Quiz Modes via JSON Ingestion:
- Mode 1: QuizMystra 4-Cards Comparison (WHO IS PREGNANT? - 4 Cards with Badges 1, 2, 3, 4)
- Mode 2: QuizMystra Visual Riddle (WHICH LAB HAS A DANGEROUS CHEMICAL LEAK? - Full-Screen Scene + Red Circle & Arrow Reveal)
- Mode 3: Cyber Arcade Photo Reveal (WHAT IS THE CAPITAL OF FRANCE? - 4 Choices + Golden-Framed Eiffel Tower Photo Reveal)

Validates that pasting a mixed-mode JSON correctly instructs the engine
to switch visual layouts dynamically between questions without crashing.
"""

import json
import time
import subprocess
from pathlib import Path

from app.services.quiz_engine_v2 import (
    QuizVideoEngineV2,
    QuizRenderOptions,
)

# 1. The Exact JSON that the user can paste into the tool
TEST_MIXED_3_MODES_JSON = [
    # MODE 1: QuizMystra 4-Cards Comparison
    {
        "id": "q1_4cards",
        "question": "WHO IS PREGNANT?",
        "cards": [
            {"id": "1", "label": "DRINKING WINE", "image_path": "assets/quizmystra_4cards/p1_wine.jpg"},
            {"id": "2", "label": "ESPRESSO SHOTS", "image_path": "assets/quizmystra_4cards/p2_coffee.jpg"},
            {"id": "3", "label": "PICKLES & ICE CREAM", "image_path": "assets/quizmystra_4cards/p3_cravings.jpg"},
            {"id": "4", "label": "RAW SUSHIS", "image_path": "assets/quizmystra_4cards/p4_sushi.jpg"}
        ],
        "correct_option": "3",
        "explanation_text": "ANSWER: PERSON #3! SHE HAS STRANGE PREGNANCY CRAVINGS!",
        "voice_q": "Riddle 1: Look closely at these four women. Only one of them is pregnant! Can you spot who it is?",
        "voice_a": "Number 3 is pregnant! Pickles and ice cream is a classic pregnancy craving!",
        "countdown_seconds": 6.0
    },

    # MODE 2: QuizMystra Full-Screen Visual Riddle (Red Circle / Arrow Clue Callout)
    {
        "id": "q2_visual_riddle",
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
            "coord": [960, 680],
            "radius": 90,
            "arrow_from": [960, 520],
        },
        "explanation_text": "ANSWER: STATION B! ACID VAPOR IS MELTING THE SENSOR!",
        "voice_q": "Riddle 2: In this high-tech lab, one workstation has a dangerous chemical leak! Which station is it?",
        "voice_a": "Station B! Look at the green acid vapor dissolving the sensor on the table!",
        "countdown_seconds": 6.0
    },

    # MODE 3: Cyber Arcade Photo Reveal (Multiple Choice with Golden Photo Reveal)
    {
        "id": "q3_photo_reveal",
        "question": "WHAT IS THE CAPITAL OF FRANCE?",
        "universe": "CAPITAL CITY",
        "choices": [
            {"id": "A", "text": "Lyon"},
            {"id": "B", "text": "Marseille"},
            {"id": "C", "text": "Paris"},
            {"id": "D", "text": "Nice"}
        ],
        "correct_id": "C",
        "answer_text": "PARIS",
        "reveal_image_path": "assets/landmarks/paris.jpg",
        "voice_q": "Question 3: Geography test! What is the official capital city of France?",
        "voice_a": "Of course, it's Paris, the City of Light!",
        "countdown_seconds": 4.0
    }
]

def main():
    print("=" * 70)
    print("  TESTING 3 DISTINCT NON-OVERLAPPING QUIZ MODES VIA JSON")
    print("=" * 70)

    # 1. Save JSON to presets
    presets_dir = Path("presets")
    presets_dir.mkdir(parents=True, exist_ok=True)
    json_path = presets_dir / "test_3_distinct_modes.json"
    json_path.write_text(json.dumps(TEST_MIXED_3_MODES_JSON, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"1. Saved test JSON to: {json_path}")

    # 2. Output path for video
    out_dir = Path("output/test_json_3_modes")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / "quiz_3_distinct_modes_test.mp4"

    opt = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        language="en",
        pacing="standard",
        countdown_seconds=6.0,
        tts_engine="piper",
        piper_voice="en_US-ryan-high",
        piper_model_dir=Path("D:/ALL AI/TestProjects/Voice/assets/models/piper"),
        piper_exe=Path("D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe"),
        output_path=out_mp4,
        bgm_path=Path("assets/bgm/bgm_cyber_trap.wav"),
    )

    engine = QuizVideoEngineV2(opt)

    print(f"\n2. Rendering video with 3 distinct dynamic modes: {out_mp4.name}")
    t0 = time.time()
    rendered = engine.render_quiz_video(
        TEST_MIXED_3_MODES_JSON,
        title="3 TRICKY RIDDLES IN 3 DIFFERENT MODES"
    )
    elapsed = time.time() - t0

    size_mb = rendered.stat().st_size / (1024 * 1024)
    print(f"\n3. RENDER COMPLETE!")
    print(f"   -> File: {rendered.resolve()}")
    print(f"   -> Size: {size_mb:.2f} MB")
    print(f"   -> Time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

    # Probe duration
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(rendered)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    dur = float(res.stdout.strip() or 0)
    print(f"   -> Duration: {dur:.2f} seconds ({dur/60:.2f} minutes)")

    # 4. Extract verification preview frames for each mode
    prev_dir = out_dir / "previews"
    prev_dir.mkdir(parents=True, exist_ok=True)

    # Let's inspect timeline to extract exact frames
    audio_dir = out_dir / "audio_cache"
    v_intro = engine._probe_dur(audio_dir / "intro.wav") + 0.5
    v_q1_q = engine._probe_dur(audio_dir / "q1_q.wav") + 0.3
    v_q1_cd = 6.0
    v_q1_a = engine._probe_dur(audio_dir / "q1_a.wav") + 0.8
    t_q1_guess = v_intro + v_q1_q / 2
    t_q1_rev = v_intro + v_q1_q + v_q1_cd + 1.0

    t_q2_start = v_intro + v_q1_q + v_q1_cd + v_q1_a
    v_q2_q = engine._probe_dur(audio_dir / "q2_q.wav") + 0.3
    v_q2_cd = 6.0
    v_q2_a = engine._probe_dur(audio_dir / "q2_a.wav") + 0.8
    t_q2_guess = t_q2_start + v_q2_q / 2
    t_q2_rev = t_q2_start + v_q2_q + v_q2_cd + 1.0

    t_q3_start = t_q2_start + v_q2_q + v_q2_cd + v_q2_a
    v_q3_q = engine._probe_dur(audio_dir / "q3_q.wav") + 0.3
    v_q3_cd = 4.0
    t_q3_guess = t_q3_start + v_q3_q / 2
    t_q3_rev = t_q3_start + v_q3_q + v_q3_cd + 1.0

    probes = [
        ("mode1_4cards_guessing.jpg", t_q1_guess),
        ("mode1_4cards_reveal.jpg", t_q1_rev),
        ("mode2_visual_riddle_guessing.jpg", t_q2_guess),
        ("mode2_visual_riddle_reveal.jpg", t_q2_rev),
        ("mode3_photo_reveal_guessing.jpg", t_q3_guess),
        ("mode3_photo_reveal_reveal.jpg", t_q3_rev),
    ]

    for fname, t_sec in probes:
        p = prev_dir / fname
        subprocess.run(["ffmpeg", "-y", "-ss", str(t_sec), "-i", str(rendered), "-vframes", "1", "-q:v", "2", str(p)], capture_output=True)
        print(f"   Extracted {fname} (t={t_sec:.1f}s): {p.exists()}")

    print("\n✅ TEST EXECUTED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
