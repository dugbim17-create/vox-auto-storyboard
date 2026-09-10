import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import _discover_cliproxy_api_key
from app.providers.base import ImageGenerationRequest
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2

OUTPUT_DIR = ROOT / "output" / "boss_acceptance_10q"
IMAGES_DIR = OUTPUT_DIR / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_PROMPTS = {
    "jupiter.png": "Cinematic breathtaking ultra-realistic 8k space photography of planet Jupiter, Great Red Spot swirling violently, vibrant atmospheric cloud bands in amber and cream, surrounded by deep black starry space, dramatic cinematic side lighting, unreal engine 5 render style",
    "saturn.png": "Majestic photorealistic 8k cosmic image of planet Saturn with glorious wide glowing rings tilted towards the sun, golden gas clouds, deep space nebula background, photorealistic astrophysics illustration",
    "gas_giant.png": "Epic cinematic illustration of massive gas giant planet with glowing aurora borealis at the poles, swirling storm vortex, deep space with distant galaxy spiral",
    "james_webb.png": "Ultra-detailed futuristic deep space telescope with golden hexagonal mirrors unfolding in outer space, reflecting colorful distant stars and cosmic nebulae, photorealistic NASA style",
    "proxima.png": "Vivid cinematic space scene of a fiery red dwarf star radiating intense solar flares into the void of space, an orbiting rocky exoplanet in the foreground, epic sci-fi astronomy",
    "black_hole.png": "Mind-bending 8k cinematic visualization of an active supermassive black hole with glowing fiery accretion disk, gravitational lensing distorting starlight, relativistic jets of plasma firing into space, Interstellar movie aesthetic",
}

async def generate_all_images():
    print("[IMAGE_GEN] Initializing CLIProxy Image Provider (gpt-image-2)...")
    api_key = _discover_cliproxy_api_key()
    provider = CliproxyImageProvider(
        base_url="http://127.0.0.1:8317/v1",
        api_key=api_key,
        model="gpt-image-2",
    )
    for filename, prompt in IMAGE_PROMPTS.items():
        out_file = IMAGES_DIR / filename
        if out_file.is_file() and out_file.stat().st_size > 50000:
            print(f"[IMAGE_GEN] Reusing existing image: {filename}")
            continue
        print(f"[IMAGE_GEN] Generating fresh AI image for {filename}...")
        t0 = time.time()
        req = ImageGenerationRequest(
            role="composite",
            prompt=prompt,
            output_path=str(out_file),
        )
        res = await provider.generate(req)
        print(f"[IMAGE_GEN] -> Done in {time.time()-t0:.2f}s: {filename} ({res.width}x{res.height})")
        # Validate Pillow open
        with Image.open(out_file) as im:
            assert im.size[0] > 0 and im.size[1] > 0

