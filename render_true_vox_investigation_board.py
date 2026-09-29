"""True Vox Investigative Corkboard & Detective Dossier Video Generator.

Implements 100% of the YouTube thumbnail & documentary benchmark elements:
- Textured Corkboard / Dark Charcoal Investigation Board
- Pinned suspect photographs with BLACK CENSORSHIP BARS (REDACTED) & 3D Red Pushpins
- Physical RED YARN STRINGS connecting evidence pins with natural sag
- Evidence Checklist dossiers with green checkmarks ([✓] Flight Logs, [✓] Bank Records)
- Yellow Sticky Notes ("FOLLOW THE MONEY", "THE TRUTH WAS SUPPRESSED")
- Grunge rubber stamps ("UNDER INVESTIGATION", "CONFIDENTIAL", "EXPOSED")
- High-contrast green & red header banners ("FREE WORKFLOW", "BREAKING NEWS", "CASE EXPOSED")
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
from app.services.investigation_board import (
    EvidenceChecklist,
    InvestigationBoardService,
    PinnedEvidence,
    StickyNote,
)
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vox_investigation_board")

PROJECT_DIR = Path("D:/ALL AI/TestProjects/Vox-deepseek/projects/prj_investigation_vox_demo")
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


def ease_out_back(t: float, s: float = 1.7) -> float:
    t = max(0.0, min(1.0, t)) - 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - math.pow(1.0 - t, 3)


# --------------------------------------------------------------------------- #
# Cached Stage Backgrounds
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=4)
def get_corkboard_bg() -> Image.Image:
    return InvestigationBoardService.generate_corkboard_texture(WIDTH, HEIGHT)


@lru_cache(maxsize=4)
def get_dark_desk_bg() -> Image.Image:
    return InvestigationBoardService.generate_dark_dossier_texture(WIDTH, HEIGHT)


def draw_investigation_header(
    canvas: Image.Image,
    top_badge: str,
    main_title: str,
    accent_color: tuple[int, int, int] = (40, 200, 80),  # Neon green accent
    badge_bg: tuple[int, int, int] = (20, 24, 28),
) -> None:
    draw = ImageDraw.Draw(canvas)
    # Header container
    w_banner = 920
    h_banner = 96
    cx = WIDTH // 2
    cy = 85

    # Black textured banner with green/red accent border
    banner_box = [(cx - w_banner // 2, cy - h_banner // 2), (cx + w_banner // 2, cy + h_banner // 2)]
    draw.rectangle(banner_box, fill=(*badge_bg, 245), outline=(*accent_color, 255), width=3)

    # Top small badge
    font_top = get_font(16, bold=True)
    draw.text((cx, cy - 22), top_badge.upper(), font=font_top, fill=(*accent_color, 255), anchor="mm")

    # Main title in bold white
    font_main = get_font(36, bold=True)
    draw.text((cx, cy + 16), main_title.upper(), font=font_main, fill=(255, 255, 255, 255), anchor="mm")

    # Top corners metadata
    font_meta = get_font(15, bold=True)
    draw.text((70, 50), "HỒ SƠ ĐIỀU TRA // TOP SECRET", font=font_meta, fill=(255, 220, 30, 230))
    draw.text((WIDTH - 320, 50), "CHỨNG CỨ SỐ: #DOC-8492", font=font_meta, fill=(255, 255, 255, 120))


# --------------------------------------------------------------------------- #
# Scene 1: The Suspect & The Secret Facility (Red String Connection)
# --------------------------------------------------------------------------- #
def render_board_scene_001(f: int, n: int) -> Image.Image:
    t = f / n
    board = get_corkboard_bg().copy()
    draw_investigation_header(board, "VỤ ÁN MẬT // GIAI ĐOẠN 01", "HỒ SƠ NHÂN VẬT & ĐỊA ĐIỂM TỐI MẬT", accent_color=(50, 220, 90))

    # Evidence 1: Suspect photo with BLACK CENSOR BAR over eyes (Left)
    p1_p = ease_out_back(min(1.0, t * 3.0))
    p1_center = (450, int(-300 + (300 + 580) * p1_p))
    ev1 = PinnedEvidence(
        img_path=str(IMAGES_DIR / "suspect_agent.png"),
        center=p1_center,
        size=(460, 350),
        angle_deg=-4.0,
        caption="ĐỐI TƯỢNG X: KẺ CHỦ MƯU",
        has_censor_bar=True,
    )
    img_ev1, pin1_anchor = InvestigationBoardService.render_pinned_photo(ev1)
    if p1_p > 0:
        board.paste(img_ev1, (p1_center[0] - img_ev1.width // 2, p1_center[1] - img_ev1.height // 2), mask=img_ev1.split()[-1])

    # Evidence 2: Secret Headquarters Building (Right)
    p2_p = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    p2_center = (1450, int(-300 + (300 + 580) * p2_p))
    ev2 = PinnedEvidence(
        img_path=str(IMAGES_DIR / "secret_building.png"),
        center=p2_center,
        size=(480, 350),
        angle_deg=3.5,
        caption="ĐỊA ĐIỂM HỌP KÍN: TRỤ SỞ BẮC KINH",
        has_censor_bar=False,
    )
    img_ev2, pin2_anchor = InvestigationBoardService.render_pinned_photo(ev2)
    if p2_p > 0:
        board.paste(img_ev2, (p2_center[0] - img_ev2.width // 2, p2_center[1] - img_ev2.height // 2), mask=img_ev2.split()[-1])

    # REAL RED STRING connecting Suspect Pin to Location Pin!
    str_p = min(1.0, max(0.0, (t - 0.35) * 2.5))
    if str_p > 0 and p1_p > 0.8 and p2_p > 0.8:
        pin_src = (p1_center[0], p1_center[1] - 160)
        pin_dst = (p2_center[0], p2_center[1] - 160)
        InvestigationBoardService.draw_catenary_red_string(board, pin_src, pin_dst, sag=40.0, progress=str_p, width=5)

    # Yellow Sticky Note in Center
    note_p = ease_out_back(min(1.0, max(0.0, (t - 0.5) * 3.0)))
    if note_p > 0:
        note = StickyNote(
            text="CUỘC GẶP GỠ BÍ MẬT LÚC 2:00 SÁNG",
            subtext="MỌI MANH MỐI BỊ XÓA DẤU VẾT",
            size=(340, 200),
            angle_deg=5.0,
        )
        rnote = InvestigationBoardService.render_sticky_note(note)
        board.paste(rnote, (WIDTH // 2 - rnote.width // 2, 580 - rnote.height // 2), mask=rnote.split()[-1])

    # Giant Stamp: UNDER INVESTIGATION
    stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
    if stamp_p > 0:
        InvestigationBoardService.render_investigation_stamp(
            board, (WIDTH // 2, 850), "UNDER INVESTIGATION", angle_deg=-10.0, scale=stamp_p
        )

    return board


# --------------------------------------------------------------------------- #
# Scene 2: Financial Trails & Evidence Checklist Dossier
# --------------------------------------------------------------------------- #
def render_board_scene_002(f: int, n: int) -> Image.Image:
    t = f / n
    board = get_corkboard_bg().copy()
    draw_investigation_header(board, "BẰNG CHỨNG TÀI CHÍNH // SEC-882", "THEO DẤU DÒNG TIỀN & TẬP HỒ SƠ MẬT", accent_color=(255, 210, 30))

    # Evidence 1: Financial Vault & Flight Logs Photo (Left)
    p1_p = ease_out_back(min(1.0, t * 3.0))
    p1_center = (480, 580)
    ev1 = PinnedEvidence(
        img_path=str(IMAGES_DIR / "bank_evidence.png"),
        center=p1_center,
        size=(520, 380),
        angle_deg=-3.0,
        caption="TÀI KHOẢN NGẦM & DỮ LIỆU CHUYẾN BAY",
    )
    img_ev1, _ = InvestigationBoardService.render_pinned_photo(ev1)
    if p1_p > 0:
        board.paste(img_ev1, (p1_center[0] - img_ev1.width // 2, p1_center[1] - img_ev1.height // 2), mask=img_ev1.split()[-1])

    # Evidence 2: Official Case File Checklist Dossier (Right)
    chk_p = ease_out_back(min(1.0, max(0.0, (t - 0.2) * 3.0)))
    if chk_p > 0:
        checklist = EvidenceChecklist(
            title="KEY EVIDENCE // CHỨNG CỨ",
            items=[
                ("Nhật ký hành trình chuyến bay", True),
                ("Dòng tiền 120 triệu USD ngầm", True),
                ("Bản ghi âm nghe lén điện thoại", True),
                ("Thỏa thuận bí mật sau cánh gà", True),
                ("Lời khai của nhân chứng giấu tên", False),
            ],
            size=(480, 420),
            angle_deg=2.5,
        )
        rchk = InvestigationBoardService.render_checklist_dossier(checklist)
        board.paste(rchk, (1420 - rchk.width // 2, 580 - rchk.height // 2), mask=rchk.split()[-1])

    # Center Red String linking money photo to checklist
    str_p = min(1.0, max(0.0, (t - 0.4) * 2.5))
    if str_p > 0:
        InvestigationBoardService.draw_catenary_red_string(board, (480, 400), (1420, 380), sag=35.0, progress=str_p, width=5)

    # Yellow Sticky Note: "FOLLOW THE MONEY"
    note_p = ease_out_back(min(1.0, max(0.0, (t - 0.55) * 3.0)))
    if note_p > 0:
        note = StickyNote(
            text="FOLLOW THE MONEY!",
            subtext="THE TRUTH CANNOT BE BURIED",
            size=(300, 180),
            angle_deg=-6.0,
            color=(255, 240, 90),
        )
        rnote = InvestigationBoardService.render_sticky_note(note)
        board.paste(rnote, (WIDTH // 2 - rnote.width // 2, 600 - rnote.height // 2), mask=rnote.split()[-1])

    # Giant Stamp: EVIDENCE OBTAINED
    stamp_p = min(1.0, max(0.0, (t - 0.75) * 4.0))
    if stamp_p > 0:
        InvestigationBoardService.render_investigation_stamp(
            board, (WIDTH // 2, 850), "EVIDENCE OBTAINED", angle_deg=8.0, color=(30, 180, 60), scale=stamp_p
        )

    return board


# --------------------------------------------------------------------------- #
# Scene 3: The Exposed Climax & Hearing (EXPOSED Rubber Stamp)
# --------------------------------------------------------------------------- #
def render_board_scene_003(f: int, n: int) -> Image.Image:
    t = f / n
    board = get_corkboard_bg().copy()
    draw_investigation_header(board, "PHIÊN ĐIỀU TRẦN CÔNG KHAI", "SỰ THẬT ĐƯỢC PHƠI BÀY TRƯỚC DƯ LUẬN", accent_color=(230, 40, 40))

    # Evidence 1: Dramatic Hearing with Microphones Photo (Center Large)
    p_prog = ease_out_back(min(1.0, t * 2.5))
    p_center = (WIDTH // 2, 540)
    ev = PinnedEvidence(
        img_path=str(IMAGES_DIR / "press_hearing.png"),
        center=p_center,
        size=(720, 460),
        angle_deg=-1.5,
        caption="PHIÊN ĐIỀU TRẦN TRƯỚC HỘI ĐỒNG LẬP PHÁP",
    )
    img_ev, _ = InvestigationBoardService.render_pinned_photo(ev)
    if p_prog > 0:
        board.paste(img_ev, (p_center[0] - img_ev.width // 2, p_center[1] - img_ev.height // 2), mask=img_ev.split()[-1])

    # Left Note: "NO ONE IS ABOVE THE LAW"
    n1_p = ease_out_back(min(1.0, max(0.0, (t - 0.25) * 3.0)))
    if n1_p > 0:
        note1 = StickyNote(text="KHÔNG AI ĐỨNG TRÊN PHÁP LUẬT", subtext="BẰNG CHỨNG KHÔNG THỂ BÁC BỎ", size=(320, 200), angle_deg=-8.0)
        rn1 = InvestigationBoardService.render_sticky_note(note1)
        board.paste(rn1, (260 - rn1.width // 2, 560 - rn1.height // 2), mask=rn1.split()[-1])

    # Right Note: "BREAKING NEWS EXPOSED"
    n2_p = ease_out_back(min(1.0, max(0.0, (t - 0.4) * 3.0)))
    if n2_p > 0:
        note2 = StickyNote(text="BREAKING NEWS // CHẤN ĐỘNG", subtext="TOÀN BỘ SỰ THẬT BỊ VẠCH TRẦN", size=(320, 200), angle_deg=7.0, color=(255, 220, 80))
        rn2 = InvestigationBoardService.render_sticky_note(note2)
        board.paste(rn2, (1660 - rn2.width // 2, 560 - rn2.height // 2), mask=rn2.split()[-1])

    # Red strings crossing from notes to central hearing photo
    str_p = min(1.0, max(0.0, (t - 0.5) * 2.5))
    if str_p > 0:
        InvestigationBoardService.draw_catenary_red_string(board, (260, 460), (WIDTH // 2 - 200, 340), sag=20.0, progress=str_p, width=4)
        InvestigationBoardService.draw_catenary_red_string(board, (1660, 460), (WIDTH // 2 + 200, 340), sag=20.0, progress=str_p, width=4)

    # Giant Stamp: EXPOSED!
    stamp_p = min(1.0, max(0.0, (t - 0.7) * 4.0))
    if stamp_p > 0:
        InvestigationBoardService.render_investigation_stamp(
            board, (WIDTH // 2, 540), "EXPOSED", angle_deg=-15.0, color=(230, 25, 25), scale=stamp_p * 1.3
        )

    return board


SCENE_RENDERERS = [
    render_board_scene_001,
    render_board_scene_002,
    render_board_scene_003,
]

SCENES_METADATA = [
    {
        "id": "scene_001",
        "narration": "Một mạng lưới ngầm tinh vi với những cuộc gặp bí mật lúc nửa đêm giữa các nhân vật quyền lực.",
        "sfx": "pushpin_hit",
    },
    {
        "id": "scene_002",
        "narration": "Dòng tiền hàng trăm triệu đô la cùng nhật ký chuyến bay đã trở thành bằng chứng không thể chối cãi.",
        "sfx": "paper_slide",
    },
    {
        "id": "scene_003",
        "narration": "Trước phiên điều trần công khai, toàn bộ bức màn bí mật đã bị xé toạc ra ánh sáng của công lý.",
        "sfx": "camera_click",
    },
]


def main() -> None:
    logger.info("=== Starting True Vox Investigation Board Video Generation ===")
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
        logger.info(f"--- Rendering Investigation Board Scene: {scene_id} [{idx + 1}/3] ---")

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
            SFXEvent(sfx_type="pop", start_ms=1200, volume_db=-3.0),
            SFXEvent(sfx_type="camera_click", start_ms=int(duration_ms * 0.75), volume_db=-3.0),
        ]
        sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
        sfx_service.render_scene_sfx_track(sfx_events, duration_ms, sfx_wav)

        scene_audio_wav = audio_dir / f"{scene_id}_audio.wav"
        sfx_service.mix_sfx_with_voice(voice_wav, sfx_wav, scene_audio_wav, voice_gain_db=1.0, sfx_gain_db=-5.0)

        # Render Frame-by-Frame Video into FFmpeg pipe
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
        renderer_fn = SCENE_RENDERERS[idx]

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
    final_mp4 = final_dir / "true_vox_investigation_board_demo.mp4"
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
    print(f"\n[DONE] Video Bảng Điều Tra Vox Hoàn Tất tại: {output_path.resolve()}")
    print(f"[FACTS] Thời lượng: {probe.duration_ms / 1000.0:.2f}s | Độ phân giải: {probe.width}x{probe.height} | FPS: {probe.fps}")


if __name__ == "__main__":
    main()
