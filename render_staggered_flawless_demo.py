"""Re-render Elon Staggered Video with Flawless True-Torn Paper Cutout & Exact Aspect Ratio."""

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
logger = logging.getLogger("staggered_vox_perfect")

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


def ease_overshoot_bounce(t: float, overshoot: float = 1.4) -> float:
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


@lru_cache(maxsize=4)
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


def render_scene_001(f: int, n: int) -> Image.Image:
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "THƯƠNG VỤ THÂU TÓM TWITTER")

    # Layer 1: Year 2022 Badge (Time 0.0s - 1.0s)
    y22_prog = min(1.0, t_sec / 0.5)
    if y22_prog > 0:
        y_scale = ease_overshoot_bounce(y22_prog, 1.4)
        draw = ImageDraw.Draw(board)
        font_y = get_font(int(40 * y_scale), bold=True)
        draw.rectangle([(WIDTH // 2 - 150, 80), (WIDTH // 2 + 150, 136)], fill=(20, 24, 30, 245), outline=(255, 220, 20, 240), width=2)
        draw.text((WIDTH // 2, 108), "NĂM 2022", font=font_y, fill=(255, 220, 20, 255), anchor="mm")

    # Layer 2: FLAWLESS Elon Musk Torn-Paper Sticker (Drop with spring bounce at 1.0s)
    elon_start_t = 1.0
    if t_sec >= elon_start_t:
        elon_prog = min(1.0, (t_sec - elon_start_t) / 0.6)
        scale_anim = ease_overshoot_bounce(elon_prog, 1.3)
        cur_y = int(-300 + (300 + 580) * scale_anim)
        cur_angle = -4.0 * scale_anim

        elon_sticker = Image.open(ASSETS_DIR / "elon_true_torn_sticker.png").convert("RGBA")
        # Proportional scale
        w_curr = max(10, int(elon_sticker.width * (0.85 + 0.15 * scale_anim) * 0.95))
        h_curr = max(10, int(elon_sticker.height * (0.85 + 0.15 * scale_anim) * 0.95))
        im_t = elon_sticker.resize((w_curr, h_curr), Image.Resampling.BICUBIC)
        im_t = im_t.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)

        board.paste(im_t, (480 - im_t.width // 2, cur_y - im_t.height // 2), mask=im_t.split()[-1])

    # Layer 3: Twitter Bird Cutout Slides In (at 3.0s)
    twitter_start_t = 3.0
    if t_sec >= twitter_start_t:
        twit_prog = min(1.0, (t_sec - twitter_start_t) / 0.6)
        slide_anim = ease_overshoot_bounce(twit_prog, 1.3)
        cur_x = int(2100 - (2100 - 1440) * slide_anim)
        cur_angle = 3.5 * slide_anim

        raw_twit = Image.open(ASSETS_DIR / "twitter_bird_cutout_cutout.png").convert("RGBA")
        scale = 480.0 / raw_twit.height
        twit_fitted = raw_twit.resize((int(raw_twit.width * scale), int(raw_twit.height * scale)), Image.Resampling.BICUBIC)
        twit_cutout = PaperCraftService.create_torn_cutout(twit_fitted, PaperCutoutOptions(border_width=12, roughness=0.6))
        im_twit = twit_cutout.rotate(cur_angle, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_twit, (cur_x - im_twit.width // 2, 560 - im_twit.height // 2), mask=im_twit.split()[-1])

    # Layer 4: Red Yarn String Connects Elon to Twitter (at 4.8s)
    string_start_t = 4.8
    if t_sec >= string_start_t:
        str_prog = min(1.0, (t_sec - string_start_t) / 0.8)
        p_elon = (480, 390)
        p_twit = (1440, 390)
        InvestigationBoardService.draw_catenary_red_string(board, p_elon, p_twit, sag=40.0, progress=str_prog, width=5)

    # Layer 5: $44.000.000.000 Odometer Rolling Metric (at 5.5s)
    money_start_t = 5.5
    if t_sec >= money_start_t:
        m_prog = ease_out_cubic(min(1.0, (t_sec - money_start_t) / 1.2))
        val = int(44000000000 * m_prog)
        val_str = f"${val:,}".replace(",", ".")

        draw = ImageDraw.Draw(board)
        draw.rectangle([(WIDTH // 2 - 380, 770), (WIDTH // 2 + 380, 870)], fill=(16, 20, 26, 245), outline=(30, 220, 80, 255), width=3)
        font_money = get_font(52, bold=True)
        draw.text((WIDTH // 2, 820), val_str, font=font_money, fill=(40, 240, 90, 255), anchor="mm")
        font_lbl = get_font(18, bold=True)
        draw.text((WIDTH // 2, 750), "GIÁ TRỊ THƯƠNG VỤ THÂU TÓM", font=font_lbl, fill=(255, 220, 20, 240), anchor="mm")

    return board


def render_scene_002(f: int, n: int) -> Image.Image:
    t_sec = f / float(FPS)
    board = get_corkboard().copy()
    draw_hud(board, f, "CUỘC ĐIỀU TRA CỦA SEC")

    # Layer 1: Stock Crash Chart Slams In (0.0s - 1.2s)
    crash_prog = min(1.0, t_sec / 0.6)
    c_anim = ease_overshoot_bounce(crash_prog, 1.3)
    c_y = int(-300 + (300 + 560) * c_anim)

    raw_chart = Image.open(ASSETS_DIR / "stock_crash_chart_cutout.png").convert("RGBA")
    scale = 460.0 / raw_chart.height
    chart_fitted = raw_chart.resize((int(raw_chart.width * scale), int(raw_chart.height * scale)), Image.Resampling.BICUBIC)
    chart_cutout = PaperCraftService.create_torn_cutout(chart_fitted, PaperCutoutOptions(border_width=12, roughness=0.6))
    im_c = chart_cutout.rotate(-4.0 * c_anim, resample=Image.Resampling.BICUBIC, expand=True)
    board.paste(im_c, (500 - im_c.width // 2, c_y - im_c.height // 2), mask=im_c.split()[-1])

    # Layer 2: SEC Investigation Dossier Slides in from Right (at 2.5s)
    sec_start_t = 2.5
    if t_sec >= sec_start_t:
        sec_prog = min(1.0, (t_sec - sec_start_t) / 0.6)
        s_anim = ease_overshoot_bounce(sec_prog, 1.3)
        s_x = int(2100 - (2100 - 1420) * s_anim)

        raw_sec = Image.open(ASSETS_DIR / "sec_investigation_dossier_cutout.png").convert("RGBA")
        scale = 460.0 / raw_sec.height
        sec_fitted = raw_sec.resize((int(raw_sec.width * scale), int(raw_sec.height * scale)), Image.Resampling.BICUBIC)
        sec_cutout = PaperCraftService.create_torn_cutout(sec_fitted, PaperCutoutOptions(border_width=12, roughness=0.6))
        im_s = sec_cutout.rotate(3.5 * s_anim, resample=Image.Resampling.BICUBIC, expand=True)
        board.paste(im_s, (s_x - im_s.width // 2, 560 - im_s.height // 2), mask=im_s.split()[-1])

    # Layer 3: Yellow Sticky Note: "MARKET MANIPULATION?" (at 4.2s)
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

    # Layer 4: Red Yarn String connecting Chart to SEC Dossier (at 5.0s)
    str_start_t = 5.0
    if t_sec >= str_start_t:
        str_p = min(1.0, (t_sec - str_start_t) / 0.6)
        InvestigationBoardService.draw_catenary_red_string(board, (500, 360), (1420, 360), sag=35.0, progress=str_p, width=5)

    # Layer 5: Giant Rubber Stamp: UNDER INVESTIGATION Slams Down (at 5.8s)
    stamp_start_t = 5.8
    if t_sec >= stamp_start_t:
        st_prog = ease_overshoot_bounce(min(1.0, (t_sec - stamp_start_t) / 0.4), 1.5)
        InvestigationBoardService.render_investigation_stamp(
            board, (WIDTH // 2, 740), "UNDER INVESTIGATION", angle_deg=-12.0, scale=st_prog * 1.2
        )

    return board


SCENES = [
    {
        "id": "scene_001",
        "narration": "Năm 2022, Elon Musk bất ngờ tung ra lời đề nghị thâu tóm Twitter với mức giá điên rồ: 44 tỷ đô la.",
        "renderer": render_scene_001,
        "sfx_timeline": [
            ("pop", 100),
            ("pushpin_hit", 1100),
            ("paper_slide", 3100),
            ("whoosh", 4900),
            ("typewriter", 5600),
        ],
    },
    {
        "id": "scene_002",
        "narration": "Ngay sau khi tiếp quản, giá cổ phiếu lao dốc và hàng loạt cuộc điều tra từ Ủy ban Chứng khoán SEC bắt đầu nổ ra.",
        "renderer": render_scene_002,
        "sfx_timeline": [
            ("pushpin_hit", 100),
            ("paper_slide", 2600),
            ("pop", 4300),
            ("whoosh", 5100),
            ("camera_click", 5900),
        ],
    },
]


def main() -> None:
    logger.info("=== Starting Flawless Staggered Vox Video Render ===")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = PROJECT_DIR / "scenes"
    audio_dir = PROJECT_DIR / "audio"
    final_dir = PROJECT_DIR / "final"
    for d in (scenes_dir, audio_dir, final_dir):
        d.mkdir(parents=True, exist_ok=True)

    voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))
    scene_mp4s: list[Path] = []
    durations_ms: list[int] = []
    subtitle_entries: list[SubtitleEntry] = []
    current_time_ms = 0
    sfx_service = AutoSFXService()

    for idx, scene in enumerate(SCENES):
        scene_id = scene["id"]
        narration = scene["narration"]
        logger.info(f"--- Rendering Scene: {scene_id} [{idx + 1}/2] ---")

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

        sfx_events = [
            SFXEvent(sfx_type=sfx_type, start_ms=st_ms, volume_db=-3.0)
            for sfx_type, st_ms in scene["sfx_timeline"]
        ]
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

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

        SceneAudioMuxer().mux(silent_scene_mp4, scene_audio_wav, scene_mp4, fps=30)
        logger.info(f"Rendered {total_frames} frames in {t1 - t0:.2f}s -> {scene_mp4}")
        scene_mp4s.append(scene_mp4)

    # Subtitles
    srt_path = final_dir / "subtitles.srt"
    srt_path.write_text(entries_to_srt(subtitle_entries), encoding="utf-8")

    # Master Audio track
    audio_concat_list = audio_dir / "audio_concat.txt"
    concat_lines = [f"file '{Path(audio_dir / (s['id'] + '_audio.wav')).resolve().as_posix()}'" for s in SCENES]
    audio_concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    full_voice_wav = audio_dir / "full_voice_sfx.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
        "-c:a", "pcm_s16le", str(full_voice_wav)
    ], check=True, capture_output=True)

    bgm_wav = audio_dir / "elon_bgm.wav"
    dur_s = sum(durations_ms) / 1000.0 + 2.0
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

    final_mp4 = final_dir / "elon_staggered_layer_flawless.mp4"
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
    print(f"\n[DONE] Video Flawless Cutout Vox Demo Hoàn Tất tại: {output_path.resolve()}")


if __name__ == "__main__":
    main()