def build_10_questions():
    return [
        {
            "id": "q01",
            "question": "HÀNH TINH NÀO LỚN NHẤT HỆ MẶT TRỜI?",
            "universe": "HÀNH TINH KHỔNG LỒ",
            "choices": [
                {"id": "A", "text": "Sao Thổ"},
                {"id": "B", "text": "Sao Mộc"},
                {"id": "C", "text": "Sao Hải Vương"},
                {"id": "D", "text": "Sao Thiên Vương"},
            ],
            "correct_id": "B",
            "answer_text": "SAO MỘC (JUPITER)",
            "reveal_image_path": str(IMAGES_DIR / "jupiter.png"),
            "voice_q": "Câu hỏi số 1: Hành tinh nào có kích thước khổng lồ lớn nhất trong toàn bộ Hệ Mặt Trời?",
            "voice_a": "Chính xác! Đó chính là Sao Mộc, hành tinh khí khổng lồ với cơn bão Đốm Đỏ vĩ đại!",
            "countdown_seconds": 4.0,
        },
        {
            "id": "q02",
            "question": "ĐOÁN TÊN THIÊN THỂ BÍ ẨN NÀY?",
            "universe": "WORD TILES",
            "word_tiles": [
                [("H", True), ("Ố", False)],
                [("Đ", True), ("E", False), ("N", True)],
            ],
            "answer_text": "HỐ ĐEN (BLACK HOLE)",
            "voice_q": "Câu đố chữ: Thiên thể nào có lực hấp dẫn cực lớn khiến ánh sáng cũng không thể thoát ra?",
            "voice_a": "Chuẩn luôn! Đó chính là Hố Đen vũ trụ kỳ bí!",
            "countdown_seconds": 4.0,
        },
        {
            "id": "q03",
            "question": "ĐỊNH CƯ NGOÀI KHÔNG GIAN: CHỌN ĐÍCH ĐẾN!",
            "universe": "THIS OR THAT",
            "side_a": {
                "name": "TRẠM MẶT TRĂNG",
                "action": "BẤM LIKE",
                "color": (46, 204, 113),
            },
            "side_b": {
                "name": "THUỘC ĐỊA SAO HỎA",
                "action": "BÌNH LUẬN",
                "color": (230, 126, 34),
            },
            "answer_text": "MẶT TRĂNG (LIKE) VS SAO HỎA (COMMENT)",
            "voice_q": "Đại chiến du hành: Nếu được chọn định cư ngoài không gian, bạn chọn Trạm Mặt Trăng hay Sao Hỏa? Bấm like cho Mặt Trăng hoặc bình luận cho Sao Hỏa!",
            "voice_a": "Hãy để lại ý kiến của bạn xem Mặt Trăng hay Sao Hỏa sẽ là ngôi nhà mới của loài người!",
            "countdown_seconds": 4.5,
        },
        {
            "id": "q04",
            "question": "GIẢI MÃ THIÊN THỂ TỪ 3 MANH MỐI!",
            "universe": "SYMBOL DECODER",
            "clues": [
                {"word": "VÀNH ĐAI KHỔNG LỒ", "color": (230, 126, 34)},
                {"word": "HÀNH TINH KHÍ", "color": (41, 128, 185)},
                {"word": "MÀU VÀNG CAM", "color": (39, 174, 96)},
            ],
            "choices": [
                {"id": "A", "text": "Sao Hỏa"},
                {"id": "B", "text": "Sao Thổ"},
                {"id": "C", "text": "Sao Kim"},
                {"id": "D", "text": "Sao Thủy"},
            ],
            "correct_id": "B",
            "answer_text": "SAO THỔ (SATURN)",
            "reveal_image_path": str(IMAGES_DIR / "saturn.png"),
            "voice_q": "Câu hỏi số 4: Giải mã ba manh mối: Vành đai khổng lồ, hành tinh khí và màu vàng cam. Đây là thiên thể nào?",
            "voice_a": "Hoàn toàn chính xác! Đó là Sao Thổ, viên ngọc quý tuyệt đẹp của Hệ Mặt Trời!",
            "countdown_seconds": 4.0,
        },
        {
            "id": "q05",
            "question": "HỘP VŨ TRỤ MAY MẮN: CHỌN MỘT HỘP!",
            "universe": "MYSTERY BOX",
            "boxes": [
                {"id": "A", "color_name": "Emerald", "color": (46, 204, 113), "reward": "THIÊN THẠCH KIM CƯƠNG"},
                {"id": "B", "color_name": "Ruby", "color": (231, 76, 60), "reward": "BÃO MẶT TRỜI QUÉT QUA"},
                {"id": "C", "color_name": "Gold", "color": (241, 196, 15), "reward": "TÀU VŨ TRỤ SIÊU TỐC"},
            ],
            "answer_text": "HỘP A: KIM CƯƠNG • HỘP B: BÃO TỪ • HỘP C: TÀU VŨ TRỤ",
            "voice_q": "Câu số 5: Thử vận may vũ trụ! Hãy chọn thật nhanh Hộp A, Hộp B hay Hộp C!",
            "voice_a": "Bạn đã chọn trúng thiên thạch kim cương hay nhận được phi thuyền siêu tốc? Hãy khoe ngay nhé!",
            "countdown_seconds": 4.5,
        },
        {
            "id": "q06",
            "question": "ĐỐI TƯỢNG NÀO KHÁC BIỆT NHẤT?",
            "universe": "ODD ONE OUT",
            "choices": [
                {"id": "A", "text": "Sao Thủy"},
                {"id": "B", "text": "Sao Kim"},
                {"id": "C", "text": "Trái Đất"},
                {"id": "D", "text": "Sao Mộc"},
            ],
            "correct_id": "D",
            "answer_text": "SAO MỘC (LÀ HÀNH TINH KHÍ, CÒN LẠI ĐẤT ĐÁ)",
            "reveal_image_path": str(IMAGES_DIR / "gas_giant.png"),
            "voice_q": "Câu hỏi số 6: Trong 4 hành tinh sau, hành tinh nào KHÔNG PHẢI là hành tinh đất đá?",
            "voice_a": "Chính là Sao Mộc! Sao Mộc là hành tinh khí khổng lồ, trong khi 3 hành tinh còn lại đều có bề mặt đất đá!",
            "countdown_seconds": 4.0,
        },
        {
            "id": "q07",
            "question": "KÍNH THIÊN VĂN HIỆN ĐẠI NHẤT HIỆN NAY?",
            "universe": "CÔNG NGHỆ VŨ TRỤ",
            "choices": [
                {"id": "A", "text": "Hubble"},
                {"id": "B", "text": "James Webb"},
                {"id": "C", "text": "Kepler"},
                {"id": "D", "text": "Spitzer"},
            ],
            "correct_id": "B",
            "answer_text": "JAMES WEBB SPACE TELESCOPE",
            "reveal_image_path": str(IMAGES_DIR / "james_webb.png"),
            "voice_q": "Câu hỏi số 7: Kính viễn vọng không gian hiện đại bậc nhất của nhân loại với gương tổ ong mạ vàng có tên là gì?",
            "voice_a": "Chính xác! Đó là kính thiên văn không gian James Webb, cánh mắt thần nhìn vào bình minh của vũ trụ!",
            "countdown_seconds": 4.0,
        },
        {
            "id": "q08",
            "question": "CÔNG NGHỆ TƯƠNG LAI BẠN MUỐN CÓ NHẤT?",
            "universe": "THIS OR THAT",
            "side_a": {
                "name": "CỔNG DỊCH CHUYỂN",
                "action": "BẤM LIKE",
                "color": (52, 152, 219),
            },
            "side_b": {
                "name": "DU HÀNH THỜI GIAN",
                "action": "BÌNH LUẬN",
                "color": (155, 89, 182),
            },
            "answer_text": "DỊCH CHUYỂN (LIKE) VS THỜI GIAN (COMMENT)",
            "voice_q": "Đại chiến công nghệ: Bạn muốn sở hữu Cổng dịch chuyển tức thời hay Cỗ máy du hành thời gian? Bấm like cho dịch chuyển hoặc bình luận cho du hành thời gian!",
            "voice_a": "Thật khó lựa chọn phải không nào! Hãy cho mọi người biết lý do lựa chọn của bạn nhé!",
            "countdown_seconds": 4.5,
        },
        {
            "id": "q09",
            "question": "NGÔI SAO GẦN TRÁI ĐẤT NHẤT SAU MẶT TRỜI?",
            "universe": "KHOẢNG CÁCH THIÊN HÀ",
            "choices": [
                {"id": "A", "text": "Sirius"},
                {"id": "B", "text": "Betelgeuse"},
                {"id": "C", "text": "Proxima Centauri"},
                {"id": "D", "text": "Vega"},
            ],
            "correct_id": "C",
            "answer_text": "PROXIMA CENTAURI (4.2 NĂM ÁNH SÁNG)",
            "reveal_image_path": str(IMAGES_DIR / "proxima.png"),
            "voice_q": "Câu hỏi số 9: Ngoại trừ Mặt Trời, ngôi sao nào ở cự ly gần Trái Đất nhất trong dải ngân hà?",
            "voice_a": "Đúng rồi! Đó là ngôi sao lùn đỏ Proxima Centauri, cách chúng ta khoảng 4,2 năm ánh sáng!",
            "countdown_seconds": 4.0,
        },
        {
            "id": "q10",
            "question": "FINAL BOSS: VẬT THỂ Ở TRUNG TÂM NGÂN HÀ?",
            "universe": "FINAL BOSS",
            "choices": [
                {"id": "A", "text": "Sao Nơ-tron cực mạnh"},
                {"id": "B", "text": "Hố đen siêu khối Sagittarius A*"},
                {"id": "C", "text": "Đám mây khí Tinh Vân"},
                {"id": "D", "text": "Cụm sao hình cầu cổ đại"},
            ],
            "correct_id": "B",
            "answer_text": "HỐ ĐEN SIÊU KHỐI SAGITTARIUS A*",
            "reveal_image_path": str(IMAGES_DIR / "black_hole.png"),
            "voice_q": "Câu hỏi Trùm Cuối: Vật thể khổng lồ thống trị ngay tại trung tâm Dải Ngân Hà của chúng ta là gì?",
            "voice_a": "Xuất sắc! Đó chính là Sagittarius A*, một Hố Đen Siêu Khối với khối lượng gấp 4 triệu lần Mặt Trời!",
            "countdown_seconds": 5.0,
        },
    ]

