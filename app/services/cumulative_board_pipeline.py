"""Multi-Node Cumulative Investigation Board & Network Dossier Engine.

Solves the core bottleneck:
Instead of resetting the screen on every single micro-beat (which made it feel disjointed),
each Chapter/Scene establishes a persistent Investigation Canvas (12s - 20s) where multiple
evidentiary nodes (portraits, ships, maps, tickets, notes) ACCUMULATE sequentially on the same page,
interconnected with dynamic red strings, pins, sticky notes, and stamps.
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
from app.services.investigation_board import EvidenceChecklist, InvestigationBoardService, StickyNote
from app.services.paper_craft import PaperCraftService, PaperCutoutOptions
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.segmentation import RembgBackend
from app.services.sfx_service import AutoSFXService, SFXEvent
from app.services.subtitle_generator import SubtitleEntry, entries_to_srt

logger = logging.getLogger(__name__)

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DEFAULT_PIPER_MODEL = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx")
DEFAULT_PIPER_CONFIG = Path(r"D:\Tool Recap 25-5\_unpack\proj\models\piper\ngoc_huyen_moi.onnx.json")


@dataclass(frozen=True)
class BeatNode:
    """A single evidentiary node inside a chapter board."""

    index: int
    text: str
    duration_ms: int
    prompt: str
    zone_pos: tuple[int, int]
    target_scale: float
    angle_deg: float


@dataclass
class ChapterBoard:
    """A thematic chapter/page containing 3 to 5 accumulating evidentiary nodes."""

    index: int
    title: str
    nodes: list[BeatNode] = field(default_factory=list)
    total_duration_ms: int = 0


# Spatial coordinate zones on 1920x1080 canvas for multi-node accumulation
CANVAS_ZONES = [
    ((480, 480), 380.0, -3.5),   # Zone 0: Mid-Left
    ((1420, 480), 380.0, 3.5),   # Zone 1: Mid-Right
    ((960, 460), 420.0, 0.0),    # Zone 2: Center Anchor
    ((520, 780), 300.0, -4.0),   # Zone 3: Bottom-Left
    ((1400, 780), 300.0, 4.0),   # Zone 4: Bottom-Right
]


def cluster_script_into_chapters(script_text: str) -> list[ChapterBoard]:
    """Cluster script into thematic chapters where facts accumulate on one canvas."""
    # Split paragraphs
    raw_paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
    if not raw_paragraphs or len(raw_paragraphs) == 1:
        # Fallback split by every 2-3 sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.?!;:])\s+", script_text) if s.strip()]
        grouped: list[list[str]] = []
        cur_g: list[str] = []
        for s in sentences:
            cur_g.append(s)
            if len(cur_g) >= 3:
                grouped.append(cur_g)
                cur_g = []
        if cur_g:
            if grouped:
                grouped[-1].extend(cur_g)
            else:
                grouped.append(cur_g)
        raw_paragraphs = [" ".join(g) for g in grouped]

    chapters: list[ChapterBoard] = []
    for chap_idx, para in enumerate(raw_paragraphs, start=1):
        sentences = [s.strip() for s in re.split(r"(?<=[.?!;:])\s+", para) if s.strip()]
        if not sentences:
            sentences = [para]

        nodes: list[BeatNode] = []
        for n_idx, s in enumerate(sentences, start=1):
            zone_idx = (n_idx - 1) % len(CANVAS_ZONES)
            pos, sc, ang = CANVAS_ZONES[zone_idx]
            # Construct distinct AI prompt for each node
            prompt = (
                f"A tactile historical mixed-media documentary photograph for: {s[:130]}. "
                "Isolated on plain solid neutral light gray studio background, clean sharp silhouette edges, "
                "dramatic top-down studio lighting, authentic editorial archival photograph, 8k resolution"
            )
            nodes.append(
                BeatNode(
                    index=n_idx,
                    text=s,
                    duration_ms=3000,  # Will be updated with exact voice duration
                    prompt=prompt,
                    zone_pos=pos,
                    target_scale=sc,
                    angle_deg=ang,
                )
            )

        title = sentences[0][:32].upper()
        chapters.append(ChapterBoard(index=chap_idx, title=title, nodes=nodes))

    return chapters


class CumulativeBoardPipeline:
    """1-Click Cumulative Multi-Node Investigation Board Engine."""

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

    async def run_from_script(
        self,
        script_text: str,
        *,
        project_title: str = "Vox_Project",
    ) -> Any:
        """Run the cumulative board pipeline where clues accumulate on unified canvases."""
        t0 = time.time()
        project_id = f"prj_{int(time.time())}_{project_title[:16].replace(' ', '_').lower()}"
        project_dir = self.output_base_dir / project_id
        scenes_dir = project_dir / "scenes"
        audio_dir = project_dir / "audio"
        assets_dir = project_dir / "assets"
        final_dir = project_dir / "final"

        for d in (scenes_dir, audio_dir, assets_dir, final_dir):
            d.mkdir(parents=True, exist_ok=True)

        logger.info(f"=== [CUMULATIVE BOARD PIPELINE START] Project: {project_id} ===")

        # Step 1: Cluster Script into Multi-Node Chapters
        chapters = cluster_script_into_chapters(script_text)
        logger.info(f"Step 1: Clustered into {len(chapters)} Chapters with total {sum(len(c.nodes) for c in chapters)} accumulating nodes.")

        # Step 2: Synthesize Voice Tracks for each node & calculate accurate durations
        logger.info("Step 2: Synthesizing TTS Voice Tracks per node...")
        voice = PiperVoice.load(str(self.piper_model), config_path=str(self.piper_config))
        subtitle_entries: list[SubtitleEntry] = []
        current_time_ms = 0
        global_node_idx = 1

        all_nodes_flat: list[tuple[int, int, BeatNode]] = []  # (chap_idx, node_idx, BeatNode)

        for chap in chapters:
            chap_dur = 0
            for n_idx, node in enumerate(chap.nodes, start=1):
                voice_wav = audio_dir / f"node_{chap.index:02d}_{n_idx:02d}_voice.wav"
                with wave.open(str(voice_wav), "wb") as wf:
                    voice.synthesize_wav(node.text, wf)

                with wave.open(str(voice_wav), "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    dur_ms = max(2600, int((frames / float(rate)) * 1000) + 400)

                # Update node duration
                updated_node = BeatNode(
                    index=node.index,
                    text=node.text,
                    duration_ms=dur_ms,
                    prompt=node.prompt,
                    zone_pos=node.zone_pos,
                    target_scale=node.target_scale,
                    angle_deg=node.angle_deg,
                )
                chap.nodes[n_idx - 1] = updated_node
                chap_dur += dur_ms

                subtitle_entries.append(
                    SubtitleEntry(
                        index=global_node_idx,
                        start_ms=current_time_ms + 50,
                        end_ms=current_time_ms + dur_ms - 100,
                        text=node.text,
                    )
                )
                current_time_ms += dur_ms
                global_node_idx += 1
                all_nodes_flat.append((chap.index, n_idx, updated_node))

            chap.total_duration_ms = chap_dur

        # Step 3: Concurrently generate dedicated AI images for ALL nodes in parallel
        logger.info(f"Step 3: Concurrently generating {len(all_nodes_flat)} dedicated AI images via CLIProxy...")
        sem = asyncio.Semaphore(6)

        async def _gen_node_asset(chap_i: int, n_i: int, node: BeatNode) -> tuple[int, int, Path]:
            raw_p = assets_dir / f"asset_{chap_i:02d}_{n_i:02d}_raw.png"
            cutout_p = assets_dir / f"asset_{chap_i:02d}_{n_i:02d}_cutout.png"
            req = ImageGenerationRequest(prompt=node.prompt, role="composite", output_path=str(raw_p))
            async with sem:
                try:
                    await self.image_provider.generate(req)
                    raw_im = Image.open(raw_p).convert("RGBA")
                    mask = self.segmenter.produce_mask(raw_im)
                    clean_im = raw_im.copy()
                    clean_im.putalpha(mask)
                    clean_im.save(cutout_p)
                    return (chap_i, n_i, cutout_p)
                except Exception as exc:
                    logger.warning(f"Chapter {chap_i} Node {n_i} image gen fallback: {exc}")
                    return (chap_i, n_i, raw_p)

        results = await asyncio.gather(*(_gen_node_asset(c_i, n_i, n) for c_i, n_i, n in all_nodes_flat))
        asset_map: dict[tuple[int, int], Path] = {(c_i, n_i): p for c_i, n_i, p in results}

        # Step 4: Render Frame-by-Frame Cumulative Chapter Scenes
        logger.info(f"Step 4: Rendering {len(chapters)} Cumulative Investigation Canvases...")
        scene_mp4s: list[Path] = []
        base_bg = InvestigationBoardService.generate_corkboard_texture(WIDTH, HEIGHT)

        for chap in chapters:
            scene_id = f"chapter_{chap.index:03d}"
            silent_scene_mp4 = scenes_dir / f"{scene_id}_silent.mp4"
            scene_mp4 = scenes_dir / f"{scene_id}.mp4"
            total_frames = int(round(chap.total_duration_ms / 1000.0 * self.fps))

            # Concatenate chapter audio
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

            # Build synchronized SFX events for each node entry
            sfx_events: list[SFXEvent] = []
            node_accum_time_ms = 0
            for n_idx, node in enumerate(chap.nodes, start=1):
                sfx_events.append(SFXEvent(sfx_type="whoosh", start_ms=node_accum_time_ms + 50, volume_db=-3.0))
                sfx_events.append(SFXEvent(sfx_type="pushpin_hit", start_ms=node_accum_time_ms + 400, volume_db=-2.5))
                if n_idx > 1:
                    sfx_events.append(SFXEvent(sfx_type="paper_slide", start_ms=node_accum_time_ms + 700, volume_db=-4.0))
                node_accum_time_ms += node.duration_ms

            # Master stamp at end of chapter
            sfx_events.append(SFXEvent(sfx_type="stamp_impact", start_ms=max(0, chap.total_duration_ms - 800), volume_db=-2.0))

            sfx_wav = audio_dir / f"{scene_id}_sfx.wav"
            self.sfx_service.render_scene_sfx_track(sfx_events, chap.total_duration_ms, sfx_wav)

            chap_mixed_audio = audio_dir / f"{scene_id}_audio.wav"
            self.sfx_service.mix_sfx_with_voice(chap_voice_wav, sfx_wav, chap_mixed_audio, voice_gain_db=1.0, sfx_gain_db=-5.0)

            # Prepare all stickers for this chapter
            rendered_stickers: list[tuple[BeatNode, Image.Image, int]] = []  # (node, sticker_img, start_ms)
            cur_ms = 0
            for n_idx, node in enumerate(chap.nodes, start=1):
                asset_p = asset_map[(chap.index, n_idx)]
                raw_stk = Image.open(asset_p).convert("RGBA")
                scale = node.target_scale / float(max(10, raw_stk.height))
                nw, nh = max(10, int(raw_stk.width * scale)), max(10, int(raw_stk.height * scale))
                fitted = raw_stk.resize((nw, nh), Image.Resampling.BICUBIC)
                torn_stk = PaperCraftService.create_torn_cutout(
                    fitted, PaperCutoutOptions(border_width=14, roughness=0.65, shadow=True)
                )
                rendered_stickers.append((node, torn_stk, cur_ms))
                cur_ms += node.duration_ms

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

            font_bold_22 = _get_font(22, bold=True)
            font_bold_16 = _get_font(16, bold=True)

            for f in range(total_frames):
                t_sec = f / float(self.fps)
                t_ms = int(t_sec * 1000)

                # Subtle continuous camera drift
                drift_x = int(math.sin(f * 0.04) * 5)
                drift_y = int(math.cos(f * 0.04) * 4)

                frame = base_bg.copy()
                draw = ImageDraw.Draw(frame)

                # Viewfinder HUD
                draw.rectangle([(40, 40), (WIDTH - 40, HEIGHT - 40)], outline=(255, 255, 255, 25), width=2)
                draw.text((WIDTH // 2, 52), f"HỒ SƠ ĐIỀU TRA // CHƯƠNG {chap.index:02d}: {chap.title}", font=font_bold_16, fill=(255, 220, 20, 230), anchor="mm")

                # Chapter Header Badge
                draw.rectangle([(WIDTH // 2 - 360, 80), (WIDTH // 2 + 360, 136)], fill=(20, 24, 30, 245), outline=(255, 220, 20, 240), width=2)
                draw.text((WIDTH // 2, 108), f"CHƯƠNG {chap.index:02d}: {chap.title}", font=font_bold_22, fill=(255, 220, 20, 255), anchor="mm")

                # Draw Accumulating Red Strings first (between previously landed nodes)
                for i in range(len(rendered_stickers) - 1):
                    node_a, _, start_ms_a = rendered_stickers[i]
                    node_b, _, start_ms_b = rendered_stickers[i + 1]
                    if t_ms >= start_ms_b + 400:
                        string_p = min(1.0, (t_ms - (start_ms_b + 400)) / 500.0)
                        InvestigationBoardService.draw_catenary_red_string(
                            frame,
                            node_a.zone_pos,
                            node_b.zone_pos,
                            sag=28.0,
                            progress=string_p,
                            width=5,
                        )

                # Paste All Currently Landed Clues / Stickers
                for node, stk_img, node_start_ms in rendered_stickers:
                    if t_ms >= node_start_ms:
                        elapsed_since_entry = (t_ms - node_start_ms) / 1000.0
                        p_drop = _ease_overshoot_bounce(min(1.0, elapsed_since_entry / 0.45))
                        cur_y = int(-200 + (200 + node.zone_pos[1] + drift_y) * p_drop)
                        rot = node.angle_deg * p_drop
                        im_rot = stk_img.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
                        frame.paste(
                            im_rot,
                            (node.zone_pos[0] + drift_x - im_rot.width // 2, cur_y - im_rot.height // 2),
                            mask=im_rot.split()[-1],
                        )

                # Paste Sticky Note Annotations for recent nodes
                for n_i, (node, _, node_start_ms) in enumerate(rendered_stickers):
                    if t_ms >= node_start_ms + 800:
                        note_p = _ease_overshoot_bounce(min(1.0, (t_ms - (node_start_ms + 800)) / 400.0))
                        note_text = node.text[:26].upper()
                        sub = node.text[26:65] if len(node.text) > 26 else ""
                        note = InvestigationBoardService.render_sticky_note(
                            StickyNote(text=note_text, subtext=sub, size=(320, 160), angle_deg=-4.0 if n_i % 2 == 0 else 4.0)
                        )
                        ny = int(node.zone_pos[1] + 180 + drift_y)
                        frame.paste(note, (node.zone_pos[0] - note.width // 2, ny - note.height // 2), mask=note.split()[-1])

                # Chapter Verification Stamp (at end of chapter)
                if t_ms >= chap.total_duration_ms - 800:
                    stamp_p = _ease_overshoot_bounce(min(1.0, (t_ms - (chap.total_duration_ms - 800)) / 350.0))
                    InvestigationBoardService.render_investigation_stamp(
                        frame, (WIDTH // 2, 750), "XÁC MINH HỒ SƠ", angle_deg=-12.0, scale=stamp_p * 1.3
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
        logger.info(f"=== [CUMULATIVE BOARD PIPELINE SUCCESS] Rendered in {elapsed:.1f}s -> {final_video_path} ===")

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
