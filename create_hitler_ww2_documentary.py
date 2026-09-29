"""Production script to generate a 60-second Vox-style documentary: 'Cuộc đời Hitler và Thế chiến thứ 2'."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from piper.voice import PiperVoice

from app.schemas.motion_plan import build_motion_plan
from app.services.document_highlighter import DocumentHighlighterService, HighlightOptions
from app.services.ffmpeg_compiler import CompileOptions, MotionCompiler
from app.services.final_composer import FinalComposer
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vox_production")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_hitler_ww2_doc")
PIPER_MODEL = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx")
PIPER_CONFIG = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx.json")

# Font candidates
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


SCENES_DATA = [
    {
        "id": "scene_001",
        "narration": "Từ một kẻ lang bạt vô danh ở Vienna, Adolf Hitler trỗi dậy trên đống đổ nát của nước Đức sau Thế chiến thứ nhất.",
        "template": "01_subject_slide_headline_pop",
        "headline": "1889 - 1933: TRỖI DẬY",
        "sub_badge": "KHỞI NGUỒN QUYỀN LỰC",
        "doc_title": "HIỆP ƯỚC VERSAILLES & KHỦNG HOẢNG WEIMAR",
        "bg_theme": "dark_slate",
        "subject_type": "portrait",
    },
    {
        "id": "scene_002",
        "narration": "Năm 1933, Hitler trở thành Thủ tướng Đức, nhanh chóng thâu tóm quyền lực và thiết lập đế chế độc tài phát xít tàn bạo.",
        "template": "07_document_highlight",
        "headline": "1933: ĐẾ CHẾ ĐỘC TÀI",
        "sub_badge": "ĐẠO LUẬT TRAO QUYỀN",
        "doc_title": "ERMÄCHTIGUNGSGESETZ — BÃI BỎ DÂN CHỦ",
        "bg_theme": "sepia_paper",
        "subject_type": "document",
    },
    {
        "id": "scene_003",
        "narration": "Ngày 1 tháng 9 năm 1939, quân đội Đức tràn qua biên giới Ba Lan. Chiến thuật chớp nhoáng Blitzkrieg đẩy toàn cầu vào thảm họa.",
        "template": "03_map_pan_marker_pulse",
        "headline": "1939: THẾ CHIẾN II BÙNG NỔ",
        "sub_badge": "CHIẾN THUẬT BLITZKRIEG",
        "doc_title": "MẶT TRẬN CHÂU ÂU — BA LAN THẤT THỦ",
        "bg_theme": "military_map",
        "subject_type": "map",
    },
    {
        "id": "scene_004",
        "narration": "Năm 1941, Hitler xé bỏ hiệp ước, điều hơn ba triệu quân tràn vào Liên Xô, mở ra chiến trường đẫm máu nhất lịch sử loài người.",
        "template": "04_before_after_split",
        "headline": "1941: CHIẾN DỊCH BARBAROSSA",
        "sub_badge": "3.000.000 QUÂN XÂM LƯỢC",
        "doc_title": "MẶT TRẬN PHÍA ĐÔNG — LIÊN XÔ PHẢN CÔNG",
        "bg_theme": "steel_gray",
        "subject_type": "military",
    },
    {
        "id": "scene_005",
        "narration": "Thất bại thảm khốc tại Stalingrad và trận đổ bộ Normandy năm 1944 đã đẩy quân phát xít vào thế gọng kìm sụp đổ không thể cứu vãn.",
        "template": "06_timeline_cards",
        "headline": "1943 - 1944: BƯỚC NGOẶT ĐẢO CHIỀU",
        "sub_badge": "STALINGRAD & NORMANDY",
        "doc_title": "GỌNG KÌM ĐỒNG MINH VÀ HỒNG QUÂN",
        "bg_theme": "dark_slate",
        "subject_type": "timeline",
    },
    {
        "id": "scene_006",
        "narration": "Dưới ách thống trị tàn độc, hơn sáu triệu người Do Thái cùng hàng triệu thường dân vô tội đã bị tàn sát trong các trại tập trung.",
        "template": "07_document_highlight",
        "headline": "THẢM HỌA HOLOCAUST",
        "sub_badge": "TỘI ÁC DIỆT CHỦNG",
        "doc_title": "CÁC TRẠI TẬP TRUNG TỬ THẦN",
        "bg_theme": "charcoal_dark",
        "subject_type": "document",
    },
    {
        "id": "scene_007",
        "narration": "Tháng 4 năm 1945, khi Hồng quân Liên Xô siết chặt vòng vây Berlin, Hitler đã tự sát dưới hầm ngầm, kết thúc triều đại bóng tối.",
        "template": "11_object_zoom_texture_wipe",
        "headline": "1945: BERLIN SỤP ĐỔ",
        "sub_badge": "NGÀY TÀN TRONG HẦM NGẦM",
        "doc_title": "HỒNG QUÂN CẮM CỜ TRÊN NHÀ QUỐC HỘI ĐỨC",
        "bg_theme": "ruins_sepia",
        "subject_type": "ruins",
    },
    {
        "id": "scene_008",
        "narration": "Thế chiến thứ hai cướp đi hơn 70 triệu sinh mạng. Sự sụp đổ của chủ nghĩa phát xít mãi là lời cảnh tỉnh đắt giá cho hòa bình thế giới.",
        "template": "12_conclusion_lockup",
        "headline": "HƠN 70 TRIỆU NGƯỜI THIỆT MẠNG",
        "sub_badge": "BÀI HỌC VĨNH CỬU CHO HÒA BÌNH",
        "doc_title": "TÒA ÁN QUỐC TẾ NUREMBERG & HÒA BÌNH THẾ GIỚI",
        "bg_theme": "deep_crimson",
        "subject_type": "memorial",
    },
]


def render_scene_background(width: int, height: int, theme: str) -> Image.Image:
    """Generate high-contrast archival documentary background with procedural textures."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(canvas)

    if theme == "dark_slate":
        color_top = (26, 30, 36)
        color_bot = (14, 16, 20)
    elif theme == "sepia_paper":
        color_top = (42, 36, 28)
        color_bot = (20, 18, 14)
    elif theme == "military_map":
        color_top = (30, 36, 32)
        color_bot = (16, 20, 18)
    elif theme == "steel_gray":
        color_top = (32, 34, 38)
        color_bot = (18, 19, 22)
    elif theme == "charcoal_dark":
        color_top = (22, 22, 24)
        color_bot = (10, 10, 12)
    elif theme == "ruins_sepia":
        color_top = (38, 28, 24)
        color_bot = (18, 14, 12)
    else:  # deep_crimson
        color_top = (45, 18, 20)
        color_bot = (18, 10, 12)

    # Vertical gradient
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] * (1 - ratio) + color_bot[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bot[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bot[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Grid / coordinate lines (Vox editorial graphic signature)
    grid_color = (255, 255, 255, 12)
    for gx in range(0, width, 120):
        draw.line([(gx, 0), (gx, height)], fill=grid_color, width=1)
    for gy in range(0, height, 120):
        draw.line([(0, gy), (width, gy)], fill=grid_color, width=1)

    # Subtle vignette
    vignette = Image.new("L", (width, height), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse((-width * 0.2, -height * 0.2, width * 1.2, height * 1.2), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120))
    
    # Overlay film grain
    grain = PaperCraftService.generate_film_grain_texture(width, height, intensity=0.05)
    canvas = Image.alpha_composite(canvas, grain)
    return canvas


def render_scene_subject(width: int, height: int, data: dict) -> Image.Image:
    """Generate thematic subject graphic styled with torn paper cutout."""
    subject_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(subject_canvas)

    center_x = width // 2
    center_y = int(height * 0.52)
    card_w = int(width * 0.44)
    card_h = int(height * 0.54)

    x0 = center_x - card_w // 2
    y0 = center_y - card_h // 2
    x1 = center_x + card_w // 2
    y1 = center_y + card_h // 2

    # Card background (archival paper look)
    draw.rectangle((x0, y0, x1, y1), fill=(244, 240, 230, 255), outline=(190, 180, 160, 255), width=2)

    # Top red header banner
    banner_h = 44
    draw.rectangle((x0, y0, x1, y0 + banner_h), fill=(195, 30, 30, 255))
    font_badge = get_font(20, bold=True)
    draw.text((x0 + 18, y0 + 12), data["sub_badge"], font=font_badge, fill=(255, 255, 255, 255))

    # Inner document / subject graphic
    font_title = get_font(24, bold=True)
    draw.text((x0 + 24, y0 + banner_h + 24), data["doc_title"], font=font_title, fill=(28, 28, 32, 255))

    # Decorative document content simulation lines
    font_body = get_font(18, bold=False)
    lines = [
        "TÀI LIỆU LỊCH SỬ / HỒ SƠ PHÓNG SỰ",
        "• Dữ liệu xác thực qua các văn kiện quốc tế",
        "• Phân tích diễn biến và tác động toàn cầu",
        "• Hồ sơ tư liệu lưu trữ thế kỷ 20",
    ]
    for i, line in enumerate(lines):
        ly = y0 + banner_h + 75 + i * 36
        draw.text((x0 + 24, ly), line, font=font_body, fill=(70, 70, 75, 255))

    # Apply highlighter stroke on the first line if template is document highlight
    if data["template"] == "07_document_highlight":
        box = (x0 + 20, y0 + banner_h + 20, x0 + card_w - 20, y0 + banner_h + 56)
        subject_canvas = DocumentHighlighterService.apply_highlight_sweep(
            subject_canvas, box, progress=1.0, options=HighlightOptions(color_name="yellow", opacity=0.6)
        )

    # Apply torn paper cutout treatment
    cutout = PaperCraftService.create_torn_cutout(
        subject_canvas,
        PaperCutoutOptions(border_width=10, roughness=0.3, shadow=True, shadow_opacity=0.45)
    )
    
    # Scale back to canvas
    final_subj = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    paste_x = (width - cutout.width) // 2
    paste_y = (height - cutout.height) // 2 + 30
    final_subj.paste(cutout, (paste_x, paste_y), mask=cutout.split()[-1])
    return final_subj


def render_scene_foreground(width: int, height: int, data: dict) -> Image.Image:
    """Generate kinetic typography and editorial framing overlay."""
    fg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    # Top left headline banner
    headline = data["headline"]
    font_headline = get_font(42, bold=True)
    
    # Text container box
    hx = 80
    hy = 70
    bbox = draw.textbbox((hx, hy), headline, font=font_headline)
    pad_x = 18
    pad_y = 10
    draw.rectangle(
        (bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y),
        fill=(220, 35, 35, 240)
    )
    draw.text((hx, hy), headline, font=font_headline, fill=(255, 255, 255, 255))

    # Outer border / TV safe crop frame
    border_color = (255, 255, 255, 35)
    draw.rectangle((40, 40, width - 40, height - 40), outline=border_color, width=2)
    # Corner marks (Vox viewfinder style)
    c_len = 24
    for cx, cy in [(40, 40), (width - 40, 40), (40, height - 40), (width - 40, height - 40)]:
        sx = 1 if cx == 40 else -1
        sy = 1 if cy == 40 else -1
        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(255, 230, 20, 220), width=3)
        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(255, 230, 20, 220), width=3)

    return fg


def main() -> None:
    logger.info("=== Starting 60s Vox Documentary Production ===")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    scenes_dir = PROJECT_DIR / "scenes"
    audio_dir = PROJECT_DIR / "audio"
    layers_dir = PROJECT_DIR / "layers"
    final_dir = PROJECT_DIR / "final"
    for d in (scenes_dir, audio_dir, layers_dir, final_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Load Piper Voice
    logger.info("1. Loading Piper TTS ('Ngọc Huyền')...")
    voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))

    scene_mp4s: list[Path] = []
    durations_ms: list[int] = []
    subtitle_entries = []
    current_time_ms = 0

    sfx_service = AutoSFXService()
    muxer = SceneAudioMuxer()
    compiler = MotionCompiler()

    for idx, scene in enumerate(SCENES_DATA, start=1):
        scene_id = scene["id"]
        narration = scene["narration"]
        logger.info(f"--- Processing {scene_id} [{idx}/{len(SCENES_DATA)}] ---")

        # Synthesize voice
        raw_voice_wav = audio_dir / f"{scene_id}_voice.wav"
        with wave.open(str(raw_voice_wav), "wb") as wf:
            voice.synthesize_wav(narration, wf)

        # Probe duration
        with wave.open(str(raw_voice_wav), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_ms = max(5000, int((frames / float(rate)) * 1000) + 600)  # +600ms padding for clean pacing

        durations_ms.append(duration_ms)

        # Build Subtitle entry
        subtitle_entries.append({
            "index": idx,
            "start_ms": current_time_ms + 150,
            "end_ms": current_time_ms + duration_ms - 200,
            "text": narration,
        })
        current_time_ms += duration_ms

        # Render Visual Layers (1920x1080)
        bg_img = render_scene_background(1920, 1080, scene["bg_theme"])
        subj_img = render_scene_subject(1920, 1080, scene)
        fg_img = render_scene_foreground(1920, 1080, scene)
        grain_img = PaperCraftService.generate_film_grain_texture(1920, 1080, intensity=0.04)

        bg_path = layers_dir / f"{scene_id}_bg.png"
        subj_path = layers_dir / f"{scene_id}_subj.png"
        fg_path = layers_dir / f"{scene_id}_fg.png"
        tex_path = layers_dir / f"{scene_id}_tex.png"

        bg_img.save(bg_path)
        subj_img.save(subj_path)
        fg_img.save(fg_path)
        grain_img.save(tex_path)

        # Generate Auto-SFX Track
        sfx_events = AutoSFXService.derive_scene_sfx_events(
            scene["template"], duration_ms, transition_out="paper_tear" if idx == 8 else "wipe_left"
        )
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        # Mix Voice + SFX into scene audio
        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(raw_voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

        # Build Motion Plan
        mid_ms = duration_ms // 2
        plan_dict = {
            "scene_id": scene_id,
            "duration_ms": duration_ms,
            "fps": 30,
            "canvas": {"width": 1920, "height": 1080},
            "camera": {
                "scale": {"easing": "ease_in_out", "keyframes": [[0, 1.0], [duration_ms, 1.04]]},
                "x": {"easing": "ease_in_out", "keyframes": [[0, 0], [duration_ms, 25]]},
            },
            "layers": [
                {
                    "id": "background",
                    "asset_role": "background",
                    "z": 0,
                    "transform": {"scale": {"easing": "linear", "keyframes": [[0, 1.0], [duration_ms, 1.03]]}},
                },
                {
                    "id": "subject",
                    "asset_role": "subject",
                    "z": 10,
                    "transform": {
                        "scale": {"easing": "ease_out", "keyframes": [[0, 0.92], [int(duration_ms * 0.35), 1.0], [duration_ms, 1.02]]},
                        "y": {"easing": "ease_in_out", "keyframes": [[0, 20], [duration_ms, -15]]},
                        "opacity": {"easing": "ease_in", "keyframes": [[0, 0.2], [int(duration_ms * 0.2), 1.0]]},
                    },
                },
                {
                    "id": "foreground",
                    "asset_role": "foreground",
                    "z": 20,
                    "transform": {
                        "x": {"easing": "linear", "keyframes": [[0, 0], [duration_ms, -12]]},
                    },
                },
            ],
            "text_animations": [],
            "effects": [
                {"type": "film_grain", "amount": 0.04},
            ],
            "transition_in": "none",
            "transition_out": "crossfade" if idx < len(SCENES_DATA) else "none",
        }

        assets_map = {
            "background": str(bg_path),
            "subject": str(subj_path),
            "foreground": str(fg_path),
        }

        # Compile and render scene MP4
        silent_scene_mp4 = scenes_dir / f"{scene_id}_silent.mp4"
        scene_final_mp4 = scenes_dir / f"{scene_id}.mp4"

        if not silent_scene_mp4.is_file():
            compiled = compiler.compile(
                plan_dict,
                assets=assets_map,
                options=CompileOptions(fps=30, width=1920, height=1080, crf=18, preset="fast"),
                output_path=silent_scene_mp4,
            )
            compiler.run(compiled, check=True)

        # Mux scene video + mixed audio
        if not scene_final_mp4.is_file():
            muxer.mux(silent_scene_mp4, scene_audio_wav, scene_final_mp4, fps=30)
        scene_mp4s.append(scene_final_mp4)

    # Generate Full SRT Subtitles
    srt_path = final_dir / "subtitles.srt"
    srt_content = entries_to_srt([
        SubtitleEntry(
            index=e["index"],
            start_ms=e["start_ms"],
            end_ms=e["end_ms"],
            text=e["text"]
        )
        for e in subtitle_entries
    ])
    srt_path.write_text(srt_content, encoding="utf-8")
    logger.info(f"Subtitles written to {srt_path}")

    # Combine all scene audio into one full master track
    audio_concat_list = audio_dir / "audio_concat.txt"
    concat_lines = [f"file '{Path(audio_dir / (s['id'] + '_audio.wav')).resolve().as_posix()}'" for s in SCENES_DATA]
    audio_concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    full_voice_wav = audio_dir / "full_voice_sfx.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_list),
        "-c:a", "pcm_s16le", str(full_voice_wav)
    ], check=True, capture_output=True)

    # Generate Procedural Cinematic BGM (Dark ambient drone + subtle rhythm)
    total_dur_ms = sum(durations_ms)
    logger.info(f"Total video duration: {total_dur_ms / 1000.0:.2f}s")
    bgm_wav = audio_dir / "documentary_bgm.wav"
    dur_s = total_dur_ms / 1000.0 + 2.0
    bgm_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"aevalsrc=sin(2*PI*55*t)*0.15 + sin(2*PI*110*t)*0.08 + sin(2*PI*220*t)*0.03:d={dur_s:.3f}:s=48000",
        "-af", f"lowpass=f=400,volume=-18dB,afade=t=in:d=2.0,afade=t=out:st={dur_s - 2.5:.2f}:d=2.5",
        "-c:a", "pcm_s16le",
        str(bgm_wav),
    ]
    subprocess.run(bgm_cmd, check=True, capture_output=True)

    # Mix full vocal+SFX with BGM
    master_audio_wav = audio_dir / "master_audio.wav"
    mix_cmd = [
        "ffmpeg", "-y",
        "-i", str(full_voice_wav),
        "-i", str(bgm_wav),
        "-filter_complex", "[0:a]volume=1.0dB[v];[1:a]volume=-18dB[b];[v][b]amix=inputs=2:duration=first:normalize=0[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(master_audio_wav)
    ]
    subprocess.run(mix_cmd, check=True, capture_output=True)

    # Compose Final MP4 Video with Concat and master audio
    final_mp4 = final_dir / "hitler_ww2_60s_final.mp4"
    composer = FinalComposer()
    output_path, probe = composer.compose(
        scenes=scene_mp4s,
        audio=master_audio_wav,
        output=final_mp4,
        fps=30,
        width=1920,
        height=1080,
    )

    logger.info(f"=== Video Successfully Composed: {output_path} ===")
    logger.info(f"Probe: {probe.width}x{probe.height} @ {probe.fps}fps, Duration: {probe.duration_ms}ms, PixFmt: {probe.pix_fmt}")
    print(f"\n[DONE] Video hoàn tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