def render_video():
    questions = build_10_questions()
    (OUTPUT_DIR / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    
    target_mp4 = OUTPUT_DIR / "quiz_space_odyssey_10modes.mp4"
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

    print(f"[RENDER] Starting 10-Question Master Video Render: {target_mp4}...")
    engine = QuizVideoEngineV2(options)
    t0 = time.perf_counter()
    actual_mp4 = engine.render_quiz_video(questions, title="BÍ ẨN VŨ TRỤ & KHÔNG GIAN TƯƠNG LAI")
    elapsed = time.perf_counter() - t0
    print(f"[RENDER] Video completed in {elapsed:.2f}s -> {actual_mp4}")

    # FFmpeg decode verification
    print("[VERIFY] Running FFmpeg decode integrity test...")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(actual_mp4), "-f", "null", "-"], check=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(actual_mp4)
    ]))
    duration = float(probe["format"]["duration"])
    size_mb = actual_mp4.stat().st_size / (1024 * 1024)
    print(f"[VERIFY] Duration: {duration:.2f}s, Size: {size_mb:.2f} MB, Resolution: 1920x1080 @ 30fps")

    # Extract 5 sample keyframes for different modes
    keyframes = [
        (10, "frame_q1_photo_reveal.png"),
        (25, "frame_q2_word_tiles.png"),
        (40, "frame_q3_this_or_that.png"),
        (65, "frame_q5_mystery_box.png"),
        (130, "frame_q10_final_boss.png"),
    ]
    for ss, fname in keyframes:
        frame_out = OUTPUT_DIR / fname
        subprocess.run([
            "ffmpeg", "-v", "error", "-ss", str(min(ss, int(duration - 2))),
            "-i", str(actual_mp4), "-frames:v", "1", "-y", str(frame_out)
        ], check=True)
        print(f"[VERIFY] Keyframe saved: {fname}")

    manifest = {
        "title": "Bí Ẩn Vũ Trụ & Không Gian Tương Lai (10 Modes)",
        "mp4_path": str(actual_mp4.resolve()),
        "duration_seconds": duration,
        "size_mb": round(size_mb, 2),
        "questions_count": len(questions),
        "modes_included": [
            "Photo Reveal", "Word Tiles", "This or That", "Symbol Decoder",
            "Mystery Box", "Odd One Out", "Future Tech Battle", "Final Boss Challenge"
        ],
        "voice": "Piper (minh_khang - Vietnamese)",
        "decode_pass": True,
    }
    (OUTPUT_DIR / "verification.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[ALL DONE] Master 10-Question Video Ready!")

if __name__ == "__main__":
    asyncio.run(generate_all_images())
    render_video()
