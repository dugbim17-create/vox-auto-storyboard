"""Deterministic frame compositor for typed semantic scene actions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont

from app.schemas.semantic_scene import CanonicalScene


class SemanticRenderError(ValueError):
    """Raised when a semantic plan cannot produce a valid frame."""


class VoxSemanticSceneRenderer:
    """Render a semantic plan to a verified H.264 scene without provider calls."""

    renderer_name = "vox_semantic_ffmpeg_pillow"
    renderer_version = "1"

    def __init__(self, *, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe") -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    @classmethod
    def for_production(
        cls,
        base_renderer: Any,
        canonical_scenes: dict[str, CanonicalScene],
    ) -> CanonicalProductionRenderer:
        return CanonicalProductionRenderer(base_renderer, canonical_scenes)

    def render_scene(self, scene: CanonicalScene, output: str | Path) -> Path:
        """Render the single canonical scene contract."""
        return self.render_plan(scene.to_render_plan(), output)

    def render_plan(self, plan: dict[str, Any], output: str | Path) -> Path:
        return _render_plan(self, plan, output)


class CanonicalProductionRenderer:
    """ProjectManager/RenderCoordinator adapter for canonical scenes only."""

    renderer_name = VoxSemanticSceneRenderer.renderer_name
    renderer_version = VoxSemanticSceneRenderer.renderer_version

    def __init__(self, base_renderer: Any, canonical_scenes: dict[str, CanonicalScene]) -> None:
        self.base_renderer = base_renderer
        self.canonical_scenes = canonical_scenes
        self.renderer = VoxSemanticSceneRenderer(
            ffmpeg_bin=base_renderer.compiler.ffmpeg_bin,
            ffprobe_bin=base_renderer.ffprobe_bin,
        )

    def render_scene(
        self,
        project_id: str,
        scene_id: str,
        plan: dict,
        *,
        assets: dict[str, str] | None = None,
        project_root: str | Path | None = None,
    ):
        del plan, assets
        from app.services.scene_renderer import SceneRenderError
        from app.storage.asset_store import AssetStore

        scene = self.canonical_scenes.get(scene_id)
        if scene is None:
            raise SceneRenderError(f"canonical scene missing: {scene_id}")
        store = AssetStore(project_root or self.base_renderer.project_root)
        output = store.subdir(project_id, "scenes") / f"{scene_id}.mp4"
        self.renderer.render_scene(scene, output)
        probe = self.base_renderer._probe(output, scene.to_render_plan())
        return output, probe

def _render_plan(renderer: VoxSemanticSceneRenderer, plan: dict[str, Any], output: str | Path) -> Path:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas = plan.get("canvas") or {}
        width = int(canvas.get("width") or 1920)
        height = int(canvas.get("height") or 1080)
        motion_fps = int(plan.get("motion_fps") or 12)
        fps = int(plan.get("fps") or 30)
        duration_ms = int(plan.get("duration_ms") or 0)
        if duration_ms <= 0:
            raise SemanticRenderError("duration_ms must be positive")
        command = [
            renderer.ffmpeg_bin, "-y", "-v", "error", "-threads", "1",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
            "-r", str(motion_fps), "-i", "-", "-vf", f"fps={fps}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-t", f"{duration_ms / 1000:.3f}", str(output),
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdin is not None
        for index in range(round(duration_ms / 1000 * motion_fps)):
            frame = render_semantic_frame(plan, round(index / motion_fps * 1000))
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        code = process.wait()
        if code:
            raise SemanticRenderError(f"semantic ffmpeg failed: {stderr[-2000:]}")
        return output


def render_semantic_frame(plan: dict[str, Any], elapsed_ms: int) -> Image.Image:
    canvas = plan.get("canvas") or {}
    width = int(canvas.get("width") or 1920)
    height = int(canvas.get("height") or 1080)
    assets = plan.get("assets") or {}
    placements = plan.get("placements") or {}
    z_order = plan.get("z_order") or {}
    if not isinstance(assets, dict):
        raise SemanticRenderError("semantic render requires an asset map")
    if "background" not in assets:
        background_id = next(
            (asset_id for asset_id in assets if asset_id.casefold() in {"bg", "background"}),
            None,
        )
        if background_id is None:
            raise SemanticRenderError("semantic render requires a background asset")
        assets = {**assets, "background": assets[background_id]}
    background = _load_rgba(assets["background"])
    if background.size != (width, height):
        background = background.resize((width, height), Image.Resampling.LANCZOS)
    frame = background.copy()

    pose_variants: set[str] = set()
    selected_pose: dict[str, str] = {}
    active_tints: dict[str, str] = {}
    reveal_states: dict[str, dict[str, Any]] = {}
    move_states: dict[str, list[dict[str, Any]]] = {}
    procedural_subjects: set[str] = set()
    route_actions: list[dict[str, Any]] = []
    overlay_actions: list[dict[str, Any]] = []
    for action in plan.get("procedural_actions") or []:
        kind = action.get("type")
        start = int(action.get("start_ms") or 0)
        end = int(action.get("end_ms") or start + 1)
        if kind == "reveal":
            reveal_states[str(action.get("subject") or action.get("target") or "")] = action
        elif kind == "move":
            move_states.setdefault(
                str(action.get("subject") or action.get("target") or ""),
                [],
            ).append(action)
        if kind == "pose_sequence":
            variants = [str(item) for item in action.get("variants") or []]
            pose_variants.update(variants)
            if variants:
                progress = _progress(elapsed_ms, start, end)
                index = min(len(variants) - 1, int(progress * len(variants)))
                selected_pose[str(action.get("subject") or variants[0])] = variants[index]
        elif kind == "state_swap" and elapsed_ms >= start:
            tint = str(action.get("active_tint") or "")
            if tint:
                active_tints[str(action.get("subject") or "")] = tint
        elif kind in {"path_draw", "traveling_marker"}:
            route_actions.append(action)
            procedural_subjects.add(str(action.get("subject") or ""))
        elif kind in {"object_path", "chart_series", "counter_progress", "document_focus", "text_reveal"}:
            overlay_actions.append(action)
            if action.get("subject"):
                procedural_subjects.add(str(action["subject"]))

    rendered: set[str] = {"background"}
    for subject, variant in selected_pose.items():
        image = _load_rgba(_asset_path(assets, variant))
        _composite(frame, image, placements.get(variant) or placements.get(subject) or (0, 0))
        rendered.add(variant)
        rendered.add(subject)

    # Static context is composed before semantic overlays so highlights,
    # routes, counters and citations cannot be hidden by their source asset.
    for asset_id, path in sorted(assets.items(), key=lambda item: int(z_order.get(item[0], 10))):
        if asset_id in rendered or asset_id in pose_variants or asset_id in procedural_subjects:
            continue
        image = _load_rgba(path)
        reveal = reveal_states.get(asset_id)
        if reveal is not None:
            start = int(reveal.get("start_ms") or 0)
            end = int(reveal.get("end_ms") or start + 1)
            if elapsed_ms < start:
                continue
            progress = _progress(elapsed_ms, start, end)
            image = _reveal_image(image, progress, str(reveal.get("enter") or "popup"))
        if asset_id in active_tints:
            image = _tint(image, active_tints[asset_id])
        placement = placements.get(asset_id) or (0, 0)
        moves = move_states.get(asset_id) or []
        for move in moves:
            if elapsed_ms < int(move.get("start_ms") or 0):
                continue
            progress = _progress(
                elapsed_ms,
                int(move.get("start_ms") or 0),
                int(move.get("end_ms") or int(move.get("start_ms") or 0) + 1),
            )
            start_x, start_y = placement
            target_x = move.get("to_x")
            target_y = move.get("to_y")
            if target_x is not None and target_y is not None:
                placement = [
                    start_x + (float(target_x) - start_x) * progress,
                    start_y + (float(target_y) - start_y) * progress,
                ]
        named = str((reveal or {}).get("placement") or "")
        if named:
            placement = _named_placement(named, image.size, width, height)
        _composite(frame, image, placement)

    for action in route_actions:
        points = _path_points(action.get("path"))
        progress = _progress(
            elapsed_ms,
            int(action.get("start_ms") or 0),
            int(action.get("end_ms") or 1),
        )
        if action.get("type") == "path_draw":
            _draw_partial_path(
                frame,
                points,
                progress,
                str(action.get("color") or "#161616"),
                int(action.get("width") or 4),
            )
        elif action.get("type") == "traveling_marker":
            subject = str(action.get("subject") or "")
            marker = _load_rgba(_asset_path(assets, subject))
            x, y = _point_on_path(points, progress)
            _composite(frame, marker, (x - marker.width / 2, y - marker.height / 2))
            rendered.add(subject)

    draw = ImageDraw.Draw(frame)
    for action in overlay_actions:
        start = int(action.get("start_ms") or 0)
        end = int(action.get("end_ms") or start + 1)
        progress = _progress(elapsed_ms, start, end)
        kind = action.get("type")
        if kind == "object_path":
            if elapsed_ms < start:
                continue
            subject = str(action.get("subject") or "")
            image = _load_rgba(_asset_path(assets, subject))
            x, y = _point_on_path(_path_points(action.get("path")), progress)
            _composite(frame, image, (x - image.width / 2, y - image.height / 2))
            rendered.add(subject)
        elif kind == "chart_series":
            if elapsed_ms < start:
                continue
            origin = action.get("origin") or [80, height - 70]
            values = [float(value) for value in action.get("values") or []]
            if values:
                max_value = max(values) or 1.0
                bar_width = int(action.get("bar_width") or 42)
                gap = int(action.get("gap") or 22)
                max_height = int(action.get("max_height") or height * 0.55)
                for index, value in enumerate(values):
                    local = max(0.0, min(1.0, progress * len(values) - index))
                    bar_height = round(max_height * value / max_value * local)
                    if bar_height <= 0:
                        continue
                    x = round(float(origin[0])) + index * (bar_width + gap)
                    y = round(float(origin[1]))
                    draw.rectangle((x, y - bar_height, x + bar_width, y), fill=str(action.get("color") or "#cf2637"))
        elif kind == "counter_progress":
            if elapsed_ms < start:
                continue
            start_value = float(action.get("from") or 0)
            end_value = float(action.get("to") or 0)
            value = round(start_value + (end_value - start_value) * progress)
            position = action.get("position") or [width // 2, height // 2]
            draw.text(
                (int(position[0]), int(position[1])),
                f"{value}{action.get('suffix') or ''}",
                fill=str(action.get("color") or "#161616"),
                font=_font(int(action.get("font_size") or 24)),
                stroke_width=1,
            )
        elif kind == "document_focus" and elapsed_ms >= start:
            box = action.get("box") or [80, 80, width - 80, height - 80]
            draw.rectangle(tuple(int(item) for item in box), outline=str(action.get("color") or "#cf2637"), width=int(action.get("width") or 6))
        elif kind == "text_reveal" and elapsed_ms >= start:
            position = action.get("position") or [80, 80]
            draw.text(
                (int(position[0]), int(position[1])),
                str(action.get("text") or ""),
                fill=str(action.get("color") or "#161616"),
                font=_font(int(action.get("font_size") or 22)),
                stroke_width=1,
                stroke_fill=str(action.get("stroke_color") or action.get("color") or "#161616"),
            )

    return frame.convert("RGB")


def _asset_path(assets: dict[str, str], asset_id: str) -> str:
    path = assets.get(asset_id)
    if not path:
        raise SemanticRenderError(f"asset missing: {asset_id}")
    return str(path)


def _load_rgba(path: str | Path) -> Image.Image:
    source = Path(path)
    if not source.is_file():
        raise SemanticRenderError(f"asset file missing: {source}")
    with Image.open(source) as image:
        image.load()
        return image.convert("RGBA")


def _progress(elapsed_ms: int, start_ms: int, end_ms: int) -> float:
    if elapsed_ms <= start_ms:
        return 0.0
    if elapsed_ms >= end_ms:
        return 1.0
    return (elapsed_ms - start_ms) / max(1, end_ms - start_ms)


def _path_points(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise SemanticRenderError("path requires at least two points")
    points: list[tuple[float, float]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise SemanticRenderError("path point must be [x, y]")
        points.append((float(item[0]), float(item[1])))
    return points


def _point_on_path(points: list[tuple[float, float]], progress: float) -> tuple[float, float]:
    lengths = [
        ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
        for left, right in zip(points, points[1:], strict=False)
    ]
    target = sum(lengths) * max(0.0, min(1.0, progress))
    travelled = 0.0
    for index, length in enumerate(lengths):
        if travelled + length >= target or index == len(lengths) - 1:
            ratio = 0.0 if length == 0 else (target - travelled) / length
            left, right = points[index], points[index + 1]
            return (
                left[0] + (right[0] - left[0]) * ratio,
                left[1] + (right[1] - left[1]) * ratio,
            )
        travelled += length
    return points[-1]


def _draw_partial_path(
    frame: Image.Image,
    points: list[tuple[float, float]],
    progress: float,
    color: str,
    width: int,
) -> None:
    end = _point_on_path(points, progress)
    lengths = [
        ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5
        for left, right in zip(points, points[1:], strict=False)
    ]
    target = sum(lengths) * max(0.0, min(1.0, progress))
    travelled = 0.0
    visible = [points[0]]
    for index, length in enumerate(lengths):
        if travelled + length < target:
            visible.append(points[index + 1])
            travelled += length
        else:
            visible.append(end)
            break
    ImageDraw.Draw(frame).line(visible, fill=color, width=max(1, width), joint="curve")


def _tint(image: Image.Image, color: str) -> Image.Image:
    tint = Image.new("RGBA", image.size, (*ImageColor.getrgb(color), 255))
    blended = Image.blend(image, tint, 0.48)
    blended.putalpha(image.getchannel("A"))
    return blended


def _reveal_image(image: Image.Image, progress: float, effect: str) -> Image.Image:
    eased = progress * progress * (3.0 - 2.0 * progress)
    scale = 0.82 + 0.18 * eased if effect in {"popup", "counter", "stamp"} else 1.0
    if scale != 1.0:
        image = image.resize(
            (max(2, round(image.width * scale)), max(2, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    alpha = image.getchannel("A").point(lambda value: round(value * eased))
    image = image.copy()
    image.putalpha(alpha)
    return image


def _named_placement(name: str, size: tuple[int, int], width: int, height: int) -> tuple[int, int]:
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


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), max(10, size))
    return ImageFont.load_default()


def _composite(frame: Image.Image, image: Image.Image, placement: Any) -> None:
    if not isinstance(placement, (list, tuple)) or len(placement) != 2:
        raise SemanticRenderError(f"invalid placement: {placement!r}")
    frame.alpha_composite(image, (round(float(placement[0])), round(float(placement[1]))))


__all__ = ["SemanticRenderError", "VoxSemanticSceneRenderer", "render_semantic_frame"]
