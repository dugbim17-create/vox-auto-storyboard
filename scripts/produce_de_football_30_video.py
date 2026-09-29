"""
Produce full 30-question German Football master video with German Thorsten TTS,
Flow Music stadium BGM, and native multi-mode visual cards.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2

DATASET_PATH = ROOT / "output" / "quiz" / "de_fussball_30_v2.json"
OUTPUT_DIR = ROOT / "output" / "de_fussball_30_v2"
CARDS_DIR = OUTPUT_DIR / "cards"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CARDS_DIR.mkdir(parents=True, exist_ok=True)

PHOTO_MAP = {
    1: "q01_ronaldo",
    2: "q02_messi",
    3: "q03_mbappe",
    4: "q04_haaland",
    6: "q06_neymar",
    8: "q08_neuer",
    11: "q11_kimmich",
    15: "q15_gnabry",
}

def prepare_football_questions() -> list[dict]:
    raw_data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    raw_questions = raw_data["questions"]
    intermission = raw_data.get("intermission")
    
    prepared = []
    
    for q in raw_questions:
        qid = q["id"]
        unit = dict(q)
        unit["universe"] = q.get("level", "DEUTSCHER FUSSBALL")
        
        # 1. Photo Reveal Mode
        if qid in PHOTO_MAP:
            card_key = PHOTO_MAP[qid]
            clue_card = CARDS_DIR / f"{card_key}_card_clue.png"
            rev_card = CARDS_DIR / f"{card_key}_reveal.png"
            if clue_card.is_file():
                unit["clues"] = [{"image_path": str(clue_card), "prompt": "WER IST DIESER SPIELER?"}]
            if rev_card.is_file():
                unit["reveal_image_path"] = str(rev_card)
        
        # 2. Career Path Mode
        elif "career_steps" in q:
            unit["career_steps"] = q["career_steps"]
            unit["universe"] = "CAREER PATH · TRANSFER-STATIONEN"
            
        # 3. Symbol Decoder Mode
        elif "clues" in q:
            unit["clues"] = q["clues"]
            unit["universe"] = "3 HINWEISE · SPIELER RATEN"
            
        # 4. Word Tiles Mode
        elif "word_tiles" in q:
            unit["word_tiles"] = q["word_tiles"]
            unit["universe"] = "BUCHSTABEN-RÄTSEL"
            
        prepared.append(unit)
        
        # Insert Intermission after Question 15
        if qid == 15 and intermission:
            fan_duell_unit = {
                "id": 155,  # intermediary id
                "universe": "HALBZEIT FAN-DUELL ⚔️",
                "question": intermission.get("question", "WIRTZ ODER MUSIALA?"),
                "side_a": intermission["side_a"],
                "side_b": intermission["side_b"],
                "voice_q": intermission["voice_q"],
                "voice_a": intermission["voice_a"],
                "countdown_seconds": float(intermission.get("countdown_seconds", 8.0)),
            }
            prepared.append(fan_duell_unit)
            
    # Set German Intro and Outro text
    prepared[0]["intro_text"] = (
        "Willkommen zum großen deutschen Fußball-Quiz! "
        "Erkennst du alle 30 Fußballstars? Los geht's mit Frage eins!"
    )
    prepared[-1]["outro_text"] = (
        "Das war's! Wie viele Punkte hast du erreicht? "
        "Schreib dein Ergebnis in die Kommentare und abonniere den Kanal für mehr Fußball-Quizze!"
    )
    
    return prepared

def main():
    print("==================================================================")
    print("  🏆 STARTE GERMAN FOOTBALL 30-QUESTION MASTER VIDEO RENDER")
    print("==================================================================")
    
    # Ensure player card assets exist
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_football_cards.py")], check=True)
    
    questions = prepare_football_questions()
    print(f"✓ Prepared {len(questions)} question units (including Halftime Fan-Duell)!")
    
    (OUTPUT_DIR / "prepared_units.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    
    target_mp4 = OUTPUT_DIR / "de_fussball_30_v2.mp4"
    bgm_file = ROOT / "assets" / "bgm" / "bgm_bundesliga_stadium_hype.wav"
    assert bgm_file.is_file(), f"Missing BGM file: {bgm_file}"
    
    piper_dir = ROOT / "assets" / "models" / "piper" / "de-DE"
    piper_model = piper_dir / "de_DE-thorsten-high.onnx"
    piper_config = piper_dir / "de_DE-thorsten-high.onnx.json"
    assert piper_model.is_file(), f"Missing Piper German model: {piper_model}"
    
    piper_exe = shutil.which("piper") or "D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe"
    
    options = QuizRenderOptions(
        aspect_ratio="16:9",
        fps=30,
        language="de",
        output_path=target_mp4,
        bgm_path=bgm_file,
        tts_engine="piper",
        piper_voice="de_DE-thorsten-high",
        piper_speed=1.05,
        piper_model_dir=piper_dir,
        piper_config_path=piper_config,
        piper_exe=Path(piper_exe),
    )
    
    print(f"🎬 Initializing QuizVideoEngineV2 with Stadium BGM: {bgm_file.name}...")
    engine = QuizVideoEngineV2(options)
    
    t0 = time.perf_counter()
    print(f"⚡ Rendering 30-question video to {target_mp4}...")
    actual_mp4 = engine.render_quiz_video(questions, title="DAS GROSSE DEUTSCHE FUSSBALL-QUIZ")
    render_time = time.perf_counter() - t0
    print(f"✓ Render completed in {render_time:.1f}s ({render_time/60:.2f}m) -> {actual_mp4}")
    
    # Decode and verify integrity with FFprobe
    print("🔍 Verifying MP4 decode integrity with FFprobe...")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(actual_mp4), "-f", "null", "-"], check=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(actual_mp4)
    ]))
    duration = float(probe["format"]["duration"])
    size_mb = actual_mp4.stat().st_size / (1024 * 1024)
    
    print(f"✅ VERIFIED: Duration = {duration:.2f}s ({duration/60:.2f}m), Size = {size_mb:.2f} MB")
    
    # Save verification report
    report = {
        "title": "Erkennst du diese 30 Fußballspieler? (German Football Quiz V2)",
        "mp4_path": str(actual_mp4.resolve()),
        "duration_seconds": duration,
        "duration_minutes": round(duration / 60, 2),
        "size_mb": round(size_mb, 2),
        "resolution": "1920x1080",
        "fps": 30,
        "total_units": len(questions),
        "voice": "Piper de_DE-thorsten-high",
        "bgm": "Flow Music Stadium Hype (bgm_bundesliga_stadium_hype.wav)",
        "render_time_seconds": round(render_time, 2),
        "decode_pass": True,
    }
    (OUTPUT_DIR / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Verification manifest written to {OUTPUT_DIR / 'verification.json'}")

if __name__ == "__main__":
    main()
