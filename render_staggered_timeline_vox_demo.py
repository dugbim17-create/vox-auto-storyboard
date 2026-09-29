"""True Staggered Multi-Layer Vox Motion Graphics Engine.

Implements exact voice-synchronized layer popups:
- When voice mentions a person/subject -> That specific torn-paper cutout slams down with bounce & pushpin
- When voice mentions a company/target -> Target cutout slides in and sticks with tape
- When voice mentions a year/metric -> Odometer numbers jump and roll dynamically
- When voice mentions scandal/connection -> Red yarn string shoots between pins & red rubber stamp slams down
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
from app.services.investigation_board import InvestigationBoardService, StickyNote
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("staggered_vox_engine")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_elon_staggered_demo")
ASSETS_DIR = PROJECT_DIR / "ai_assets"
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


# Easing Curves with Overshoot Spring Bounce
def ease_overshoot_bounce(t: float, overshoot: float = 1.6) -> float:
    """Natural physical bounce curve (overshoots slightly then settles)."""
    t = max(0.0, min(1.0, t))
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    t -= 1.0
    return t * t * ((overshoot + 1.0) * t + overshoot) + 1.0


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)


# --------------------------------------------------------------------------- #
# Cached Cutout Processors
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8)
def get_cached_cutout(path_str: str, max_w: int, max_h: int) -> Image.Image:
    im = Image.open(path_str).convert("RGBA")
    scale = min(max_w / float(im.width), max_h / float(im.height))
    nw, nh = max(10, int(im.width * scale)), max(10, int(im.height * scale))
    im_resized = im.resize((nw, nh), Image.Resampling.BICUBIC)

    alpha = im_resized.split()[-1]
    pad = 30
    canvas = Image.new("RGBA", (nw + pad * 2, nh + pad * 2), (0, 0, 0, 0))

    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(8))
    shadow_fill = Image.new("RGBA", (nw, nh), (12, 14, 18, 150))
    canvas.paste(shadow_fill, (pad + 6, pad + 10), mask=shadow_mask)
    canvas.paste(im_resized, (pad, pad), mask=alpha)
    return canvas


@lru_cache(maxsize=2)
def get_corkboard() -> Image.Image:
    return InvestigationBoardService.generate_corkboard_texture(WIDTH, HEIGHT)


def draw_hud(canvas: Image.Image, frame_num: int, tag: str) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
    c_len = 22
    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 220, 20, 220), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 220, 20, 220), width=3)

    font_tag = get_font(16, bold=True)
    draw.text((WIDTH // 2, 52), f"HỒ SƠ ĐIỀU TRA // {tag.upper()}", font=font_tag, fill=(255, 220, 20, 230), anchor="mm")
    font_mono = get_font(14, bold=False)
    draw.text((WIDTH - 300, 52), f"BẰNG CHỨNG SỐ // F:{frame_num:04d}", font=font_mono, fill=(255, 255, 255, 80))


# --------------------------------------------------------------------------- #
# Scene 1: Elon Musk -> Twitter -> $44B Metric -> Red String
# Voice: "Năm 2022, Elon Musk bất ngờ tung ra lời đề nghị thâu tóm Twitter với mức giá điên rồ: 44 tỷ đô la."
# --------------------------------------------------------------------------- #
def render_staggered_scene_001(f: int, n: int) -> Image.Image:
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "THƯƠNG VỤ THÂU TÓM TWITTER")

    # Layer 1: Year 2022 Badge (Time 0.0s - 1.2s)
    # Pops in at start
    y22_prog = min(1.0, t_sec / 0.5)
    if y22_prog > 0:
        y_scale = ease_overshoot_bounce(y22_prog, 1.4)
        draw = ImageDraw.Draw(board)
        font_y = get_font(int(42 * y_scale), bold=True)
        # Top banner
        draw.rectangle([(WIDTH // 2 - 160, 80), (WIDTH // 2 + 160, 136)], fill=(20, 24, 30, 240), outline=(255, 220, 20, 240), width=2)
        draw.text((WIDTH // 2, 108), "NĂM 2022", font=font_y, fill=(255, 220, 20, 255), anchor="mm")

    # Layer 2: Elon Musk Polaroid Slam Drop (Triggered at 1.0s when voice says "Elon Musk")
    elon_start_t = 1.0
    if t_sec >= elon_start_t:
        elon_prog = min(1.0, (t_sec - elon_start_t) / 0.6)
        scale_anim = ease_overshoot_bounce(elon_prog, 1.3)
        # Drop from top
        cur_y = int(-300 + (300 + 560) * scale_anim)
        cur_angle = -5.0 * scale_anim

        elon_cutout = get_cached_cutout(str(ASSETS_DIR / "elon_polaroid_cutout.png"), 540, 520)
        # Scale and rotate
        w_curr = max(10, int(elon_cutout.width * (0.8 + 0.2 * scale_anim)))
        h_curr = max(10, int(elon_cutout.height * (0.8 + 0.2 * scale_anim)))
        im_t = elon_cutout.resize((w_curr, h_curr), Image.Resampling.BICUBIC)
        im_t = im_t.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)

        board.paste(im_t, (480 - im_t.width // 2, cur_y - im_t.height // 2), mask=im_t.split()[-1])

    # Layer 3: Twitter Bird Cutout Slides In (Triggered at 3.0s when voice says "Twitter")
    twitter_start_t = 3.0
    if t_sec >= twitter_start_t:
        twit_prog = min(1.0, (t_sec - twitter_start_t) / 0.6)
        slide_anim = ease_overshoot_bounce(twit_prog, 1.3)
        cur_x = int(2100 - (2100 - 1440) * slide_anim)
        cur_angle = 4.0 * slide_anim

        twit_cutout = get_cached_cutout(str(ASSETS_DIR / "twitter_bird_cutout_cutout.png"), 560, 520)
        im_twit = twit_cutout.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_twit, (cur_x - im_twit.width // 2, 560 - im_twit.height // 2), mask=im_twit.split()[-1])

    # Layer 4: Red Yarn String Connects Elon to Twitter (Triggered at 4.8s)
    string_start_t = 4.8
    if t_sec >= string_start_t:
        str_prog = min(1.0, (t_sec - string_start_t) / 0.8)
        p_elon = (480, 370)
        p_twit = (1440, 370)
        InvestigationBoardService.draw_catenary_red_string(board, p_elon, p_twit, sag=45.0, progress=str_prog, width=5)

    # Layer 5: $44.000.000.000 Mega Odometer Metric (Triggered at 5.5s when voice says "44 tỷ đô la")
    money_start_t = 5.5
    if t_sec >= money_start_t:
        m_prog = ease_out_cubic(min(1.0, (t_sec - money_start_t) / 1.2))
        val = int(44000000000 * m_prog)
        val_str = f"${val:,}".replace(",", ".")

        draw = ImageDraw.Draw(board)
        # Background dark pill
        draw.rectangle([(WIDTH // 2 - 380, 770), (WIDTH // 2 + 380, 870)], fill=(16, 20, 26, 245), outline=(30, 220, 80, 255), width=3)
        font_money = get_font(52, bold=True)
        draw.text((WIDTH // 2, 820), val_str, font=font_money, fill=(40, 240, 90, 255), anchor="mm")

        # Label above
        font_lbl = get_font(18, bold=True)
        draw.text((WIDTH // 2, 750), "GIÁ TRỊ THƯƠNG VỤ THÂU TÓM", font=font_lbl, fill=(255, 220, 20, 240), anchor="mm")

    return board


# --------------------------------------------------------------------------- #
# Scene 2: Stock Crash -> SEC Dossier -> Under Investigation Stamp
# Voice: "Ngay sau khi tiếp quản, giá cổ phiếu lao dốc và hàng loạt cuộc điều tra từ Ủy ban Chứng khoán SEC bắt đầu nổ ra."
# --------------------------------------------------------------------------- #
def render_staggered_scene_002(f: int, n: int) -> Image.Image:
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "CUỘC ĐIỀU TRA CỦA SEC")

    # Layer 1: Stock Crash Chart Slams In (Time 0.0s - 1.2s when voice says "giá cổ phiếu lao dốc")
    crash_prog = min(1.0, t_sec / 0.6)
    c_anim = ease_overshoot_bounce(crash_prog, 1.3)
    c_y = int(-300 + (300 + 560) * c_anim)
    chart_cutout = get_cached_cutout(str(ASSETS_DIR / "stock_crash_chart_cutout.png"), 540, 520)
    im_c = chart_cutout.rotate(-4.0 * c_anim, resample=Image.Resampling.BICUBIC, expand=True)
    board.paste(im_c, (500 - im_c.width // 2, c_y - im_c.height // 2), mask=im_c.split()[-1])

    # Layer 2: SEC Investigation Dossier Slides in from Right (Triggered at 2.5s when voice says "điều tra từ SEC")
    sec_start_t = 2.5
    if t_sec >= sec_start_t:
        sec_prog = min(1.0, (t_sec - sec_start_t) / 0.6)
        s_anim = ease_overshoot_bounce(sec_prog, 1.3)
        s_x = int(2100 - (2100 - 1420) * s_anim)
        sec_cutout = get_cached_cutout(str(ASSETS_DIR / "sec_investigation_dossier_cutout.png"), 540, 520)
        im_s = sec_cutout.rotate(3.5 * s_anim, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_s, (s_x - im_s.width // 2, 560 - im_s.height // 2), mask=im_s.split()[-1])

    # Layer 3: Yellow Sticky Note: "MARKET MANIPULATION?" (Triggered at 4.2s)
    note_start_t = 4.2
    if t_sec >= note_start_t:
        n_prog = ease_overshoot_bounce(min(1.0, (t_sec - note_start_t) / 0.5), 1.4)
        note = InvestigationBoardService.render_sticky_note(
            StickyNote(
                text="THAO TÚNG THỊ TRƯỜNG?",
                subtext="SEC ĐANG MỞ RỘNG ĐIỀU TRA",
                size=(320, 180),
                angle_deg=-6.0,
            )
        )
        board.paste(note, (WIDTH // 2 - note.width // 2, 420 - note.height // 2), mask=note.split()[-1])

    # Layer 4: Red Yarn String connecting Chart to SEC Dossier (Triggered at 5.0s)
    str_start_t = 5.0
    if t_sec >= str_start_t:
        str_p = min(1.0, (t_sec - str_start_t) / 0.6)
        InvestigationBoardService.draw_catenary_red_string(board, (500, 360), (1420, 360), sag=35.0, progress=str_p, width=5)

    # Layer 5: Giant Rubber Stamp: UNDER INVESTIGATION Slams Down (Triggered at 5.8s)
    stamp_start_t = 5.8
    if t_sec >= stamp_start_t:
        st_prog = ease_overshoot_bounce(min(1.0, (t_sec - stamp_start_t) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(
            board, (WIDTH // 2, 740), "UNDER INVESTIGATION", angle_deg=-12.0, scale=st_prog * 1.2
        )

    return board


SCENES_METADATA = [
    {
        "id": "scene_001_takeover",
        "narration": "Năm 2022, Elon Musk bất ngờ tung ra lời đề nghị thâu tóm Twitter với mức giá điên rồ: 44 tỷ đô la.",
        "renderer": render_staggered_scene_001,
        "sfx_timeline": [
            ("pop", 100),            # 0.1s: Year badge pop
            ("pushpin_hit", 1100),    # 1.1s: Elon polaroid slam drop
            ("paper_slide", 3100),   # 3.1s: Twitter bird cutout slide
            ("whoosh", 4900),        # 4.9s: Red string shoot
            ("typewriter", 5600),    # 5.6s: $44B Odometer rolling
        ],
    },
    {
        "id": "scene_002_investigation",
        "narration": "Ngay sau khi tiếp quản, giá cổ phiếu lao dốc và hàng loạt cuộc điều tra từ Ủy ban Chứng khoán SEC bắt đầu nổ ra.",
        "renderer": render_staggered_scene_002,
        "sfx_timeline": [
            ("pushpin_hit", 100),    # 0.1s: Crash chart slam drop
            ("paper_slide", 2600),   # 2.6s: SEC dossier slide in
            ("pop", 4300),           # 4.3s: Sticky note pop
            ("whoosh", 5100),        # 5.1s: Red string shoot
            ("camera_click", 5900),  # 5.9s: Stamp slam impact
        ],
    },
]


def main() -> None:
    logger.info("=== Starting True Staggered Voice-Synchronized Vox Video Generation ===")
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
        logger.info(f"--- Rendering Staggered Scene: {scene_id} [{idx + 1}/2] ---")

        # Synthesize Voice
        voice_wav = audio_dir / f"{scene_id}_voice.wav"
        if not voice_wav.is_file():
            with wave.open(str(voice_wav), "wb") as wf:
                voice.synthesize_wav(narration, wf)

        with wave.open(str(voice_wav), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_ms = max(7800, int((frames / float(rate)) * 1000) + 600)

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

        # SFX Track with exact synchronized cue timing
        sfx_events = [
            SFXEvent(sfx_type=sfx_type, start_ms=st_ms, volume_db=-3.0)
            for sfx_type, st_ms in scene["sfx_timeline"]
        ]
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

        # Render Staggered Frame-by-Frame Video into FFmpeg pipe
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
        renderer_fn = scene["renderer"]

        for f in range(total_frames):
            frame_img = renderer_fn(f, total_frames)
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
    bgm_wav = audio_dir / "elon_bgm.wav"
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
    final_mp4 = final_dir / "elon_staggered_layer_vox_demo.mp4"
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
    print(f"\n[DONE] Video Staggered Layer Vox Demo Hoàn Tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
