#!/usr/bin/env python3
"""
Produce 30-Question US Multi-Mode Dynamic Quiz Video (5.5 - 6 Minutes):
- Rotating Gameplay Modes:
  1. Flag Identification (Framed Flag + Golden Trim)
  2. Capital City Rapid Fire (Tricky Misconceptions: Australia -> Canberra, Brazil -> Brasilia)
  3. Symbol / Rebus Decoder (3 Iconic Clues -> Name Country)
  4. Odd One Out / Geography Riddle (Landlocked, Color Exclusions)
  5. This or That: Travel Battle (Tokyo vs Paris)
  6. Mystery Lucky Travel Box (Box A, B, C)
  7. Final Boss Endgame Challenge
- High-Energy Studio BGM (bgm_cyber_trap.wav) with dynamic audio ducking
- 100% US Native English Narration via Piper (en_US-ryan-high)
- Cyber Arcade HUD, 3D icons, screen shake, and Arcade Scoreboard
"""

import sys
import time
from pathlib import Path

from app.services.quiz_engine_v2 import (
    QuizVideoEngineV2,
    QuizRenderOptions,
)

# -------------------------------------------------------------
# 30-QUESTION MULTI-MODE DYNAMIC DATASET (30 Questions, ~5.5 Min)
# -------------------------------------------------------------

