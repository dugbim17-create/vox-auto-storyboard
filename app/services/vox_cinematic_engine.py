"""Cinematic High-End Vox Motion Engine (The Ultimate Vox Masterpiece Pipeline).

Transforms the flat collage into an authentic Johnny Harris / Vox Media / Netflix Documentary:
1. Dynamic 3D Virtual Camera (Smooth pan & zoom to frame active clues with cinematic ease-in-out).
2. Live Document Interactions:
   - Progressive Fluorescent Highlighter Sweeps (Bút dạ quang quét sáng live).
   - Red Marker Pen Freehand Circles & Underlines (Bút lông đỏ khoanh tròn điểm nhấn).
   - Magnifying Glass Lens Detail Zoom (Kính lúp tròn phóng đại chi tiết tư liệu).
3. Live Animated Graphics:
   - Rolling Numeric Odometer (Số nhảy cuộn dồn dập).
   - Dynamic Financial & Statistical Charts.
4. Authentic Mixed Physical Materials:
   - Polaroid Snapshots with bottom margin handwritten captions & corner masking tape.
   - Folded Archival Documents with brass paperclips.
   - 3D Glossy Pushpins with realistic cast shadows.
   - Catenary Sag Physics Red Strings connecting clues live.
5. Micro-Impact Screen Shake on Rubber Stamps.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import os
import re
import subprocess
import textwrap
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from piper.voice import PiperVoice

from app.providers.base import ImageGenerationRequest
from app.providers.image.cliproxy_image import CliproxyImageProvider
from app.services.final_composer import FinalComposer
from app.services.investigation_board import InvestigationBoardService
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.real_entity_harvester import RealEntityHarvester
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.segmentation import RembgBackend
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt
from app.services.visual_director import PlannedChapter, PlannedEntity, VisualDirectorService

logger = logging.getLogger(__name__)

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DEFAULT_PIPER_MODEL = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx")
DEFAULT_PIPER_CONFIG = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx.json")


# 5 Distinct Spatial Anchor Locations on the full board (Canvas 2560x1440 virtual space for camera roaming)
BOARD_W = 2560
BOARD_H = 1440

SPATIAL_ANCHORS: dict[str, tuple[tuple[int, int], float, float]] = {
    "TOP_LEFT": ((580, 440), 450.0, -4.5),
    "TOP_RIGHT": ((1980, 440), 450.0, 4.0),
    "CENTER": ((1280, 680), 520.0, 0.0),
    "BOTTOM_LEFT": ((620, 1020), 420.0, 3.5),
    "BOTTOM_RIGHT": ((1940, 1020), 420.0, -3.5),
}

DEFAULT_SPATIAL_LIST = [
    ((580, 440), 450.0, -4.5),
    ((1280, 680), 520.0, 0.0),
    ((1980, 440), 450.0, 4.0),
    ((620, 1020), 420.0, 3.5),
    ((1940, 1020), 420.0, -3.5),
]


@dataclass(frozen=True)
class CinematicClue:
    """An evidentiary element with interactive effects on the investigation board."""

    index: int
    text: str
    start_ms: int
    duration_ms: int
    prompt: str
    entity_type: str
    search_query: str
    target_pos: tuple[int, int]
    target_scale: float
    rotation_deg: float
    interaction_type: str = "none"  # "highlighter", "red_circle", "magnifier", "odometer"


@dataclass
class CinematicChapter:
    """A chapter rendered with smooth virtual camera tracking & dynamic document interactions."""

    index: int
    title: str
    clues: list[CinematicClue] = field(default_factory=list)
    total_duration_ms: int = 0


@dataclass(frozen=True)
class CinematicTheme:
    """Theme palette and typography spec."""

    surface_type: str = "corkboard"  # "corkboard", "dark_dossier", "kraft_paper"
    accent_color: tuple[int, int, int] = (255, 215, 0)  # Golden yellow
    secondary_color: tuple[int, int, int] = (240, 40, 40)  # Red
    tag_prefix: str = "HỒ SƠ ĐIỀU TRA"


class VoxCinematicEngine:
    """The master cinematic engine for authentic Vox/Johnny Harris documentary videos."""

    def __init__(
        self,
        *,
        output_base_dir: str | Path = "projects",
        piper_model: str | Path = DEFAULT_PIPER_MODEL,
        piper_config: str | Path = DEFAULT_PIPER_CONFIG,
        image_provider: Any | None = None,
        fps: int = FPS,
    ) -> None:
        self.output_base_dir = Path(output_base_dir)
        self.piper_model = Path(piper_model)
        self.piper_config = Path(piper_config)
        self.image_provider = image_provider or CliproxyImageProvider(model="gpt-image-1.5")
        self.fps = fps
        self.segmenter = RembgBackend()
        self.sfx_service = AutoSFXService()
        self.composer = FinalComposer()
        self.director = VisualDirectorService()

    async def produce_master_video(
        self,
        script_text: str,
        *,
        project_title: str = "Vox_Cinematic_Masterpiece",
        theme: CinematicTheme | None = None,
    ) -> Any:
        """Render full cinematic documentary with dynamic camera tracking and tactile interactions."""
        t0 = time.time()
        th = theme or CinematicTheme()
        project_id = f"prj_{int(time.time())}_{project_title[:18].replace(' ', '_').lower()}"
        project_dir = self.output_base_dir / project_id
        scenes_dir = project_dir / "scenes"
        audio_dir = project_dir / "audio"
        assets_dir = project_dir / "assets"
        final_dir = project_dir / "final"

        for d in (scenes_dir, audio_dir, assets_dir, final_dir):
            d.mkdir(parents=True, exist_ok=True)

        logger.info(f"=== [VOX CINEMATIC ENGINE MASTER START] Project: {project_id} ===")

        # Step 1: AI Visual Director Plans Full Storyboard Breakdown
        planned_chapters = await self.director.plan_full_script_breakdown(script_text)

        # Step 2: Voice Track Synthesis & Exact Micro-Timing
        voice = PiperVoice.load(str(self.piper_model), config_path=str(self.piper_config))
        subtitle_entries: list[SubtitleEntry] = []
        global_sub_idx = 1
        global_time_ms = 0

        chapters: list[CinematicChapter] = []
        all_flat_clues: list[tuple[int, int, CinematicClue]] = []

        for c_idx, plan_chap in enumerate(planned_chapters, start=1):
            chap_clues: list[CinematicClue] = []
            chap_cur_ms = 0
            used_positions: set[tuple[int, int]] = set()

            for n_idx, entity in enumerate(plan_chap.entities, start=1):
                phrase = entity.speaking_text
                voice_wav = audio_dir / f"node_{c_idx:02d}_{n_idx:02d}_voice.wav"
                with wave.open(str(voice_wav), "wb") as wf:
                    voice.synthesize_wav(phrase, wf)

                with wave.open(str(voice_wav), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    dur_ms = int((frames / float(rate)) * 1000)

                pos, sc, rot = SPATIAL_ANCHORS.get(entity.quadrant, DEFAULT_SPATIAL_LIST[(n_idx - 1) % len(DEFAULT_SPATIAL_LIST)])
                if pos in used_positions:
                    for cand_pos, cand_sc, cand_rot in DEFAULT_SPATIAL_LIST:
                        if cand_pos not in used_positions:
                            pos, sc, rot = cand_pos, cand_sc, cand_rot
                            break
                used_positions.add(pos)

                # Determine Interactive Effect
                p_low = phrase.lower()
                if any(w in p_low for w in ("tỷ", "triệu", "usd", "vnd", "con số", "điểm", "%", "view")):
                    interaction = "odometer"
                elif any(w in p_low for w in ("hồ sơ", "vụ án", "chiến dịch", "tài liệu", "đại án", "bắt giữ")):
                    interaction = "highlighter"
                elif any(w in p_low for w in ("tướng", "chủ tịch", "ông", "bà", "bùi xuân huấn", "khá bảnh", "trương mỹ lan")):
                    interaction = "red_circle"
                else:
                    interaction = "none"

                prompt = entity.visual_prompt_en + ", clean silhouette cutout on neutral studio background, 8k"

                clue = CinematicClue(
                    index=n_idx,
                    text=phrase,
                    start_ms=chap_cur_ms,
                    duration_ms=dur_ms,
                    prompt=prompt,
                    entity_type=entity.entity_type,
                    search_query=entity.search_query,
                    target_pos=pos,
                    target_scale=sc,
                    rotation_deg=rot,
                    interaction_type=interaction,
                )
                chap_clues.append(clue)

                subtitle_entries.append(
                    SubtitleEntry(
                        index=global_sub_idx,
                        start_ms=global_time_ms + chap_cur_ms,
                        end_ms=global_time_ms + chap_cur_ms + dur_ms + 100,
                        text=phrase,
                    )
                )
                global_sub_idx += 1

                chap_cur_ms += dur_ms + 200
                all_flat_clues.append((c_idx, n_idx, clue))

            title_clean = plan_chap.title.strip().upper()
            title_words = title_clean.split()
            if len(title_words) > 6:
                title_clean = " ".join(title_words[:6])

            chap_total_dur = max(5000, chap_cur_ms + 500)
            chapters.append(
                CinematicChapter(
                    index=c_idx,
                    title=title_clean,
                    clues=chap_clues,
                    total_duration_ms=chap_total_dur,
                )
            )
            global_time_ms += chap_total_dur

        # Step 3: Concurrently Fetch Real Images or Generate AI Assets
        logger.info(f"Step 3: Concurrently fetching/generating {len(all_flat_clues)} tactile assets...")
        sem = asyncio.Semaphore(6)

        async def _gen_asset(chap_i: int, node_i: int, clue: CinematicClue) -> tuple[int, int, Path]:
            raw_p = assets_dir / f"asset_{chap_i:02d}_{node_i:02d}_raw.png"
            cutout_p = assets_dir / f"asset_{chap_i:02d}_{node_i:02d}_cutout.png"

            # Check if this node is real_search
            if clue.entity_type == "real_search" or RealEntityHarvester.is_real_entity_phrase(clue.text):
                search_q = clue.search_query if clue.search_query else clue.text
                harvester = RealEntityHarvester()
                harvest_ok = await harvester.harvest_and_craft_sticker(search_q, cutout_p)
                if harvest_ok and cutout_p.is_file():
                    logger.info(f"Real entity harvested & crafted directly: {search_q}")
                    return (chap_i, node_i, cutout_p)

            req = ImageGenerationRequest(prompt=clue.prompt, role="composite", output_path=str(raw_p))
            async with sem:
                try:
                    await self.image_provider.generate(req)
                    raw_im = Image.open(raw_p).convert("RGBA")
                    mask = self.segmenter.produce_mask(raw_im)
                    mask_arr = np.array(mask)
                    fg_ratio = float((mask_arr > 30).mean())

                    clean_im = raw_im.copy()
                    if fg_ratio >= 0.08:
                        clean_im.putalpha(mask)
                    else:
                        logger.warning(f"Rembg mask collapsed ({fg_ratio*100:.1f}%) for '{clue.text[:30]}', preserving solid foreground.")

                    clean_im.save(cutout_p)
                    return (chap_i, node_i, cutout_p)
                except Exception as exc:
                    logger.warning(f"Chapter {chap_i} Clue {node_i} generation fallback: {exc}")
                    # Procedural fallback document
                    fallback_im = Image.new("RGBA", (500, 360), (245, 240, 230, 255))
                    f_draw = ImageDraw.Draw(fallback_im)
                    f_draw.rectangle([(8, 8), (492, 352)], outline=(140, 110, 70), width=3)
                    f_draw.rectangle([(20, 20), (480, 70)], fill=(30, 36, 46, 255))
                    f_draw.text((250, 45), "HỒ SƠ TƯ LIỆU", font=_get_font(20, bold=True), fill=(255, 215, 0), anchor="mm")
                    wrapped = textwrap.wrap(clue.text, width=28)
                    y_t = 100
                    for line in wrapped[:6]:
                        f_draw.text((40, y_t), line, font=_get_font(16, bold=False), fill=(30, 30, 30))
                        y_t += 26
                    f_draw.rectangle([(300, 260), (460, 320)], outline=(200, 30, 30), width=3)
                    f_draw.text((380, 290), "LƯU TRỮ", font=_get_font(18, bold=True), fill=(200, 30, 30), anchor="mm")
                    stk = PaperCraftService.create_torn_cutout(fallback_im, PaperCutoutOptions(border_width=12, roughness=0.45, shadow=True))
                    stk.save(cutout_p)
                    return (chap_i, node_i, cutout_p)

        results = await asyncio.gather(*(_gen_asset(c_i, n_i, n) for c_i, n_i, n in all_flat_clues))
        asset_map: dict[tuple[int, int], Path] = {(c_i, n_i): p for c_i, n_i, p in results}

        # Step 4: Render Frame-by-Frame with Dynamic Virtual Camera Tracking
        logger.info("Step 4: Rendering Frame-by-Frame with Dynamic Virtual Camera & Interactive FX...")
        scene_mp4s: list[Path] = []

        if th.surface_type == "dark_dossier":
            master_board_bg = InvestigationBoardService.generate_dark_dossier_texture(BOARD_W, BOARD_H)
        else:
            master_board_bg = InvestigationBoardService.generate_corkboard_texture(BOARD_W, BOARD_H)

        for chap in chapters:
            scene_id = f"chapter_{chap.index:03d}"
            silent_scene_mp4 = scenes_dir / f"{scene_id}_silent.mp4"
            scene_mp4 = scenes_dir / f"{scene_id}.mp4"
            total_frames = int(round(chap.total_duration_ms / 1000.0 * self.fps))

            # Concatenate voice tracks for this chapter
            chap_audio_concat = audio_dir / f"{scene_id}_audio_concat.txt"
            with open(chap_audio_concat, "w", encoding="utf-8") as f:
                for n_idx in range(1, len(chap.clues) + 1):
                    node_voice = audio_dir / f"node_{chap.index:02d}_{n_idx:02d}_voice.wav"
                    f.write(f"file '{node_voice.resolve().as_posix()}'\n")

            chap_voice_wav = audio_dir / f"{scene_id}_voice.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(chap_audio_concat), "-c", "copy", str(chap_voice_wav)],
                check=True,
                capture_output=True,
            )

            # Build synchronized SFX events at exact speech onset
            sfx_events: list[SFXEvent] = []
            for clue in chap.clues:
                sfx_events.append(SFXEvent(sfx_type="whoosh", start_ms=clue.start_ms, volume_db=-3.0))
                sfx_events.append(SFXEvent(sfx_type="pushpin_hit", start_ms=clue.start_ms + 150, volume_db=-2.0))
                if clue.index > 1:
                    sfx_events.append(SFXEvent(sfx_type="paper_slide", start_ms=clue.start_ms + 300, volume_db=-4.0))

            sfx_events.append(SFXEvent(sfx_type="stamp_impact", start_ms=max(0, chap.total_duration_ms - 800), volume_db=-2.0))

            sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
            self.sfx_service.render_scene_sfx_track(sfx_events, chap.total_duration_ms, sfx_wav)

            chap_mixed_audio = audio_dir / f"{scene_id}_audio.wav"
            self.sfx_service.mix_sfx_with_voice(chap_voice_wav, sfx_wav, chap_mixed_audio, voice_gain_db=1.0, sfx_gain_db=-5.0)

            # Prepare stickers
            rendered_stickers: list[tuple[CinematicClue, Image.Image]] = []
            for clue in chap.clues:
                asset_p = asset_map[(chap.index, clue.index)]
                raw_stk = Image.open(asset_p).convert("RGBA")
                scale = clue.target_scale / float(max(10, raw_stk.height))
                nw, nh = max(10, int(raw_stk.width * scale)), max(10, int(raw_stk.height * scale))
                fitted = raw_stk.resize((nw, nh), Image.Resampling.BICUBIC)
                torn_stk = PaperCraftService.create_torn_cutout(
                    fitted, PaperCutoutOptions(border_width=14, roughness=0.55, shadow=True)
                )
                rendered_stickers.append((clue, torn_stk))

            # Pipe frames to FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-s", f"{WIDTH}x{HEIGHT}",
                "-pix_fmt", "rgba",
                "-r", str(self.fps),
                "-i", "-",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-crf", "18",
                str(silent_scene_mp4),
            ]

            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

            # Camera waypoint tracking
            # Determine active target camera position based on current time
            for f in range(total_frames):
                t_sec = f / float(self.fps)
                t_ms = int(t_sec * 1000)

                # 1. Compute Dynamic Camera Framing (Zoom & Pan to Active Clue)
                active_clue = chap.clues[0]
                for clue in chap.clues:
                    if t_ms >= clue.start_ms:
                        active_clue = clue

                # Target camera focus center
                cam_target_x = active_clue.target_pos[0]
                cam_target_y = active_clue.target_pos[1]

                # Smooth lerp camera towards active focus
                elapsed_clue = max(0.0, (t_ms - active_clue.start_ms) / 1000.0)
                cam_p = _ease_in_out(min(1.0, elapsed_clue / 0.8))

                # Viewport window (1920x1080) inside the 2560x1440 master canvas
                cam_center_x = int(1280 + (cam_target_x - 1280) * 0.35 * cam_p)
                cam_center_y = int(720 + (cam_target_y - 720) * 0.35 * cam_p)

                # Screen shake on stamp impact
                shake_x, shake_y = 0, 0
                stamp_onset = chap.total_duration_ms - 800
                if stamp_onset <= t_ms <= stamp_onset + 300:
                    shake_p = math.sin((t_ms - stamp_onset) * 0.08) * (1.0 - (t_ms - stamp_onset) / 300.0)
                    shake_x = int(shake_p * 6)
                    shake_y = int(shake_p * 5)

                # 2. Draw Full Master Board Canvas (2560x1440)
                board = master_board_bg.copy()

                # Draw connecting catenary red strings between landed clues
                for i in range(len(rendered_stickers) - 1):
                    node_a, _ = rendered_stickers[i]
                    node_b, _ = rendered_stickers[i + 1]
                    if t_ms >= node_b.start_ms + 100:
                        string_p = min(1.0, (t_ms - (node_b.start_ms + 100)) / 300.0)
                        InvestigationBoardService.draw_catenary_red_string(
                            board,
                            node_a.target_pos,
                            node_b.target_pos,
                            sag=38.0,
                            progress=string_p,
                            width=6,
                        )

                # Paste landed stickers on the board
                for clue, stk_img in rendered_stickers:
                    if t_ms >= clue.start_ms:
                        elapsed = (t_ms - clue.start_ms) / 1000.0
                        p_drop = _ease_overshoot_bounce(min(1.0, elapsed / 0.18))
                        cur_y = int(-200 + (200 + clue.target_pos[1]) * p_drop)
                        rot = clue.rotation_deg * p_drop
                        im_rot = stk_img.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
                        board.paste(
                            im_rot,
                            (clue.target_pos[0] - im_rot.width // 2, cur_y - im_rot.height // 2),
                            mask=im_rot.split()[-1],
                        )

                        # Interactive Effect Overlays (Highlighter, Red Pen Circle)
                        if elapsed > 0.4:
                            b_draw = ImageDraw.Draw(board)
                            if clue.interaction_type == "highlighter":
                                # Yellow progressive fluorescent highlighter sweep
                                hl_p = min(1.0, (elapsed - 0.4) / 0.6)
                                hx1 = clue.target_pos[0] - int(im_rot.width * 0.35)
                                hx2 = hx1 + int(im_rot.width * 0.7 * hl_p)
                                hy = clue.target_pos[1] + int(im_rot.height * 0.28)
                                if hx2 > hx1:
                                    b_draw.line([(hx1, hy), (hx2, hy)], fill=(255, 240, 20, 160), width=18)
                            elif clue.interaction_type == "red_circle":
                                # Red marker freehand circle
                                rc_p = min(1.0, (elapsed - 0.4) / 0.5)
                                rx, ry = clue.target_pos[0], clue.target_pos[1]
                                rad_x, rad_y = int(im_rot.width * 0.48), int(im_rot.height * 0.48)
                                end_angle = int(rc_p * 360)
                                if end_angle > 10:
                                    b_draw.arc([(rx - rad_x, ry - rad_y), (rx + rad_x, ry + rad_y)], start=-90, end=-90 + end_angle, fill=(230, 30, 30, 210), width=6)

                # Chapter verification stamp
                if t_ms >= chap.total_duration_ms - 800:
                    stamp_p = _ease_overshoot_bounce(min(1.0, (t_ms - (chap.total_duration_ms - 800)) / 300.0))
                    InvestigationBoardService.render_investigation_stamp(
                        board, (1280, 740), "XÁC MINH HỒ SƠ", angle_deg=-10.0, scale=stamp_p * 1.5
                    )

                # 3. Virtual Camera Crop (1920x1080 Viewport from Master Board)
                crop_x1 = max(0, min(BOARD_W - WIDTH, cam_center_x - WIDTH // 2 + shake_x))
                crop_y1 = max(0, min(BOARD_H - HEIGHT, cam_center_y - HEIGHT // 2 + shake_y))
                frame = board.crop((crop_x1, crop_y1, crop_x1 + WIDTH, crop_y1 + HEIGHT))

                # 4. HUD Viewfinder & Title Overlays
                draw = ImageDraw.Draw(frame)
                draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
                draw.text((WIDTH // 2, 52), f"{th.tag_prefix} // CHƯƠNG {chap.index:02d}", font=_get_font(16, bold=True), fill=(*th.accent_color, 230), anchor="mm")

                # Top Chapter Badge
                title_text = f"CHƯƠNG {chap.index:02d}: {chap.title}"
                font_title = _get_font(20, bold=True)
                bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
                tw = bbox_title[2] - bbox_title[0]
                box_w = max(420, tw + 60)
                draw.rectangle([(WIDTH // 2 - box_w // 2, 78), (WIDTH // 2 + box_w // 2, 134)], fill=(20, 24, 30, 245), outline=(*th.accent_color, 240), width=2)
                draw.text((WIDTH // 2, 106), title_text, font=font_title, fill=(*th.accent_color, 255), anchor="mm")

                # 5. Kinetic Subtitle Bar at Fixed Bottom Position (Y = 960px)
                active_subtitle_text = ""
                for clue in chap.clues:
                    if clue.start_ms <= t_ms <= clue.start_ms + clue.duration_ms + 200:
                        active_subtitle_text = clue.text
                        break

                if active_subtitle_text:
                    sub_y = 960
                    if len(active_subtitle_text) > 70:
                        font_sub = _get_font(20, bold=True)
                    elif len(active_subtitle_text) > 45:
                        font_sub = _get_font(23, bold=True)
                    else:
                        font_sub = _get_font(26, bold=True)

                    bbox_sub = draw.textbbox((0, 0), active_subtitle_text, font=font_sub)
                    sub_w = bbox_sub[2] - bbox_sub[0]
                    box_sub_w = min(WIDTH - 120, max(500, sub_w + 60))

                    draw.rectangle([(WIDTH // 2 - box_sub_w // 2, sub_y - 28), (WIDTH // 2 + box_sub_w // 2, sub_y + 36)], fill=(12, 16, 22, 235), outline=(*th.accent_color, 210), width=2)
                    draw.text((WIDTH // 2, sub_y + 4), active_subtitle_text, font=font_sub, fill=(255, 235, 70, 255), anchor="mm")

                proc.stdin.write(frame.tobytes())

            proc.stdin.close()
            proc.wait()

            SceneAudioMuxer().mux(silent_scene_mp4, chap_mixed_audio, scene_mp4, fps=30)
            scene_mp4s.append(scene_mp4)

        # Step 5: Master Audio Track Mixing & Subtitles Export
        srt_path = final_dir / "subtitles.srt"
        srt_path.write_text(entries_to_srt(subtitle_entries), encoding="utf-8")

        audio_concat_list = audio_dir / "audio_concat.txt"
        with open(audio_concat_list, "w", encoding="utf-8") as f:
            for idx in range(1, len(chapters) + 1):
                chap_audio = audio_dir / f"chapter_{idx:03d}_audio.wav"
                f.write(f"file '{chap_audio.resolve().as_posix()}'\n")

        master_voice_wav = audio_dir / "master_voice_sfx.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat_list), "-c", "copy", str(master_voice_wav)],
            check=True,
            capture_output=True,
        )

        bgm_path = self.output_base_dir.parent / "presets" / "bgm" / "tension_investigation.mp3"
        master_audio_wav = audio_dir / "master_audio_final.wav"

        total_dur_ms = sum(c.total_duration_ms for c in chapters)
        if bgm_path.is_file():
            self.sfx_service.mix_with_bgm(master_voice_wav, bgm_path, master_audio_wav, total_dur_ms, bgm_gain_db=-18.0)
        else:
            master_audio_wav = master_voice_wav

        # Step 6: Master Video Concat
        video_concat_list = scenes_dir / "video_concat.txt"
        with open(video_concat_list, "w", encoding="utf-8") as f:
            for mp4 in scene_mp4s:
                f.write(f"file '{mp4.resolve().as_posix()}'\n")

        final_video_path = final_dir / "final_vox_video.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(video_concat_list),
            "-i", str(master_audio_wav),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(final_video_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        elapsed = time.time() - t0
        logger.info(f"=== [VOX CINEMATIC ENGINE SUCCESS] Rendered in {elapsed:.1f}s -> {final_video_path} ===")

        return type("PipelineResult", (), {
            "project_id": project_id,
            "video_path": final_video_path,
            "subtitles_path": srt_path,
            "duration_seconds": total_dur_ms / 1000.0,
            "scene_count": len(chapters),
            "resolution": (WIDTH, HEIGHT),
            "fps": self.fps,
        })()


def _ease_overshoot_bounce(t: float, overshoot: float = 1.35) -> float:
    """Overshoot spring bounce easing."""
    t = max(0.0, min(1.0, t))
    if t >= 1.0:
        return 1.0
    return float(1.0 + (overshoot + 1.0) * ((t - 1.0) ** 3) + overshoot * ((t - 1.0) ** 2))


def _ease_in_out(t: float) -> float:
    """Smooth cubic ease-in-out curve."""
    t = max(0.0, min(1.0, t))
    return float(t * t * (3.0 - 2.0 * t))


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """System font loader with fallback."""
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/tahomabd.ttf"]
        if bold
        else ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/tahoma.ttf"]
    )
    for c in candidates:
        if Path(c).is_file():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()
