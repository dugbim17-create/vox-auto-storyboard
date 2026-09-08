"""Tactical radar sweep, nautical compass, and waypoint tracking engine for Vox documentaries."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Waypoint:
    """A tactical map/radar coordinate waypoint."""

    name: str
    x: int
    y: int
    active: bool = True
    blip_color: tuple[int, int, int] = (255, 220, 30)  # Neon amber/yellow


@dataclass(frozen=True)
class RadarOptions:
    """Configuration options for procedural tactical radar sweep."""

    radius: int = 240
    color: tuple[int, int, int] = (40, 220, 180)  # Neon cyan/teal
    beam_width_deg: float = 35.0
    beam_opacity: float = 0.55
    ring_count: int = 4
    crosshair: bool = True
    grid_background: bool = True


class TacticalRadarService:
    """Render procedural 360-degree radar beams, pulsing sonar blips, and flight waypoints."""

    @staticmethod
    def render_radar_frame(
        width: int,
        height: int,
        center: tuple[int, int],
        angle_deg: float,
        waypoints: list[Waypoint] | None = None,
        options: RadarOptions | None = None,
    ) -> Image.Image:
        """Render a single frame of an animated 360-degree rotating radar scan."""
        opts = options or RadarOptions()
        radar_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(radar_img)
        cx, cy = center
        r = opts.radius

        # 1. Concentric range rings
        for i in range(1, opts.ring_count + 1):
            curr_r = int(r * (i / float(opts.ring_count)))
            draw.ellipse(
                [(cx - curr_r, cy - curr_r), (cx + curr_r, cy + curr_r)],
                outline=(*opts.color, 45),
                width=1,
            )

        # 2. Tactical Crosshairs
        if opts.crosshair:
            draw.line([(cx - r, cy), (cx + r, cy)], fill=(*opts.color, 40), width=1)
            draw.line([(cx, cy - r), (cx, cy + r)], fill=(*opts.color, 40), width=1)

        # 3. Rotating radar beam sector with smooth fading angular trail
        beam_mask = Image.new("L", (width, height), 0)
        bdraw = ImageDraw.Draw(beam_mask)
        rad_angle = math.radians(angle_deg)
        steps = int(opts.beam_width_deg)

        for deg_offset in range(steps):
            a = rad_angle - math.radians(deg_offset)
            decay = math.pow(1.0 - (deg_offset / float(steps)), 1.5)
            alpha = int(255 * opts.beam_opacity * decay)
            ex = cx + math.cos(a) * r
            ey = cy + math.sin(a) * r
            bdraw.line([(cx, cy), (int(ex), int(ey))], fill=alpha, width=2)

        beam_layer = Image.new("RGBA", (width, height), (*opts.color, 255))
        radar_img.paste(beam_layer, (0, 0), mask=beam_mask)

        # 4. Waypoints & pulsing radar blips
        for wp in waypoints or []:
            wx, wy = wp.x, wp.y
            # Blip core
            draw.ellipse([(wx - 5, wy - 5), (wx + 5, wy + 5)], fill=(*wp.blip_color, 255))
            # Echo ring
            draw.ellipse([(wx - 11, wy - 11), (wx + 11, wy + 11)], outline=(*wp.blip_color, 160), width=1)
            if wp.name:
                # Text label
                draw.text((wx + 14, wy - 8), wp.name, fill=(255, 255, 255, 220))

        return radar_img

    @staticmethod
    def draw_tactical_flight_arc(
        canvas: Image.Image,
        points: list[tuple[int, int]],
        progress: float = 1.0,
        color: tuple[int, int, int] = (255, 220, 30),
        width: int = 3,
    ) -> None:
        """Draw an animated dashed/dotted tactical flight or sea navigation route."""
        if len(points) < 2 or progress <= 0:
            return
        draw = ImageDraw.Draw(canvas)
        p = max(0.0, min(1.0, progress))

        total_segments = len(points) - 1
        active_segments = int(total_segments * p)
        rem_frac = (total_segments * p) - active_segments

        for i in range(active_segments):
            draw.line([points[i], points[i + 1]], fill=(*color, 230), width=width)

        if active_segments < total_segments and rem_frac > 0:
            p0 = points[active_segments]
            p1 = points[active_segments + 1]
            inter_x = int(p0[0] + (p1[0] - p0[0]) * rem_frac)
            inter_y = int(p0[1] + (p1[1] - p0[1]) * rem_frac)
            draw.line([p0, (inter_x, inter_y)], fill=(*color, 230), width=width)