US_MULTIMODE_QUIZ_30 = [
    # ROUND 1: LEVEL 1 EASY — FLAGS & CAPITALS WARM-UP (Q1 - Q6)
    {
        "id": "q01",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "STARS & STRIPES", "image_path": "assets/flags/us.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "United Kingdom"}, {"id": "B", "text": "United States"}, {"id": "C", "text": "Australia"}, {"id": "D", "text": "Canada"}],
        "correct_id": "B",
        "answer_text": "UNITED STATES (USA)",
        "voice_q": "Question 1: Starting easy! Which country has the famous Stars and Stripes flag?",
        "voice_a": "That's the United States, home of the free!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q02",
        "question": "WHAT IS THE CAPITAL OF FRANCE?",
        "universe": "CAPITAL CITY",
        "choices": [{"id": "A", "text": "Lyon"}, {"id": "B", "text": "Marseille"}, {"id": "C", "text": "Paris"}, {"id": "D", "text": "Nice"}],
        "correct_id": "C",
        "answer_text": "PARIS",
        "reveal_image_path": "assets/landmarks/paris.jpg",
        "voice_q": "Question 2: Geography test! What is the official capital city of France?",
        "voice_a": "Of course, it's Paris, the City of Light!",
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
        "voice_q": "Question 3: A red circle on a white background. Name this Asian nation!",
        "voice_a": "Boom! It's Japan, the Land of the Rising Sun!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q04",
        "question": "NAME THE COUNTRY FROM 3 CLUES!",
        "universe": "SYMBOL DECODER",
        "clues": [
            {"word": "MAPLE SYRUP", "color": (230, 126, 34)},
            {"word": "ICE HOCKEY", "color": (41, 128, 185)},
            {"word": "BEAVER", "color": (39, 174, 96)}
        ],
        "choices": [{"id": "A", "text": "Norway"}, {"id": "B", "text": "Finland"}, {"id": "C", "text": "Canada"}, {"id": "D", "text": "Sweden"}],
        "correct_id": "C",
        "answer_text": "CANADA",
        "reveal_image_path": "assets/landmarks/canada_landscape.jpg",
        "voice_q": "Question 4: Decode these three symbols! Maple syrup, ice hockey, and a beaver.",
        "voice_a": "That's Canada! Home of the great white north!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q05",
        "question": "WHICH NATION FLIES THE UNION JACK?",
        "universe": "LEVEL 1: EASY",
        "clues": [{"word": "UNION JACK", "image_path": "assets/flags/gb.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Australia"}, {"id": "B", "text": "United Kingdom"}, {"id": "C", "text": "Iceland"}, {"id": "D", "text": "Norway"}],
        "correct_id": "B",
        "answer_text": "UNITED KINGDOM (UK)",
        "voice_q": "Question 5: Which country flies the historic Union Jack flag?",
        "voice_a": "You got it! It's the United Kingdom!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q06",
        "question": "WHAT IS THE CAPITAL OF AUSTRALIA?",
        "universe": "TRICK QUESTION",
        "choices": [{"id": "A", "text": "Sydney"}, {"id": "B", "text": "Melbourne"}, {"id": "C", "text": "Canberra"}, {"id": "D", "text": "Brisbane"}],
        "correct_id": "C",
        "answer_text": "CANBERRA (NOT SYDNEY!)",
        "reveal_image_path": "assets/landmarks/canberra.jpg",
        "voice_q": "Question 6: Tricky question! Most people get this wrong: What is the capital of Australia?",
        "voice_a": "It's Canberra! Not Sydney and not Melbourne!",
        "countdown_seconds": 4.0,
    },

    # ROUND 2: LEVEL 2 MEDIUM — TRAVEL BATTLE, REBUS & TRICK FLAGS (Q7 - Q12)
    {
        "id": "q07",
        "question": "WHICH COUNTRY HAS THIS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "ORDER & PROGRESS", "image_path": "assets/flags/br.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Argentina"}, {"id": "B", "text": "Jamaica"}, {"id": "C", "text": "Brazil"}, {"id": "D", "text": "South Africa"}],
        "correct_id": "C",
        "answer_text": "BRAZIL",
        "voice_q": "Question 7: Green and yellow diamond with a starry blue globe. Level 2 begins!",
        "voice_a": "It's Brazil, the largest country in South America!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q08",
        "question": "THE ULTIMATE TRAVEL BATTLE: CHOOSE ONE!",
        "universe": "THIS OR THAT",
        "side_a": {"name": "1 WEEK IN TOKYO, JAPAN", "action": "HIT LIKE", "color": (46, 204, 113)},
        "side_b": {"name": "1 WEEK IN PARIS, FRANCE", "action": "LEAVE COMMENT", "color": (230, 126, 34)},
        "answer_text": "TOKYO (LIKE) VS PARIS (COMMENT)",
        "voice_q": "Question 8: Travel Battle! One week all-expenses-paid in Tokyo, or Paris? Hit like for Tokyo, or comment for Paris!",
        "voice_a": "Tell us your dream vacation in the comments below!",
        "countdown_seconds": 4.5,
    },
    {
        "id": "q09",
        "question": "NAME THE COUNTRY FROM 3 CLUES!",
        "universe": "SYMBOL DECODER",
        "clues": [
            {"word": "PYRAMIDS", "color": (241, 196, 15)},
            {"word": "NILE RIVER", "color": (52, 152, 219)},
            {"word": "SPHINX", "color": (230, 126, 34)}
        ],
        "choices": [{"id": "A", "text": "Sudan"}, {"id": "B", "text": "Egypt"}, {"id": "C", "text": "Greece"}, {"id": "D", "text": "Morocco"}],
        "correct_id": "B",
        "answer_text": "EGYPT",
        "reveal_image_path": "assets/landmarks/pyramids.jpg",
        "voice_q": "Question 9: Ancient symbols! Pyramids of Giza, the Nile River, and the Sphinx.",
        "voice_a": "That is Egypt, the cradle of ancient civilization!",
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
        "question": "WHAT IS THE CAPITAL OF BRAZIL?",
        "universe": "TRICK QUESTION",
        "choices": [{"id": "A", "text": "Rio de Janeiro"}, {"id": "B", "text": "Sao Paulo"}, {"id": "C", "text": "Brasilia"}, {"id": "D", "text": "Salvador"}],
        "correct_id": "C",
        "answer_text": "BRASILIA (NOT RIO!)",
        "reveal_image_path": "assets/landmarks/brasilia.jpg",
        "voice_q": "Question 11: Another classic trap! What is the official capital city of Brazil?",
        "voice_a": "It's Brasilia! Not Rio and not Sao Paulo!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q12",
        "question": "CHOOSE A LUCKY TRAVEL BOX!",
        "universe": "MYSTERY BOX",
        "boxes": [
            {"id": "A", "color_name": "Emerald", "color": (46, 204, 113), "reward": "FREE HAWAII TRIP!"},
            {"id": "B", "color_name": "Ruby", "color": (231, 76, 60), "reward": "STUCK AT AIRPORT 24H"},
            {"id": "C", "color_name": "Gold", "color": (241, 196, 15), "reward": "$10,000 TRAVEL VOUCHER!"}
        ],
        "answer_text": "BOX A: HAWAII • BOX B: AIRPORT • BOX C: $10,000",
        "voice_q": "Question 12: Mystery Box time! Pick Box A, Box B, or Box C right now!",
        "voice_a": "Did you get the Hawaii trip or the ten thousand dollars? Let us know!",
        "countdown_seconds": 4.5,
    },

    # ROUND 3: LEVEL 2/3 — ODD ONE OUT & GEOGRAPHY RIDDLES (Q13 - Q18)
    {
        "id": "q13",
        "question": "WHICH OF THESE IS LANDLOCKED (NO COASTLINE)?",
        "universe": "ODD ONE OUT",
        "choices": [{"id": "A", "text": "Germany"}, {"id": "B", "text": "Switzerland"}, {"id": "C", "text": "Spain"}, {"id": "D", "text": "Italy"}],
        "correct_id": "B",
        "answer_text": "SWITZERLAND",
        "reveal_image_path": "assets/landmarks/switzerland.jpg",
        "voice_q": "Question 13: Test your world geography! Which of these European countries has zero coastline?",
        "voice_a": "It's Switzerland, surrounded entirely by the Alps and land!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q14",
        "question": "WHICH COUNTRY HAS 4 RED STARS ON ITS FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "4 RED STARS", "image_path": "assets/flags/nz.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Australia"}, {"id": "B", "text": "New Zealand"}, {"id": "C", "text": "Fiji"}, {"id": "D", "text": "Tuvalu"}],
        "correct_id": "B",
        "answer_text": "NEW ZEALAND",
        "voice_q": "Question 14: Union Jack with four red stars outlined in white. Australia or New Zealand?",
        "voice_a": "That's New Zealand! Australia has six white stars!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q15",
        "question": "WHAT IS THE CAPITAL OF CANADA?",
        "universe": "CAPITAL CITY",
        "choices": [{"id": "A", "text": "Toronto"}, {"id": "B", "text": "Vancouver"}, {"id": "C", "text": "Montreal"}, {"id": "D", "text": "Ottawa"}],
        "correct_id": "D",
        "answer_text": "OTTAWA (NOT TORONTO!)",
        "reveal_image_path": "assets/landmarks/ottawa.jpg",
        "voice_q": "Question 15: Over eighty percent of people fail this: What is the capital city of Canada?",
        "voice_a": "It's Ottawa! Not Toronto and not Vancouver!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q16",
        "question": "NAME THE COUNTRY FROM 3 CLUES!",
        "universe": "SYMBOL DECODER",
        "clues": [
            {"word": "KANGAROO", "color": (230, 126, 34)},
            {"word": "OPERA HOUSE", "color": (52, 152, 219)},
            {"word": "BOOMERANG", "color": (46, 204, 113)}
        ],
        "choices": [{"id": "A", "text": "South Africa"}, {"id": "B", "text": "Australia"}, {"id": "C", "text": "New Zealand"}, {"id": "D", "text": "Argentina"}],
        "correct_id": "B",
        "answer_text": "AUSTRALIA",
        "reveal_image_path": "assets/landmarks/sydney.jpg",
        "voice_q": "Question 16: Three famous symbols! A kangaroo, the Sydney Opera House, and a boomerang.",
        "voice_a": "G'day mate! That is Australia!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q17",
        "question": "WHICH COUNTRY HAS NO RED COLOR ON ITS FLAG?",
        "universe": "ODD ONE OUT",
        "choices": [{"id": "A", "text": "Sweden"}, {"id": "B", "text": "United States"}, {"id": "C", "text": "Japan"}, {"id": "D", "text": "France"}],
        "correct_id": "A",
        "answer_text": "SWEDEN (BLUE & YELLOW)",
        "reveal_image_path": "assets/flags/se.png",
        "voice_q": "Question 17: Visual observation! Which of these four national flags has zero red on it?",
        "voice_a": "It's Sweden, flying blue and yellow!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q18",
        "question": "WHICH NATION FLIES THE RAINBOW FLAG?",
        "universe": "LEVEL 2: MEDIUM",
        "clues": [{"word": "RAINBOW NATION", "image_path": "assets/flags/za.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Kenya"}, {"id": "B", "text": "Nigeria"}, {"id": "C", "text": "Ghana"}, {"id": "D", "text": "South Africa"}],
        "correct_id": "D",
        "answer_text": "SOUTH AFRICA",
        "voice_q": "Question 18: Six vibrant colors forming a horizontal Y pattern. Final question of Level 2!",
        "voice_a": "It's South Africa, Nelson Mandela's homeland! Level 3 Hard begins now!",
        "countdown_seconds": 4.0,
    },

    # ROUND 4: LEVEL 3 HARD — RARE FLAGS & WORLD CURIOSITIES (Q19 - Q24)
    {
        "id": "q19",
        "question": "WHICH TERRITORY HAS THIS NORDIC CROSS?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "NORDIC CROSS", "image_path": "assets/flags/ax.png", "prompt": "NAME THIS TERRITORY"}],
        "choices": [{"id": "A", "text": "Sweden"}, {"id": "B", "text": "Finland"}, {"id": "C", "text": "Aland Islands"}, {"id": "D", "text": "Norway"}],
        "correct_id": "C",
        "answer_text": "ALAND ISLANDS",
        "voice_q": "Question 19: Level 3 Hard! A blue field with a yellow and red Nordic cross.",
        "voice_a": "That's the Aland Islands, an autonomous territory of Finland!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q20",
        "question": "WHAT IS THE CAPITAL OF SWITZERLAND?",
        "universe": "TRICK QUESTION",
        "choices": [{"id": "A", "text": "Zurich"}, {"id": "B", "text": "Geneva"}, {"id": "C", "text": "Bern"}, {"id": "D", "text": "Basel"}],
        "correct_id": "C",
        "answer_text": "BERN (DE FACTO CAPITAL)",
        "reveal_image_path": "assets/landmarks/bern.jpg",
        "voice_q": "Question 20: Beware! Zurich and Geneva are famous, but what is the official capital of Switzerland?",
        "voice_a": "It's Bern, the federal city of Switzerland!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q21",
        "question": "WHICH CARIBBEAN NATION HAS A TRIDENT FLAG?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "BLACK TRIDENT", "image_path": "assets/flags/bb.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Barbados"}, {"id": "B", "text": "Bahamas"}, {"id": "C", "text": "Saint Lucia"}, {"id": "D", "text": "Curacao"}],
        "correct_id": "A",
        "answer_text": "BARBADOS",
        "voice_q": "Question 21: Ultramarine blue and gold with a black trident head in the center.",
        "voice_a": "That's Barbados, singer Rihanna's beautiful homeland!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q22",
        "question": "WHICH COUNTRY HAS THE ONLY NON-RECTANGULAR FLAG?",
        "universe": "GEOGRAPHY RIDDLE",
        "clues": [{"word": "DOUBLE TRIANGLE", "image_path": "assets/flags/np.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Bhutan"}, {"id": "B", "text": "Vatican City"}, {"id": "C", "text": "Nepal"}, {"id": "D", "text": "Monaco"}],
        "correct_id": "C",
        "answer_text": "NEPAL (TWO TRIANGLES)",
        "voice_q": "Question 22: The only national flag in the entire world made of two stacked triangles!",
        "voice_a": "It's Nepal, home of Mount Everest and the Himalayas!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q23",
        "question": "WHICH COUNTRY FLIES THE STEPPE EAGLE?",
        "universe": "LEVEL 3: HARD",
        "clues": [{"word": "STEPPE EAGLE", "image_path": "assets/flags/kz.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Mongolia"}, {"id": "B", "text": "Kazakhstan"}, {"id": "C", "text": "Uzbekistan"}, {"id": "D", "text": "Kyrgyzstan"}],
        "correct_id": "B",
        "answer_text": "KAZAKHSTAN",
        "voice_q": "Question 23: Sky blue field with a soaring golden steppe eagle beneath thirty-two rays of sun.",
        "voice_a": "Magnificent Kazakhstan! The ninth largest country in the world!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q24",
        "question": "WHICH OF THESE IS THE SMALLEST SOVEREIGN NATION?",
        "universe": "WORLD RECORDS",
        "choices": [{"id": "A", "text": "Monaco"}, {"id": "B", "text": "Nauru"}, {"id": "C", "text": "Vatican City"}, {"id": "D", "text": "Tuvalu"}],
        "correct_id": "C",
        "answer_text": "VATICAN CITY (0.19 SQ MI)",
        "reveal_image_path": "assets/landmarks/vatican.jpg",
        "voice_q": "Question 24: World records! Which of these four sovereign nations is the smallest on Earth?",
        "voice_a": "It's Vatican City, covering less than zero point two square miles! Level 3 complete!",
        "countdown_seconds": 4.0,
    },

    # ROUND 5: LEVEL 4 GOD LEVEL — THE 1% IMPOSSIBLE SECRETS (Q25 - Q30)
    {
        "id": "q25",
        "question": "WHICH COUNTRY HAS AN AK-47 ON ITS FLAG?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "ASSAULT RIFLE", "image_path": "assets/flags/mz.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Mozambique"}, {"id": "B", "text": "Angola"}, {"id": "C", "text": "Burkina Faso"}, {"id": "D", "text": "Guinea-Bissau"}],
        "correct_id": "A",
        "answer_text": "MOZAMBIQUE",
        "voice_q": "Question 25: Level 4 Impossible! The only national flag in the world featuring a modern assault rifle.",
        "voice_a": "Incredible knowledge! That is Mozambique in Southeast Africa!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q26",
        "question": "WHAT IS THE NORTHERNMOST CAPITAL IN THE WORLD?",
        "universe": "CAPITAL CITY",
        "choices": [{"id": "A", "text": "Oslo"}, {"id": "B", "text": "Helsinki"}, {"id": "C", "text": "Stockholm"}, {"id": "D", "text": "Reykjavik"}],
        "correct_id": "D",
        "answer_text": "REYKJAVIK (ICELAND)",
        "reveal_image_path": "assets/landmarks/reykjavik.jpg",
        "voice_q": "Question 26: Geography masters only! What is the northernmost sovereign capital city on Earth?",
        "voice_a": "It's Reykjavik, the capital of Iceland, sitting at 64 degrees north!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q27",
        "question": "WHICH HIMALAYAN NATION FLIES THE THUNDER DRAGON?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "THUNDER DRAGON", "image_path": "assets/flags/bt.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Wales"}, {"id": "B", "text": "Bhutan"}, {"id": "C", "text": "Sri Lanka"}, {"id": "D", "text": "Cambodia"}],
        "correct_id": "B",
        "answer_text": "BHUTAN",
        "voice_q": "Question 27: Yellow and orange diagonal split with Druk the Thunder Dragon holding jewels.",
        "voice_a": "That is the mystical kingdom of Bhutan, home of Gross National Happiness!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q28",
        "question": "WHICH FLAG FEATURES THE RARE COLOR PURPLE?",
        "universe": "FLAG CURIOSITY",
        "clues": [{"word": "SISSEROU PARROT", "image_path": "assets/flags/dm.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Dominica"}, {"id": "B", "text": "Fiji"}, {"id": "C", "text": "Palau"}, {"id": "D", "text": "Tuvalu"}],
        "correct_id": "A",
        "answer_text": "DOMINICA (PURPLE PARROT)",
        "voice_q": "Question 28: Look closely at the parrot! Which country features the rarest color in vexillology, purple?",
        "voice_a": "That is Dominica in the Caribbean, not Dominican Republic!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q29",
        "question": "WHICH COUNTRY HAS THREE MOUNTAIN TOWERS?",
        "universe": "LEVEL 4: GOD",
        "clues": [{"word": "THREE TOWERS", "image_path": "assets/flags/sm.png", "prompt": "NAME THIS COUNTRY"}],
        "choices": [{"id": "A", "text": "Andorra"}, {"id": "B", "text": "Liechtenstein"}, {"id": "C", "text": "San Marino"}, {"id": "D", "text": "Monaco"}],
        "correct_id": "C",
        "answer_text": "SAN MARINO",
        "voice_q": "Question 29: White and light blue featuring three fortified castle towers on Monte Titano.",
        "voice_a": "Spot on! That is the ancient republic of San Marino, dating back to 301 AD!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q30",
        "question": "FINAL BOSS: NAME THIS PACIFIC ISLAND NATION!",
        "universe": "FINAL BOSS",
        "clues": [{"word": "12-POINT STAR", "image_path": "assets/flags/nr.png", "prompt": "NAME THIS PACIFIC NATION"}],
        "choices": [{"id": "A", "text": "Kiribati"}, {"id": "B", "text": "Tuvalu"}, {"id": "C", "text": "Marshall Islands"}, {"id": "D", "text": "Nauru"}],
        "correct_id": "D",
        "answer_text": "NAURU",
        "voice_q": "Question 30, THE FINAL BOSS! Blue field, gold equator line, and a twelve-pointed star. Name this tiny Pacific island nation!",
        "voice_a": "It's Nauru, the smallest island nation in the world! DID YOU SCORE THIRTY OUT OF THIRTY?!",
        "countdown_seconds": 4.5,
    },
]

