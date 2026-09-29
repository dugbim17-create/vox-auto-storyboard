#!/usr/bin/env python3
"""
Produce 30-Question US & World Flag Master Video (5.5 Minutes):
- Full 5 - 6 minute runtime (~340s)
- Authentic US English Narration via Piper (en_US-ryan-high)
- 30 Country Flags (assets/flags/{code}.png) framed with golden trim & drop shadow
- 4-Tier Difficulty Progression: Level 1 (Easy) -> Level 2 (Medium) -> Level 3 (Hard) -> Level 4 (Impossible)
- Cyber Arcade HUD, 3D icons, screen shake, accelerando countdown ticks, and outro scoreboard
"""

import os
import sys
import time
from pathlib import Path
from PIL import Image

from app.services.quiz_engine_v2 import (
    QuizVideoEngineV2,
    QuizRenderOptions,
)

# -------------------------------------------------------------
# 30-QUESTION US MASTER DATASET (30 Questions, ~5.5 Minutes)
# -------------------------------------------------------------

US_FLAG_QUIZ_30 = [
    # LEVEL 1: EASY (Questions 1 - 8)
    {
        "id": "q01",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "STARS & STRIPES", "image_path": "assets/flags/us.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "United Kingdom"}, {"id": "B", "text": "United States"}, {"id": "C", "text": "Australia"}, {"id": "D", "text": "Canada"}],
        "correct_id": "B",
        "answer_text": "UNITED STATES (USA)",
        "voice_q": "Question 1: Which country has the famous Stars and Stripes flag?",
        "voice_a": "That's the United States, home to fifty states!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q02",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "RED MAPLE LEAF", "image_path": "assets/flags/ca.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "New Zealand"}, {"id": "B", "text": "Austria"}, {"id": "C", "text": "Canada"}, {"id": "D", "text": "Switzerland"}],
        "correct_id": "C",
        "answer_text": "CANADA",
        "voice_q": "Question 2: Which country features a bold red maple leaf?",
        "voice_a": "Correct! That is Canada, our northern neighbor!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q03",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "RED SUN DISC", "image_path": "assets/flags/jp.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Japan"}, {"id": "B", "text": "South Korea"}, {"id": "C", "text": "China"}, {"id": "D", "text": "Singapore"}],
        "correct_id": "A",
        "answer_text": "JAPAN",
        "voice_q": "Question 3: A red circle on a crisp white field. Name this Asian nation!",
        "voice_a": "Boom! It's Japan, the Land of the Rising Sun!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q04",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "BLUE WHITE RED", "image_path": "assets/flags/fr.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Italy"}, {"id": "B", "text": "Netherlands"}, {"id": "C", "text": "France"}, {"id": "D", "text": "Russia"}],
        "correct_id": "C",
        "answer_text": "FRANCE",
        "voice_q": "Question 4: Blue, white, and red vertical stripes. What country is this?",
        "voice_a": "Magnifique! That is France!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q05",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "UNION JACK", "image_path": "assets/flags/gb.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Australia"}, {"id": "B", "text": "United Kingdom"}, {"id": "C", "text": "Iceland"}, {"id": "D", "text": "Norway"}],
        "correct_id": "B",
        "answer_text": "UNITED KINGDOM (UK)",
        "voice_q": "Question 5: Which nation flies the historic Union Jack?",
        "voice_a": "You got it! It's the United Kingdom!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q06",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "BLACK RED GOLD", "image_path": "assets/flags/de.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Belgium"}, {"id": "B", "text": "Poland"}, {"id": "C", "text": "Germany"}, {"id": "D", "text": "Spain"}],
        "correct_id": "C",
        "answer_text": "GERMANY",
        "voice_q": "Question 6: Black, red, and gold horizontal stripes belong to which country?",
        "voice_a": "Wunderbar! That is Germany!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q07",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "GOLDEN EAGLE", "image_path": "assets/flags/mx.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Mexico"}, {"id": "B", "text": "Italy"}, {"id": "C", "text": "Portugal"}, {"id": "D", "text": "Brazil"}],
        "correct_id": "A",
        "answer_text": "MEXICO",
        "voice_q": "Question 7: Green, white, and red with an eagle perched on a cactus!",
        "voice_a": "Viva Mexico! That is Mexico!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q08",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "ROYAL CREST", "image_path": "assets/flags/es.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Portugal"}, {"id": "B", "text": "Spain"}, {"id": "C", "text": "Colombia"}, {"id": "D", "text": "Venezuela"}],
        "correct_id": "B",
        "answer_text": "SPAIN",
        "voice_q": "Question 8: Red and yellow stripes with a royal coat of arms. Final question of Level 1!",
        "voice_a": "It's Spain! Level 1 complete, are you ready for Level 2?",
        "countdown_seconds": 4.0,
    },

    # LEVEL 2: MEDIUM (Questions 9 - 16)
    {
        "id": "q09",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "DUTCH TRICOLOR", "image_path": "assets/flags/nl.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "France"}, {"id": "B", "text": "Russia"}, {"id": "C", "text": "Netherlands"}, {"id": "D", "text": "Luxembourg"}],
        "correct_id": "C",
        "answer_text": "NETHERLANDS",
        "voice_q": "Question 9: Level 2 begins! Red, white, and blue horizontal stripes. Don't confuse it with France!",
        "voice_a": "That's the Netherlands, the land of windmills!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q10",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "EMERALD ISLE", "image_path": "assets/flags/ie.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Ireland"}, {"id": "B", "text": "Ivory Coast"}, {"id": "C", "text": "India"}, {"id": "D", "text": "Italy"}],
        "correct_id": "A",
        "answer_text": "IRELAND",
        "voice_q": "Question 10: Green, white, and orange vertical stripes. Make sure you don't pick Ivory Coast!",
        "voice_a": "It's Ireland! Green starts on the flagpole side!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q11",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "4 RED STARS", "image_path": "assets/flags/nz.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Australia"}, {"id": "B", "text": "New Zealand"}, {"id": "C", "text": "Fiji"}, {"id": "D", "text": "Tuvalu"}],
        "correct_id": "B",
        "answer_text": "NEW ZEALAND",
        "voice_q": "Question 11: Pay close attention to the stars! Four red stars outlined in white.",
        "voice_a": "That is New Zealand! Australia has six white stars!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q12",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "ORDER & PROGRESS", "image_path": "assets/flags/br.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Argentina"}, {"id": "B", "text": "Jamaica"}, {"id": "C", "text": "Brazil"}, {"id": "D", "text": "South Africa"}],
        "correct_id": "C",
        "answer_text": "BRAZIL",
        "voice_q": "Question 12: A vibrant green field with a yellow diamond and starry blue globe.",
        "voice_a": "It's Brazil, football champions of the world!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q13",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "SQUARE FLAG", "image_path": "assets/flags/ch.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Denmark"}, {"id": "B", "text": "Switzerland"}, {"id": "C", "text": "Norway"}, {"id": "D", "text": "Sweden"}],
        "correct_id": "B",
        "answer_text": "SWITZERLAND",
        "voice_q": "Question 13: One of only two square national flags, featuring a bold white cross.",
        "voice_a": "Yes, that's Switzerland in the heart of the Alps!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q14",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "RAINBOW NATION", "image_path": "assets/flags/za.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Kenya"}, {"id": "B", "text": "Nigeria"}, {"id": "C", "text": "Ghana"}, {"id": "D", "text": "South Africa"}],
        "correct_id": "D",
        "answer_text": "SOUTH AFRICA",
        "voice_q": "Question 14: Six vibrant colors forming a horizontal Y pattern.",
        "voice_a": "It's South Africa, the Rainbow Nation!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q15",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "SUN OF MAY", "image_path": "assets/flags/ar.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Argentina"}, {"id": "B", "text": "Uruguay"}, {"id": "C", "text": "Greece"}, {"id": "D", "text": "Guatemala"}],
        "correct_id": "A",
        "answer_text": "ARGENTINA",
        "voice_q": "Question 15: Sky blue and white horizontal bands featuring the smiling Sun of May.",
        "voice_a": "That is Argentina, home of Messi and tango!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q16",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "YELLOW BLUE RED", "image_path": "assets/flags/co.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Venezuela"}, {"id": "B", "text": "Ecuador"}, {"id": "C", "text": "Colombia"}, {"id": "D", "text": "Romania"}],
        "correct_id": "C",
        "answer_text": "COLOMBIA",
        "voice_q": "Question 16: Yellow, blue, and red with no stars or symbols. Final question of Level 2!",
        "voice_a": "It's Colombia! Level 2 complete. Things are about to get real tough!",
        "countdown_seconds": 4.0,
    },

    # LEVEL 3: HARD (Questions 17 - 24)
    {
        "id": "q17",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "NORDIC CROSS", "image_path": "assets/flags/ax.png", "prompt": "NAME THIS TERRITORY"}],
        "choices": [{"id": "A", "text": "Sweden"}, {"id": "B", "text": "Finland"}, {"id": "C", "text": "Aland Islands"}, {"id": "D", "text": "Norway"}],
        "correct_id": "C",
        "answer_text": "ALAND ISLANDS",
        "voice_q": "Question 17: Level 3 Hard begins! A blue field with a yellow and red Nordic cross.",
        "voice_a": "That's the Aland Islands, an autonomous region of Finland!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q18",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "CROWN & 7 STARS", "image_path": "assets/flags/tj.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Tajikistan"}, {"id": "B", "text": "Iran"}, {"id": "C", "text": "Hungary"}, {"id": "D", "text": "Bulgaria"}],
        "correct_id": "A",
        "answer_text": "TAJIKISTAN",
        "voice_q": "Question 18: Red, white, and green featuring a crown surrounded by seven golden stars.",
        "voice_a": "Impressive! That is Tajikistan in Central Asia!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q19",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "GREY CRANE", "image_path": "assets/flags/ug.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Rwanda"}, {"id": "B", "text": "Uganda"}, {"id": "C", "text": "Tanzania"}, {"id": "D", "text": "Zimbabwe"}],
        "correct_id": "B",
        "answer_text": "UGANDA",
        "voice_q": "Question 19: Black, yellow, and red stripes with a crested crane in the white circle.",
        "voice_a": "It's Uganda, the Pearl of Africa!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q20",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "RISING RED SUN", "image_path": "assets/flags/mw.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Kenya"}, {"id": "B", "text": "Zambia"}, {"id": "C", "text": "Malawi"}, {"id": "D", "text": "South Sudan"}],
        "correct_id": "C",
        "answer_text": "MALAWI",
        "voice_q": "Question 20: Black, red, and green with a rising red sun of hope.",
        "voice_a": "Great job if you knew that! It's Malawi!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q21",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "BLACK TRIDENT", "image_path": "assets/flags/bb.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Barbados"}, {"id": "B", "text": "Bahamas"}, {"id": "C", "text": "Saint Lucia"}, {"id": "D", "text": "Curacao"}],
        "correct_id": "A",
        "answer_text": "BARBADOS",
        "voice_q": "Question 21: Ultramarine blue and gold with a black trident head in the center.",
        "voice_a": "That's Barbados, the jewel of the Caribbean!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q22",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "CRESCENT & STARS", "image_path": "assets/flags/sg.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Turkey"}, {"id": "B", "text": "Malaysia"}, {"id": "C", "text": "Singapore"}, {"id": "D", "text": "Tunisia"}],
        "correct_id": "C",
        "answer_text": "SINGAPORE",
        "voice_q": "Question 22: Red and white horizontal halves with a white crescent and five stars.",
        "voice_a": "Correct! That is Singapore, the Lion City!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q23",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "STEPPE EAGLE", "image_path": "assets/flags/kz.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Mongolia"}, {"id": "B", "text": "Kazakhstan"}, {"id": "C", "text": "Uzbekistan"}, {"id": "D", "text": "Kyrgyzstan"}],
        "correct_id": "B",
        "answer_text": "KAZAKHSTAN",
        "voice_q": "Question 23: Sky blue field with a golden sun and soaring steppe eagle.",
        "voice_a": "Magnificent Kazakhstan! The world's largest landlocked country!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q24",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "DOUBLE TRIANGLE", "image_path": "assets/flags/np.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Bhutan"}, {"id": "B", "text": "Vatican City"}, {"id": "C", "text": "Nepal"}, {"id": "D", "text": "Monaco"}],
        "correct_id": "C",
        "answer_text": "NEPAL",
        "voice_q": "Question 24: The only non-quadrilateral national flag in the world!",
        "voice_a": "It's Nepal! Home of Mount Everest! Level 3 complete!",
        "countdown_seconds": 4.0,
    },

    # LEVEL 4: IMPOSSIBLE / GOD LEVEL (Questions 25 - 30)
    {
        "id": "q25",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "ASSAULT RIFLE", "image_path": "assets/flags/mz.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Mozambique"}, {"id": "B", "text": "Angola"}, {"id": "C", "text": "Burkina Faso"}, {"id": "D", "text": "Guinea-Bissau"}],
        "correct_id": "A",
        "answer_text": "MOZAMBIQUE",
        "voice_q": "Question 25: Level 4 Impossible! The only national flag featuring a modern assault rifle with bayonet.",
        "voice_a": "Incredible! That is Mozambique in Southeast Africa!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q26",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "THUNDER DRAGON", "image_path": "assets/flags/bt.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Wales"}, {"id": "B", "text": "Bhutan"}, {"id": "C", "text": "Sri Lanka"}, {"id": "D", "text": "Cambodia"}],
        "correct_id": "B",
        "answer_text": "BHUTAN",
        "voice_q": "Question 26: Yellow and orange diagonal split with Druk the Thunder Dragon.",
        "voice_a": "That is the Himalayan kingdom of Bhutan!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q27",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "THREE TOWERS", "image_path": "assets/flags/sm.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Andorra"}, {"id": "B", "text": "Liechtenstein"}, {"id": "C", "text": "San Marino"}, {"id": "D", "text": "Monaco"}],
        "correct_id": "C",
        "answer_text": "SAN MARINO",
        "voice_q": "Question 27: White and light blue featuring three fortified mountain peaks.",
        "voice_a": "Spot on! That is the ancient republic of San Marino!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q28",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "SISSEROU PARROT", "image_path": "assets/flags/dm.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Dominica"}, {"id": "B", "text": "Fiji"}, {"id": "C", "text": "Palau"}, {"id": "D", "text": "Tuvalu"}],
        "correct_id": "A",
        "answer_text": "DOMINICA",
        "voice_q": "Question 28: Look closely at the parrot! One of the few flags with purple feathers.",
        "voice_a": "That is Dominica, not to be confused with Dominican Republic!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q29",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "MACHETE & GEAR", "image_path": "assets/flags/ao.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Vietnam"}, {"id": "B", "text": "Angola"}, {"id": "C", "text": "Congo"}, {"id": "D", "text": "East Timor"}],
        "correct_id": "B",
        "answer_text": "ANGOLA",
        "voice_q": "Question 29: Red and black horizontal bands with a crossed machete and cogwheel.",
        "voice_a": "You got it! That is Angola!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q30",
        "question": "FINAL QUESTION: NAME THIS ISLAND!",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "12-POINT STAR", "image_path": "assets/flags/nr.png", "prompt": "NAME THIS PACIFIC NATION"}],
        "choices": [{"id": "A", "text": "Kiribati"}, {"id": "B", "text": "Tuvalu"}, {"id": "C", "text": "Marshall Islands"}, {"id": "D", "text": "Nauru"}],
        "correct_id": "D",
        "answer_text": "NAURU",
        "voice_q": "Question 30, THE FINAL BOSS! Blue field, gold equator line, and a 12-pointed star. What tiny island nation is this?",
        "voice_a": "It's Nauru, the world's smallest island nation! Did you get it right?!",
        "countdown_seconds": 4.5,
    },
]

