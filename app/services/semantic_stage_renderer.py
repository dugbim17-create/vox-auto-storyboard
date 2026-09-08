"""Raster compositor for semantic entities and state mutations."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

from app.schemas.semantic_visual_stage import SemanticVisualStage


def compose_semantic_stage_frame(
    background: Image.Image,
    entity_images: dict[str, Image.Image],
    stage: SemanticVisualStage,
    elapsed_ms: int,
) -> Image.Image:
    canvas = background.copy().convert("RGBA")
    revealed: set[str] = set()
    positions = {entity.entity_id: (float(entity.x), float(entity.y)) for entity in stage.entities}
    merged: set[str] = set()
    transformed: set[str] = set()
    highlighted: set[str] = set()
    focused: str = ""
    edges: list[tuple[str, str, float, str]] = []

    for event in stage.events:
        if elapsed_ms < event.start_ms:
            continue
        progress = min(1.0, (elapsed_ms - event.start_ms) / max(1, event.duration_ms))
        eased = progress * progress * (3.0 - 2.0 * progress)
        if event.action == "reveal":
            revealed.add(event.target)
        elif event.action == "connect":
            revealed.update((event.source, event.target))
            edges.append((event.source, event.target, eased, event.label))
        elif event.action == "disconnect":
            edges = [edge for edge in edges if not (edge[0] == event.source and edge[1] == event.target)]
        elif event.action == "merge":
            revealed.update((event.source, event.target))
            source_pos = positions[event.source]
            target_pos = positions[event.target]
            positions[event.source] = (
                source_pos[0] + (target_pos[0] - source_pos[0]) * eased,
                source_pos[1] + (target_pos[1] - source_pos[1]) * eased,
            )
            if eased >= 1.0:
                merged.add(event.source)
        elif event.action == "move":
            revealed.add(event.target)
            start = positions[event.target]
            destination = (
                float(event.to_x if event.to_x is not None else start[0]),
                float(event.to_y if event.to_y is not None else start[1]),
            )
            positions[event.target] = (
                start[0] + (destination[0] - start[0]) * eased,
                start[1] + (destination[1] - start[1]) * eased,
            )
        elif event.action == "transform":
            revealed.add(event.target)
            if eased >= 0.5:
                transformed.add(event.target)
        elif event.action == "highlight":
            revealed.add(event.target)
            highlighted.add(event.target)
        elif event.action == "focus":
            revealed.add(event.target)
            focused = event.target

    draw = ImageDraw.Draw(canvas)
    for source_id, target_id, progress, label in edges:
        _draw_edge(draw, positions[source_id], positions[target_id], progress, label)

    for entity in sorted(stage.entities, key=lambda item: item.z):
        if entity.entity_id not in revealed or entity.entity_id in merged:
            continue
        image_key = f"{entity.entity_id}:transform" if entity.entity_id in transformed else entity.entity_id
        image = entity_images[image_key].copy().convert("RGBA")
        x, y = positions[entity.entity_id]
        reveal_events = [
            event
            for event in stage.events
            if event.action == "reveal" and event.target == entity.entity_id and elapsed_ms >= event.start_ms
        ]
        if reveal_events:
            reveal = reveal_events[-1]
            progress = min(1.0, max(0.0, (elapsed_ms - reveal.start_ms) / max(1, reveal.duration_ms)))
            eased = progress * progress * (3.0 - 2.0 * progress)
            if eased <= 0:
                continue
            scale = 0.72 + 0.28 * eased
            original_size = image.size
            scaled_size = (max(2, round(image.width * scale)), max(2, round(image.height * scale)))
            image = image.resize(scaled_size, Image.Resampling.LANCZOS)
            x += (original_size[0] - scaled_size[0]) / 2
            y += (original_size[1] - scaled_size[1]) / 2
            alpha = image.getchannel("A").point(lambda value, opacity=eased: round(value * opacity))
            image.putalpha(alpha)
        if focused and entity.entity_id != focused:
            alpha = image.getchannel("A").point(lambda value: round(value * 0.28))
            image.putalpha(alpha)
        if entity.entity_id in highlighted:
            pulse = 12 + round(6 * math.sin(elapsed_ms / 120))
            draw.ellipse(
                (x - pulse, y - pulse, x + image.width + pulse, y + image.height + pulse),
                outline="#d1283b",
                width=8,
            )
        canvas.alpha_composite(image, (round(x), round(y)))
    return canvas.convert("RGB")


def _draw_edge(
    draw: ImageDraw.ImageDraw,
    source: tuple[float, float],
    target: tuple[float, float],
    progress: float,
    label: str,
) -> None:
    start = (source[0] + 40, source[1] + 40)
    end = (target[0] + 40, target[1] + 40)
    current = (
        start[0] + (end[0] - start[0]) * progress,
        start[1] + (end[1] - start[1]) * progress,
    )
    draw.line((start, current), fill="#cf2637", width=10)
    if progress > 0.75:
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        arrow = 18
        p1 = (current[0] - arrow * math.cos(angle - 0.6), current[1] - arrow * math.sin(angle - 0.6))
        p2 = (current[0] - arrow * math.cos(angle + 0.6), current[1] - arrow * math.sin(angle + 0.6))
        draw.polygon((current, p1, p2), fill="#cf2637")
    if label and progress > 0.45:
        font = _font(26)
        center = ((start[0] + current[0]) / 2, (start[1] + current[1]) / 2 - 34)
        bbox = draw.textbbox((0, 0), label, font=font)
        width = bbox[2] - bbox[0]
        draw.rounded_rectangle(
            (center[0] - width / 2 - 12, center[1] - 6, center[0] + width / 2 + 12, center[1] + 34),
            radius=8,
            fill="#eee4ce",
            outline="#151515",
            width=3,
        )
        draw.text((center[0] - width / 2, center[1]), label, font=font, fill="#151515")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = r"C:\Windows\Fonts\arialbd.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


__all__ = ["compose_semantic_stage_frame"]
