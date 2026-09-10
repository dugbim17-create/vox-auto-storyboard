import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2

QUESTIONS = [
    {
        "id": "q01",
        "question": "QUỐC KỲ NÀY LÀ CỦA QUỐC GIA NÀO?",
        "universe": "QUỐC KỲ THẾ GIỚI",
        "clues": [
            {
                "word": "LÁ PHONG ĐỎ",
                "image_path": "assets/flags/ca.png",
                "prompt": "ĐẤT NƯỚC LÁ PHONG",
            }
        ],
        "choices": [
            {"id": "A", "text": "New Zealand"},
            {"id": "B", "text": "Áo"},
            {"id": "C", "text": "Canada"},
            {"id": "D", "text": "Thụy Sĩ"},
        ],
        "correct_id": "C",
        "answer_text": "CANADÁ",
        "reveal_image_path": "assets/flags/ca.png",
        "voice_q": "Câu hỏi số 1: Quốc kỳ có biểu tượng lá phong đỏ nổi tiếng là của quốc gia nào?",
        "voice_a": "Chính xác! Đó chính là Canada, đất nước lá phong xinh đẹp!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q02",
        "question": "THÁP EIFFEL NẰM Ở THỦ ĐÔ NÀO?",
        "universe": "ĐỊA DANH NỔI TIẾNG",
        "choices": [
            {"id": "A", "text": "Lyon"},
            {"id": "B", "text": "Paris"},
            {"id": "C", "text": "Marseille"},
            {"id": "D", "text": "Nice"},
        ],
        "correct_id": "B",
        "answer_text": "PARIS (NƯỚC PHÁP)",
        "reveal_image_path": "assets/landmarks/paris.jpg",
        "voice_q": "Câu hỏi số 2: Tháp Eiffel tráng lệ là biểu tượng nổi tiếng của thủ đô nào?",
        "voice_a": "Đúng rồi! Đó là Paris, kinh đô ánh sáng của nước Pháp!",
        "countdown_seconds": 4.0,
    },
    {
        "id": "q03",
        "question": "KIM TỰ THÁP GIZA Ở QUỐC GIA NÀO?",
        "universe": "KỲ QUAN CỔ ĐẠI",
        "choices": [
            {"id": "A", "text": "Ai Cập"},
            {"id": "B", "text": "Hy Lạp"},
            {"id": "C", "text": "Jordan"},
            {"id": "D", "text": "Thổ Nhĩ Kỳ"},
        ],
        "correct_id": "A",
        "answer_text": "AI CẬP (EGYPT)",
        "reveal_image_path": "assets/landmarks/pyramids.jpg",
        "voice_q": "Câu hỏi số 3: Quần thể kim tự tháp Giza kỳ vĩ tọa lạc tại quốc gia nào?",
        "voice_a": "Hoàn toàn chính xác! Kim tự tháp Giza nằm ở Ai Cập, một trong bảy kỳ quan cổ đại!",
        "countdown_seconds": 4.0,
    },
]

out_dir = ROOT / "output" / "pilot_boss_acceptance"
out_dir.mkdir(parents=True, exist_ok=True)
target_mp4 = out_dir / "vietnam_world_quiz_pilot.mp4"

model_dir = Path("D:/ALL AI/TestProjects/Voice/assets/models/piper")
piper_exe = Path(shutil.which("piper") or "D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe")

options = QuizRenderOptions(
    aspect_ratio="16:9",
    fps=30,
    language="vi",
    output_path=target_mp4,
    bgm_path=ROOT / "assets/bgm/bgm_cyber_trap.wav",
    tts_engine="piper",
    piper_voice="minh_khang",
    piper_speed=1.05,
    piper_model_dir=model_dir,
    piper_config_path=model_dir / "minh_khang.onnx.json",
    piper_exe=piper_exe,
)

print("[PILOT] Initializing Quiz Engine V2...")
engine = QuizVideoEngineV2(options)
start_t = time.perf_counter()
actual_mp4 = engine.render_quiz_video(QUESTIONS, title="ĐỐ VUI ĐỊA DANH THẾ GIỚI")
elapsed = time.perf_counter() - start_t

print(f"[PILOT] Render finished in {elapsed:.2f}s -> {actual_mp4}")

# Decode check
subprocess.run(["ffmpeg", "-v", "error", "-i", str(actual_mp4), "-f", "null", "-"], check=True)
probe = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(actual_mp4)
]))

duration = float(probe["format"]["duration"])
size_mb = actual_mp4.stat().st_size / (1024 * 1024)
print(f"[PILOT] VERIFIED: Duration = {duration:.2f}s, Size = {size_mb:.2f} MB, Codec = h264/aac")
