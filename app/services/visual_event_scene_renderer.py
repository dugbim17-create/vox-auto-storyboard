"""Verified scene renderer for accumulated VisualStage events."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from app.schemas.visual_events import VisualStage, build_visual_stage
from app.services.scene_renderer import LocalSceneRenderer, RenderProbe, SceneRenderError
from app.storage.asset_store import AssetStore


class VoxAccumulatedSceneRenderer:
    """Rasterise narration events into one persistent stage per scene.

    The old FFmpeg motion renderer remains available as a fallback outside this
    explicit adapter. Production VOX uses this adapter so earlier events stay
    visible while later facts enter the same composition.
    """

    renderer_name = "ffmpeg_vox_visual_events"
    renderer_version = "1"

    def __init__(
        self,
        base_renderer: LocalSceneRenderer,
        event_stages: dict[str, dict[str, Any]],
        asset_maps: dict[str, dict[str, str]],
        *,
        motion_fps: int = 12,
    ) -> None:
        self.base_renderer = base_renderer
        self.event_stages = event_stages
        self.asset_maps = asset_maps
        self.motion_fps = motion_fps

    def render_scene(
        self,
        project_id: str,
        scene_id: str,
        plan: dict,
        *,
        assets: dict[str, str] | None = None,
        project_root: str | Path | None = None,
    ) -> tuple[Path, RenderProbe]:
        del plan, assets
        envelope = self.event_stages.get(scene_id)
        payload = envelope.get("payload") if isinstance(envelope, dict) else None
        if not isinstance(payload, dict):
            raise SceneRenderError(f"visual stage missing: {scene_id}")
        stage = build_visual_stage(payload)
        if not stage.events or not all(event.persistent for event in stage.events):
            raise SceneRenderError(f"visual stage is not accumulated: {scene_id}")
        role_assets = self.asset_maps.get(scene_id) or {}
        store = AssetStore(project_root or self.base_renderer.project_root)
        output = store.subdir(project_id, "scenes") / f"{scene_id}.mp4"
        self._render(stage, role_assets, output)
        probe = self.base_renderer._probe(
            output,
            {
                "fps": 30,
                "canvas": {
                    "width": stage.canvas_width,
                    "height": stage.canvas_height,
                },
                "duration_ms": stage.duration_ms,
            },
        )
        return output, probe

    def _render(self, stage: VisualStage, assets: dict[str, str], output: Path) -> None:
        background = Image.open(stage.background).convert("RGBA")
        event_images = {
            event.event_id: Image.open(assets.get(event.asset, event.asset)).convert("RGBA")
            for event in stage.events
        }
        command = [
            self.base_renderer.compiler.ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-threads",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{stage.canvas_width}x{stage.canvas_height}",
            "-r",
            str(self.motion_fps),
            "-i",
            "-",
            "-vf",
            "fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-t",
            f"{stage.duration_ms / 1000:.3f}",
            str(output),
        ]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        frames = round(stage.duration_ms / 1000 * self.motion_fps)
        for index in range(frames):
            elapsed_ms = round(index / self.motion_fps * 1000)
            frame = compose_visual_stage_frame(background, event_images, stage, elapsed_ms)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        code = proc.wait()
        if code:
            raise SceneRenderError(f"visual-event ffmpeg failed: {stderr[-2000:]}")


def compose_visual_stage_frame(
    background: Image.Image,
    event_images: dict[str, Image.Image],
    stage: VisualStage,
    elapsed_ms: int,
) -> Image.Image:
    canvas = background.copy().convert("RGBA")
    for event in sorted(stage.events, key=lambda item: (item.z, item.start_ms)):
        if elapsed_ms < event.start_ms:
            continue
        if not event.persistent and elapsed_ms > event.end_ms:
            continue
        image = event_images[event.event_id]
        opacity, scale, dx, dy = _event_state(event, elapsed_ms)
        if event.enter == "page_flip":
            image = image.resize((max(2, round(image.width * max(0.04, opacity))), image.height), Image.Resampling.LANCZOS)
        elif scale != 1.0:
            image = image.resize((max(2, round(image.width * scale)), max(2, round(image.height * scale))), Image.Resampling.LANCZOS)
        x, y = _placement(event.placement, image.size, stage.canvas_width, stage.canvas_height)
        x += round(dx)
        y += round(dy)
        alpha = image.getchannel("A").point(lambda value, factor=opacity: round(value * factor))
        image = image.copy()
        image.putalpha(alpha)
        canvas.alpha_composite(image, (x, y))
    return canvas.convert("RGB")


def _event_state(event: Any, elapsed_ms: int) -> tuple[float, float, float, float]:
    elapsed = max(0, elapsed_ms - event.start_ms)
    progress = min(1.0, elapsed / min(320, max(120, event.duration_ms)))
    eased = progress * progress * (3.0 - 2.0 * progress)
    if event.enter in {"popup", "fade", "glow"}:
        return eased, 0.82 + 0.18 * eased, 0.0, 0.0
    if event.enter == "counter":
        return eased, 1.08 - 0.08 * eased, 0.0, 0.0
    if event.enter == "stamp":
        return eased, 1.10 - 0.10 * eased, (1.0 - eased) * 8.0, 0.0
    if event.enter == "swipe_right":
        return eased, 1.0, -180.0 * (1.0 - eased), 0.0
    if event.enter == "swipe_left":
        return eased, 1.0, 180.0 * (1.0 - eased), 0.0
    if event.enter == "swipe_up":
        return eased, 1.0, 0.0, 180.0 * (1.0 - eased)
    return eased, 1.0, 0.0, 0.0


def _placement(name: str, size: tuple[int, int], width: int, height: int) -> tuple[int, int]:
    w, h = size
    return {
        "center_top": ((width - w) // 2, 120),
        "center": ((width - w) // 2, (height - h) // 2),
        "left": (120, (height - h) // 2),
        "left_center": (180, (height - h) // 2),
        "left_bottom": (140, height - h - 120),
        "right": (width - w - 140, (height - h) // 2),
        "right_bottom": (width - w - 140, height - h - 140),
        "center_bottom": ((width - w) // 2, height - h - 130),
        "top_left": (120, 120),
        "top_right": (width - w - 120, 120),
    }.get(name, ((width - w) // 2, (height - h) // 2))


__all__ = ["VoxAccumulatedSceneRenderer", "compose_visual_stage_frame"]