# -------------------------------------------------------------
# EXECUTION WORKFLOW
# -------------------------------------------------------------

def main():
    print("=" * 65)
    print("  PRODUCING 30-QUESTION US MASTER QUIZ VIDEO (5.5 MINUTES)")
    print("=" * 65)

    out_dir = Path("output/us_flag_quiz_5min")
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / "us_world_flag_quiz_master_16_9.mp4"

    opt = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        language="en",
        pacing="standard",
        countdown_seconds=4.0,
        tts_engine="piper",
        piper_voice="en_US-ryan-high",
        piper_speed=1.05,
        piper_model_dir=Path("D:/ALL AI/TestProjects/Voice/assets/models/piper"),
        piper_exe=Path("D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe"),
        output_path=mp4_path,
        mascot_type="loc",
        bg_theme="cyber",
    )

    engine = QuizVideoEngineV2(opt)

    print(f"\n[1/2] Initializing 30-question video compilation for: {mp4_path.name}")
    t0 = time.time()
    rendered_mp4 = engine.render_quiz_video(
        US_FLAG_QUIZ_30,
        title="THE ULTIMATE WORLD FLAG CHALLENGE"
    )
    elapsed = time.time() - t0

    file_size_mb = rendered_mp4.stat().st_size / (1024 * 1024)
    print(f"\n[2/2] COMPILATION FINISHED!")
    print(f"   -> Output File: {rendered_mp4.resolve()}")
    print(f"   -> File Size:   {file_size_mb:.2f} MB")
    print(f"   -> Render Time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

    # Probe duration with ffprobe
    import subprocess
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(rendered_mp4)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    dur = float(res.stdout.strip() or 0)
    print(f"   -> Exact Video Duration: {dur:.2f} seconds ({dur/60:.2f} minutes)")

    # Extract verification frames
    prev_dir = out_dir / "previews"
    prev_dir.mkdir(parents=True, exist_ok=True)
    frames_to_extract = [
        ("frame_q1_usa.jpg", 12.0),
        ("frame_q11_nz.jpg", 115.0),
        ("frame_q24_nepal.jpg", 255.0),
        ("frame_q30_nauru.jpg", 315.0),
        ("frame_outro_scoreboard.jpg", dur - 2.0),
    ]
    for fname, t_sec in frames_to_extract:
        p = prev_dir / fname
        subprocess.run(["ffmpeg", "-y", "-ss", str(t_sec), "-i", str(rendered_mp4), "-vframes", "1", "-q:v", "2", str(p)], capture_output=True)
        print(f"   Saved preview: {fname} (t={t_sec}s): {p.exists()}")

    print("\n✅ 30-QUESTION US MASTER QUIZ VIDEO COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