# -------------------------------------------------------------
# EXECUTION WORKFLOW
# -------------------------------------------------------------

def main():
    print("=" * 70)
    print("  PRODUCING 30-QUESTION US MULTI-MODE DYNAMIC QUIZ (5.5 MINUTES)")
    print("=" * 70)

    out_dir = Path("output/us_multimode_quiz_5min")
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / "us_multimode_world_quiz_16_9.mp4"

    bgm_file = Path("assets/bgm/bgm_cyber_trap.wav")

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
        bgm_path=bgm_file,
    )

    engine = QuizVideoEngineV2(opt)

    print(f"\n[1/2] Compiling 30-Question Multi-Mode Quiz with Cyber Trap BGM: {mp4_path.name}")
    t0 = time.time()
    rendered_mp4 = engine.render_quiz_video(
        US_MULTIMODE_QUIZ_30,
        title="THE ULTIMATE WORLD GEOGRAPHY CHALLENGE"
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

    # Extract verification frames across all rotating modes
    prev_dir = out_dir / "previews"
    prev_dir.mkdir(parents=True, exist_ok=True)
    frames_to_extract = [
        ("mode1_flag_usa.jpg", 16.0),
        ("mode2_capital_paris.jpg", 28.0),
        ("mode3_symbol_canada.jpg", 52.0),
        ("mode4_travel_battle.jpg", 102.0),
        ("mode5_mystery_box.jpg", 152.0),
        ("mode6_odd_one_out.jpg", 165.0),
        ("mode7_final_boss_nauru.jpg", 335.0),
        ("mode8_final_scoreboard.jpg", dur - 2.0),
    ]
    for fname, t_sec in frames_to_extract:
        p = prev_dir / fname
        subprocess.run(["ffmpeg", "-y", "-ss", str(t_sec), "-i", str(rendered_mp4), "-vframes", "1", "-q:v", "2", str(p)], capture_output=True)
        print(f"   Saved preview: {fname} (t={t_sec}s): {p.exists()}")

    print("\n✅ MULTI-MODE DYNAMIC US QUIZ VIDEO COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
