"""True Vox Masterpiece Video Generator using Pure AI-Generated Tactile Torn-Paper Collages.

Showcases the breakthrough workflow discovered:
- Generating 100% authentic tactile torn-paper collage, scotch tape, pushpins, red strings,
  and yellow highlighters directly via CLIProxy gpt-image-1.5.
- Applying 3D cinematic camera drifts, film grain, and studio-grade Foley audio.
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
import time
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from piper.voice import PiperVoice

from app.services.final_composer import FinalComposer
from app.services.paper_craft import PaperCraftService
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("torn_paper_masterpiece")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_torn_paper_ai_demo")
IMAGES_DIR = PROJECT_DIR / "ai_images"
PIPER_MODEL = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx")
PIPER_CONFIG = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx.json")

WIDTH = 1920
HEIGHT = 1080
FPS = 30


@lru_cache(maxsize=32)
def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for c in candidates:
        if Path(c).is_file():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def render_tactile_camera_shot(
    img_path: str,
    frame_idx: int,
    total_frames: int,
    zoom_start: float = 1.0,
    zoom_end: float = 1.08,
    pan_x_max: int = 40,
    pan_y_max: int = -20,
    hud_tag: str = "HỒ SƠ ĐIỀU TRA",
) -> Image.Image:
    """Render a dynamic cinematic 3D camera move on a high-res AI torn-paper collage."""
    t = frame_idx / float(max(1, total_frames))
    im = Image.open(img_path).convert("RGB")

    # Current smooth zoom
    cur_zoom = zoom_start + (zoom_end - zoom_start) * (1.0 - math.pow(1.0 - t, 2.5))
    target_w = int(WIDTH * cur_zoom)
    target_h = int(HEIGHT * cur_zoom)

    # Resize with high-quality bicubic
    im_scaled = im.resize((target_w, target_h), Image.Resampling.BICUBIC)

    # Smooth pan offsets
    cur_pan_x = int(pan_x_max * math.sin(t * math.pi * 0.8))
    cur_pan_y = int(pan_y_max * t)

    crop_x0 = max(0, min(im_scaled.width - WIDTH, (target_w - WIDTH) // 2 + cur_pan_x))
    crop_y0 = max(0, min(im_scaled.height - HEIGHT, (target_h - HEIGHT) // 2 + cur_pan_y))

    frame = im_scaled.crop((crop_x0, crop_y0, crop_x0 + WIDTH, crop_y0 + HEIGHT)).convert("RGBA")

    # Film grain overlay
    grain = PaperCraftService.generate_film_grain_texture(WIDTH, HEIGHT, intensity=0.03)
    frame = Image.alpha_composite(frame, grain)

    # Subtle cinematic HUD watermark
    draw = ImageDraw.Draw(frame)
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
    c_len = 20
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 200), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 200), width=3)

    font_tag = get_font(15, bold=True)
    draw.text((70, 52), f"VOX INVESTIGATIVE DOSSIER // {hud_tag.upper()}", font=font_tag, fill=(255, 220, 20, 230))
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 280, 52), f"TƯ LIỆU // F:{frame_idx:04d}", font=font_mono, fill=(255, 255, 255, 80))

    return frame


SCENES_METADATA = [
    {
        "id": "scene_001_suspect",
        "image": "torn_suspect_corkboard.png",
        "narration": "Một mạng lưới ngầm tinh vi với những cuộc gặp bí mật lúc nửa đêm giữa các nhân vật tài phiệt quyền lực.",
        "hud_tag": "BẢNG ĐIỀU TRA // ĐỐI TƯỢNG X",
        "sfx": "pushpin_hit",
        "zoom_start": 1.0,
        "zoom_end": 1.07,
        "pan_x": 30,
        "pan_y": -15,
    },
    {
        "id": "scene_002_evidence",
        "image": "torn_flight_logs_evidence.png",
        "narration": "Nhật ký hành trình cùng dòng tiền hàng triệu đô la tại các thiên đường thuế đã trở thành bằng chứng không thể chối cãi.",
        "hud_tag": "BẰNG CHỨNG TÀI CHÍNH // LOGS",
        "sfx": "paper_slide",
        "zoom_start": 1.06,
        "zoom_end": 1.0,
        "pan_x": -35,
        "pan_y": 20,
    },
    {
        "id": "scene_003_exposed",
        "image": "torn_courtroom_exposed.png",
        "narration": "Trước phiên điều trần công khai chấn động, toàn bộ bức màn bí mật đã bị vạch trần ra ánh sáng của công lý.",
        "hud_tag": "ĐẠI ÁN PHƠI BÀY // EXPOSED",
        "sfx": "camera_click",
        "zoom_start": 1.0,
        "zoom_end": 1.08,
        "pan_x": 0,
        "pan_y": -25,
    },
]


def main() -> None:
    logger.info("=== Starting AI-Generated Torn Paper Masterpiece Video Render ===")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = PROJECT_DIR / "scenes"
    audio_dir = PROJECT_DIR / "audio"
    final_dir = PROJECT_DIR / "final"
    for d in (scenes_dir, audio_dir, final_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Load Piper Voice
    logger.info("1. Loading Piper TTS ('Ngọc Huyền')...")
    voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))

    scene_mp4s: list[Path] = []
    durations_ms: list[int] = []
    subtitle_entries: list[SubtitleEntry] = []
    current_time_ms = 0
    sfx_service = AutoSFXService()

    for idx, scene in enumerate(SCENES_METADATA):
        scene_id = scene["id"]
        narration = scene["narration"]
        img_path = str(IMAGES_DIR / scene["image"])
        logger.info(f"--- Rendering Pure AI Torn-Paper Scene: {scene_id} [{idx + 1}/3] ---")

        # Synthesize Voice
        voice_wav = audio_dir / f"{scene_id}_voice.wav"
        if not voice_wav.is_file():
            with wave.open(str(voice_wav), "wb") as wf:
                voice.synthesize_wav(narration, wf)

        with wave.open(str(voice_wav), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_ms = max(5500, int((frames / float(rate)) * 1000) + 600)

        durations_ms.append(duration_ms)
        total_frames = int(round(duration_ms / 1000.0 * FPS))

        subtitle_entries.append(
            SubtitleEntry(
                index=idx + 1,
                start_ms=current_time_ms + 100,
                end_ms=current_time_ms + duration_ms - 150,
                text=narration,
            )
        )
        current_time_ms += duration_ms

        # SFX Track
        sfx_events = [
            SFXEvent(sfx_type="whoosh", start_ms=100, volume_db=-4.0),
            SFXEvent(sfx_type=scene["sfx"], start_ms=int(duration_ms * 0.35), volume_db=-3.0),
        ]
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

        # Render Cinematic Camera Move directly piped to FFmpeg
        silent_scene_mp4 = scenes_dir / f"{scene_id}_silent.mp4"
        scene_mp4 = scenes_dir / f"{scene_id}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "rgba",
            "-r", str(FPS),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "18",
            str(silent_scene_mp4),
        ]

        t0 = time.time()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

        for f in range(total_frames):
            frame_img = render_tactile_camera_shot(
                img_path=img_path,
                frame_idx=f,
                total_frames=total_frames,
                zoom_start=scene["zoom_start"],
                zoom_end=scene["zoom_end"],
                pan_x_max=scene["pan_x"],
                pan_y_max=scene["pan_y"],
                hud_tag=scene["hud_tag"],
            )
            proc.stdin.write(frame_img.tobytes())

        proc.stdin.close()
        proc.wait()
        t1 = time.time()

        # Mux audio onto silent scene MP4
        SceneAudioMuxer().mux(silent_scene_mp4, scene_audio_wav, scene_mp4, fps=30)
        logger.info(f"Rendered {total_frames} frames in {t1 - t0:.2f}s -> {scene_mp4}")
        scene_mp4s.append(scene_mp4)

    # Subtitles
    srt_path = final_dir / "subtitles.srt"
    srt_content = entries_to_srt(subtitle_entries)
    srt_path.write_text(srt_content, encoding="utf-8")

    # Master Audio track
    audio_concat_list = audio_dir / "audio_concat.txt"
    concat_lines = [f"file '{Path(audio_dir / (s['id'] + '_audio.wav')).resolve().as_posix()}'" for s in SCENES_METADATA]
    audio_concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    full_voice_wav = audio_dir / "full_voice_sfx.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
        "-c:a", "pcm_s16le", str(full_voice_wav)
    ], check=True, capture_output=True)

    # Tension BGM
    total_dur_ms = sum(durations_ms)
    logger.info(f"Total video duration: {total_dur_ms / 1000.0:.2f}s")
    bgm_wav = audio_dir / "investigation_bgm.wav"
    dur_s = total_dur_ms / 1000.0 + 2.0
    bgm_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc=sin(2*PI*55*t)*0.18 + sin(2*PI*110*t)*0.09 + sin(2*PI*220*t)*0.04:d={dur_s:.3f}:s=48000",
        "-af", f"lowpass=f=400,volume=-16dB,afade=t=in:d=1.5,afade=t=out:st={dur_s - 2.0:.2f}:d=2.0",
        "-c:a", "pcm_s16le",
        str(bgm_wav),
    ]
    subprocess.run(bgm_cmd, check=True, capture_output=True)

    master_audio_wav = audio_dir / "master_audio.wav"
    mix_cmd = [
        "ffmpeg", "-y",
        "-i", str(full_voice_wav),
        "-i", str(bgm_wav),
        "-filter_complex", "[0:a]volume=1.0dB[v];[1:a]volume=-16dB[b];[v][b]amix=inputs=2:duration=first:normalize=0[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(master_audio_wav),
    ]
    subprocess.run(mix_cmd, check=True, capture_output=True)

    # Final Concat Composition
    final_mp4 = final_dir / "pure_ai_torn_paper_vox_masterpiece.mp4"
    composer = FinalComposer()
    output_path, probe = composer.compose(
        scenes=scene_mp4s,
        audio=master_audio_wav,
        output=final_mp4,
        fps=30,
        width=1920,
        height=1080,
        tolerance_frames=3,
    )

    logger.info(f"=== Video Successfully Composed: {output_path} ===")
    logger.info(f"Probe: {probe.width}x{probe.height} @ {probe.fps}fps, Duration: {probe.duration_ms}ms, PixFmt: {probe.pix_fmt}")
    print(f"\n[DONE] Video Nghệ Thuật Xé Giấy AI Vox Hoàn Tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
