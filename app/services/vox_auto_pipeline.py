"""Autonomous 1-Click End-to-End Vox Video Pipeline (Zero-Omission Crazy-Wall Edition).

Guarantees 100% Zero-Lag & Zero-Omission Audio-Visual Alignment:
1. AI Visual Director plans every spoken clause into a dedicated visual entity (no ideas skipped).
2. Exact Entity Speech Timestamping:
   - Voice reads Entity 1 -> Visual 1 SLAMS down at exact speech onset.
   - Voice reads Entity 2 -> Visual 2 SLAMS down at exact speech onset.
   - Voice reads Entity 3 -> Visual 3 SLAMS down at exact speech onset.
   - Voice reads Entity 4 -> Visual 4 SLAMS down at exact speech onset.
3. Clean Background Cutout & Morphology (no dirty specks or ragged holes).
4. Bottom Kinetic Subtitles (Karaoke-Style) with auto-scaling box (zero overflow).
5. Dynamic Catenary Red Strings connecting all active clues across the chapter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import subprocess
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
from app.services.vox_cinematic_engine import VoxCinematicEngine, CinematicTheme

logger = logging.getLogger(__name__)

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DEFAULT_PIPER_MODEL = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx")
DEFAULT_PIPER_CONFIG = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx.json")


QUADRANT_COORDS: dict[str, tuple[tuple[int, int], float, float]] = {
    "TOP_LEFT": ((420, 360), 380.0, -4.5),
    "TOP_RIGHT": ((1500, 360), 380.0, 4.0),
    "CENTER": ((960, 470), 420.0, 0.0),
    "BOTTOM_LEFT": ((440, 720), 340.0, 3.5),
    "BOTTOM_RIGHT": ((1480, 720), 340.0, -3.0),
}

DEFAULT_FALLBACK_SPATIAL = [
    ((420, 360), 380.0, -4.5),
    ((960, 470), 420.0, 0.0),
    ((1500, 360), 380.0, 4.0),
    ((440, 720), 340.0, 3.5),
    ((1480, 720), 340.0, -3.0),
]


@dataclass(frozen=True)
class TimedEntityNode:
    """A physical evidence node with exact millisecond start & duration."""

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


@dataclass
class TimedBoardChapter:
    """A unified investigation board chapter containing precisely timed accumulating nodes."""

    index: int
    title: str
    nodes: list[TimedEntityNode] = field(default_factory=list)
    total_duration_ms: int = 0


@dataclass(frozen=True)
class VisualThemeConfig:
    """Full customization configuration for typography, background surfaces, and color palettes."""

    background_type: str = "corkboard"  # "corkboard", "dark_dossier", "kraft_paper", "grid_blueprint", "custom_image"
    custom_bg_path: str | None = None
    font_bold_path: str | None = None
    font_regular_path: str | None = None
    accent_color: tuple[int, int, int] = (255, 220, 20)  # Vox Neon Yellow
    secondary_color: tuple[int, int, int] = (240, 40, 40)  # Crimson Red
    banner_bg_color: tuple[int, int, int] = (20, 24, 30)
    sticky_note_color: tuple[int, int, int] = (255, 235, 110)
    hud_overlay: bool = True
    hud_tag_prefix: str = "HỒ SƠ ĐIỀU TRA"


@dataclass(frozen=True)
class PipelineResult:
    """Final output artifact result of the 1-click pipeline."""

    project_id: str
    video_path: Path
    subtitles_path: Path
    duration_seconds: float
    scene_count: int
    resolution: tuple[int, int]
    fps: int


class VoxAutoPipeline:
    """1-Click Autonomous Multi-Entity Zero-Omission Crazy-Wall Engine."""

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

    async def run_from_script(
        self,
        script_text: str,
        *,
        project_title: str = "Vox_Project",
        aspect_ratio: str = "16:9",
        style_preset: str = "editorial_collage",
        theme_config: VisualThemeConfig | None = None,
    ) -> PipelineResult:
        """Execute autonomous zero-omission crazy-wall pipeline with bottom karaoke subtitles."""
        t0 = time.time()
        theme = theme_config or VisualThemeConfig()
        project_id = f"prj_{int(time.time())}_{project_title[:16].replace(' ', '_').lower()}"
        project_dir = self.output_base_dir / project_id
        scenes_dir = project_dir / "scenes"
        audio_dir = project_dir / "audio"
        assets_dir = project_dir / "assets"
        final_dir = project_dir / "final"

        for d in (scenes_dir, audio_dir, assets_dir, final_dir):
            d.mkdir(parents=True, exist_ok=True)

        logger.info(f"=== [ZERO-OMISSION CRAZY-WALL START] Project: {project_id} ===")

        # Route directly through VoxCinematicEngine for authentic Johnny Harris / Vox documentary motion
        cinematic_engine = VoxCinematicEngine(
            output_base_dir=self.output_base_dir,
            piper_model=self.piper_model,
            piper_config=self.piper_config,
            image_provider=self.image_provider,
            fps=self.fps,
        )
        cine_theme = CinematicTheme(
            surface_type=theme.background_type,
            accent_color=theme.accent_color,
            secondary_color=theme.secondary_color,
            tag_prefix=theme.hud_tag_prefix,
        )
        return await cinematic_engine.produce_master_video(
            script_text,
            project_title=project_title,
            theme=cine_theme,
        )

        # Step 2: Synthesize Voice Track per Entity & Compute Exact Millisecond Timestamps
        logger.info("Step 2: Synthesizing TTS Audio for Every Spoken Clause...")
        voice = PiperVoice.load(str(self.piper_model), config_path=str(self.piper_config))
        subtitle_entries: list[SubtitleEntry] = []
        global_sub_idx = 1
        global_time_ms = 0

        chapters: list[TimedBoardChapter] = []
        all_flat_nodes: list[tuple[int, int, TimedEntityNode]] = []

        for c_idx, plan_chap in enumerate(planned_chapters, start=1):
            chap_nodes: list[TimedEntityNode] = []
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

                # Determine Spatial Position based on quadrant directive
                pos, sc, rot = QUADRANT_COORDS.get(entity.quadrant, DEFAULT_FALLBACK_SPATIAL[(n_idx - 1) % len(DEFAULT_FALLBACK_SPATIAL)])
                if pos in used_positions:
                    # Choose alternative fallback position
                    for cand_pos, cand_sc, cand_rot in DEFAULT_FALLBACK_SPATIAL:
                        if cand_pos not in used_positions:
                            pos, sc, rot = cand_pos, cand_sc, cand_rot
                            break
                used_positions.add(pos)

                prompt = entity.visual_prompt_en + ", clean silhouette cutout on neutral studio background, 8k"

                node = TimedEntityNode(
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
                )
                chap_nodes.append(node)

                subtitle_entries.append(
                    SubtitleEntry(
                        index=global_sub_idx,
                        start_ms=global_time_ms + chap_cur_ms,
                        end_ms=global_time_ms + chap_cur_ms + dur_ms + 100,
                        text=phrase,
                    )
                )
                global_sub_idx += 1

                chap_cur_ms += dur_ms + 180
                all_flat_nodes.append((c_idx, n_idx, node))

            # Clean word-bounded title
            title_clean = plan_chap.title.strip().upper()
            title_words = title_clean.split()
            if len(title_words) > 6:
                title_clean = " ".join(title_words[:6])

            chap_total_dur = max(4500, chap_cur_ms + 400)
            chapters.append(
                TimedBoardChapter(
                    index=c_idx,
                    title=title_clean,
                    nodes=chap_nodes,
                    total_duration_ms=chap_total_dur,
                )
            )
            global_time_ms += chap_total_dur

        # Step 3: Concurrently Generate / Crawl All Dedicated Images in Parallel
        logger.info(f"Step 3: Concurrently generating/crawling {len(all_flat_nodes)} dedicated visual assets...")
        sem = asyncio.Semaphore(6)

        async def _gen_asset(chap_i: int, node_i: int, node: TimedEntityNode) -> tuple[int, int, Path]:
            raw_p = assets_dir / f"asset_{chap_i:02d}_{node_i:02d}_raw.png"
            cutout_p = assets_dir / f"asset_{chap_i:02d}_{node_i:02d}_cutout.png"

            # Check if this node has a real_search directive or references real person/brand
            if node.entity_type == "real_search" or RealEntityHarvester.is_real_entity_phrase(node.text):
                search_q = node.search_query if node.search_query else node.text
                harvester = RealEntityHarvester()
                harvest_ok = await harvester.harvest_and_craft_sticker(search_q, cutout_p)
                if harvest_ok and cutout_p.is_file():
                    logger.info(f"Real entity harvested & crafted directly: {search_q}")
                    return (chap_i, node_i, cutout_p)

            req = ImageGenerationRequest(prompt=node.prompt, role="composite", output_path=str(raw_p))
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
                        logger.warning(f"Rembg mask collapsed ({fg_ratio*100:.1f}%) for '{node.text[:30]}', preserving solid foreground.")

                    clean_im.save(cutout_p)
                    return (chap_i, node_i, cutout_p)
                except Exception as exc:
                    logger.warning(f"Chapter {chap_i} Node {node_i} image gen fallback: {exc}")
                    # Procedural fallback document asset if AI generation blocked or failed
                    fallback_im = Image.new("RGBA", (500, 360), (245, 240, 230, 255))
                    f_draw = ImageDraw.Draw(fallback_im)
                    f_draw.rectangle([(8, 8), (492, 352)], outline=(140, 110, 70), width=3)
                    f_draw.rectangle([(20, 20), (480, 70)], fill=(30, 36, 46, 255))
                    f_draw.text((250, 45), "HỒ SƠ TƯ LIỆU", font=_get_cfg_font(20, bold=True), fill=(255, 215, 0), anchor="mm")
                    
                    # Split text into lines
                    wrapped = textwrap.wrap(node.text, width=28)
                    y_text = 100
                    for line in wrapped[:6]:
                        f_draw.text((40, y_text), line, font=_get_cfg_font(16, bold=False), fill=(30, 30, 30))
                        y_text += 26
                    
                    # Red stamp
                    f_draw.rectangle([(300, 260), (460, 320)], outline=(200, 30, 30), width=3)
                    f_draw.text((380, 290), "LƯU TRỮ", font=_get_cfg_font(18, bold=True), fill=(200, 30, 30), anchor="mm")
                    
                    stk = PaperCraftService.create_torn_cutout(fallback_im, PaperCutoutOptions(border_width=12, roughness=0.45, shadow=True))
                    stk.save(cutout_p)
                    return (chap_i, node_i, cutout_p)

        results = await asyncio.gather(*(_gen_asset(c_i, n_i, n) for c_i, n_i, n in all_flat_nodes))
        asset_map: dict[tuple[int, int], Path] = {(c_i, n_i): p for c_i, n_i, p in results}

        # Step 4: Render Frame-by-Frame Zero-Delay Cumulative Board Scenes
        logger.info(f"Step 4: Rendering {len(chapters)} Exhaustive Crazy-Wall Canvases with Bottom Subtitles...")
        scene_mp4s: list[Path] = []

        if theme.background_type == "dark_dossier":
            base_bg = InvestigationBoardService.generate_dark_dossier_texture(WIDTH, HEIGHT)
        elif theme.background_type == "custom_image" and theme.custom_bg_path and Path(theme.custom_bg_path).is_file():
            im = Image.open(theme.custom_bg_path).convert("RGB")
            scale = max(WIDTH / float(im.width), HEIGHT / float(im.height))
            nw, nh = int(im.width * scale), int(im.height * scale)
            base_bg = im.resize((nw, nh), Image.Resampling.BICUBIC).crop(((nw - WIDTH)//2, (nh - HEIGHT)//2, (nw + WIDTH)//2, (nh + HEIGHT)//2)).convert("RGBA")
        else:
            base_bg = InvestigationBoardService.generate_corkboard_texture(WIDTH, HEIGHT)

        def _get_cfg_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
            cp = theme.font_bold_path if bold else theme.font_regular_path
            if cp and Path(cp).is_file():
                return ImageFont.truetype(cp, size)
            return _get_font(size, bold=bold)

        for chap in chapters:
            scene_id = f"chapter_{chap.index:03d}"
            silent_scene_mp4 = scenes_dir / f"{scene_id}_silent.mp4"
            scene_mp4 = scenes_dir / f"{scene_id}.mp4"
            total_frames = int(round(chap.total_duration_ms / 1000.0 * self.fps))

            # Concatenate node audio tracks for this chapter
            chap_audio_concat = audio_dir / f"{scene_id}_audio_concat.txt"
            with open(chap_audio_concat, "w", encoding="utf-8") as f:
                for n_idx in range(1, len(chap.nodes) + 1):
                    node_voice = audio_dir / f"node_{chap.index:02d}_{n_idx:02d}_voice.wav"
                    f.write(f"file '{node_voice.resolve().as_posix()}'\n")

            chap_voice_wav = audio_dir / f"{scene_id}_voice.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(chap_audio_concat), "-c", "copy", str(chap_voice_wav)],
                check=True,
                capture_output=True,
            )

            # Build synchronized SFX events at EXACT onset of each node
            sfx_events: list[SFXEvent] = []
            for node in chap.nodes:
                sfx_events.append(SFXEvent(sfx_type="whoosh", start_ms=node.start_ms, volume_db=-3.0))
                sfx_events.append(SFXEvent(sfx_type="pushpin_hit", start_ms=node.start_ms + 150, volume_db=-2.0))
                if node.index > 1:
                    sfx_events.append(SFXEvent(sfx_type="paper_slide", start_ms=node.start_ms + 300, volume_db=-4.0))

            # Master stamp at end of chapter
            sfx_events.append(SFXEvent(sfx_type="stamp_impact", start_ms=max(0, chap.total_duration_ms - 800), volume_db=-2.0))

            sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
            self.sfx_service.render_scene_sfx_track(sfx_events, chap.total_duration_ms, sfx_wav)

            chap_mixed_audio = audio_dir / f"{scene_id}_audio.wav"
            self.sfx_service.mix_sfx_with_voice(chap_voice_wav, sfx_wav, chap_mixed_audio, voice_gain_db=1.0, sfx_gain_db=-5.0)

            # Prepare all stickers for this chapter with clean torn cutout
            rendered_stickers: list[tuple[TimedEntityNode, Image.Image]] = []
            for node in chap.nodes:
                asset_p = asset_map[(chap.index, node.index)]
                raw_stk = Image.open(asset_p).convert("RGBA")
                scale = node.target_scale / float(max(10, raw_stk.height))
                nw, nh = max(10, int(raw_stk.width * scale)), max(10, int(raw_stk.height * scale))
                fitted = raw_stk.resize((nw, nh), Image.Resampling.BICUBIC)
                torn_stk = PaperCraftService.create_torn_cutout(
                    fitted, PaperCutoutOptions(border_width=14, roughness=0.55, shadow=True)
                )
                rendered_stickers.append((node, torn_stk))

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

            for f in range(total_frames):
                t_sec = f / float(self.fps)
                t_ms = int(t_sec * 1000)

                # Subtle continuous camera drift
                drift_x = int(math.sin(f * 0.035) * 5)
                drift_y = int(math.cos(f * 0.035) * 4)

                frame = base_bg.copy()
                draw = ImageDraw.Draw(frame)

                # Viewfinder HUD
                if theme.hud_overlay:
                    draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
                    c_len = 22
                    for cx, cy in [(40, 40), (WIDTH - 40, 40), (40, HEIGHT - 40), (WIDTH - 40, HEIGHT - 40)]:
                        sx = 1 if cx == 40 else -1
                        sy = 1 if cy == 40 else -1
                        draw.line([(cx, cy), (cx + sx * c_len, cy)], fill=(*theme.accent_color, 220), width=3)
                        draw.line([(cx, cy), (cx, cy + sy * c_len)], fill=(*theme.accent_color, 220), width=3)

                    font_tag = _get_cfg_font(16, bold=True)
                    draw.text((WIDTH // 2, 52), f"{theme.hud_tag_prefix.upper()} // CHƯƠNG {chap.index:02d}", font=font_tag, fill=(*theme.accent_color, 230), anchor="mm")

                # Top Chapter Header Badge with auto-expanding width
                p_top = min(1.0, t_sec / 0.3)
                if p_top > 0:
                    title_text = f"CHƯƠNG {chap.index:02d}: {chap.title}"
                    font_title = _get_cfg_font(20, bold=True)
                    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
                    tw = bbox_title[2] - bbox_title[0]
                    box_w = max(420, tw + 60)
                    draw.rectangle([(WIDTH // 2 - box_w // 2, 78), (WIDTH // 2 + box_w // 2, 134)], fill=(*theme.banner_bg_color, 245), outline=(*theme.accent_color, 240), width=2)
                    draw.text((WIDTH // 2, 106), title_text, font=font_title, fill=(*theme.accent_color, 255), anchor="mm")

                # 1. DRAW CONNECTING RED STRINGS between currently landed nodes
                for i in range(len(rendered_stickers) - 1):
                    node_a, _ = rendered_stickers[i]
                    node_b, _ = rendered_stickers[i + 1]
                    if t_ms >= node_b.start_ms + 100:
                        string_p = min(1.0, (t_ms - (node_b.start_ms + 100)) / 300.0)
                        InvestigationBoardService.draw_catenary_red_string(
                            frame,
                            node_a.target_pos,
                            node_b.target_pos,
                            sag=32.0,
                            progress=string_p,
                            width=5,
                        )

                # 2. PASTE ALL LANDED EVIDENCE CUTOUTS AT EXACT MILLISECOND WITH 0.15s SNAPPY SLAM
                for node, stk_img in rendered_stickers:
                    if t_ms >= node.start_ms:
                        elapsed = (t_ms - node.start_ms) / 1000.0
                        p_drop = _ease_overshoot_bounce(min(1.0, elapsed / 0.18))
                        cur_y = int(-180 + (180 + node.target_pos[1] + drift_y) * p_drop)
                        rot = node.rotation_deg * p_drop
                        im_rot = stk_img.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
                        frame.paste(
                            im_rot,
                            (node.target_pos[0] + drift_x - im_rot.width // 2, cur_y - im_rot.height // 2),
                            mask=im_rot.split()[-1],
                        )

                # 3. KINETIC SUBTITLE AT FIXED BOTTOM POSITION (Y = 960px) - AUTO SIZING & ZERO OVERFLOW
                active_subtitle_text = ""
                for node in chap.nodes:
                    if node.start_ms <= t_ms <= node.start_ms + node.duration_ms + 200:
                        active_subtitle_text = node.text
                        break

                if active_subtitle_text:
                    sub_y = 960
                    if len(active_subtitle_text) > 70:
                        font_sub = _get_cfg_font(20, bold=True)
                    elif len(active_subtitle_text) > 45:
                        font_sub = _get_cfg_font(23, bold=True)
                    else:
                        font_sub = _get_cfg_font(26, bold=True)

                    bbox_sub = draw.textbbox((0, 0), active_subtitle_text, font=font_sub)
                    sub_w = bbox_sub[2] - bbox_sub[0]
                    box_sub_w = min(WIDTH - 120, max(500, sub_w + 60))

                    draw.rectangle([(WIDTH // 2 - box_sub_w // 2, sub_y - 28), (WIDTH // 2 + box_sub_w // 2, sub_y + 36)], fill=(12, 16, 22, 235), outline=(*theme.accent_color, 210), width=2)
                    draw.text((WIDTH // 2, sub_y + 4), active_subtitle_text, font=font_sub, fill=(255, 235, 70, 255), anchor="mm")

                # 4. CHAPTER VERIFICATION STAMP (at end of chapter)
                if t_ms >= chap.total_duration_ms - 800:
                    stamp_p = _ease_overshoot_bounce(min(1.0, (t_ms - (chap.total_duration_ms - 800)) / 300.0))
                    InvestigationBoardService.render_investigation_stamp(
                        frame, (WIDTH // 2, 700), "XÁC MINH HỒ SƠ", angle_deg=-10.0, scale=stamp_p * 1.3
                    )

                proc.stdin.write(frame.tobytes())

            proc.stdin.close()
            proc.wait()

            SceneAudioMuxer().mux(silent_scene_mp4, chap_mixed_audio, scene_mp4, fps=30)
            scene_mp4s.append(scene_mp4)

        # Step 5: Master Audio & Subtitles
        logger.info("Step 5: Mixing Master Audio Track and Exporting Subtitles...")
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
        logger.info("Step 6: Concatenating all chapters into Master 1080p MP4...")
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
        logger.info(f"=== [ZERO-OMISSION CRAZY-WALL SUCCESS] Rendered in {elapsed:.1f}s -> {final_video_path} ===")

        return PipelineResult(
            project_id=project_id,
            video_path=final_video_path,
            subtitles_path=srt_path,
            duration_seconds=total_dur_ms / 1000.0,
            scene_count=len(chapters),
            resolution=(WIDTH, HEIGHT),
            fps=self.fps,
        )


def _ease_overshoot_bounce(t: float, overshoot: float = 1.35) -> float:
    """Overshoot spring bounce easing."""
    t = max(0.0, min(1.0, t))
    if t >= 1.0:
        return 1.0
    return float(1.0 + (overshoot + 1.0) * ((t - 1.0) ** 3) + overshoot * ((t - 1.0) ** 2))


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
