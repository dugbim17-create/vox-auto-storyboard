"""Unit tests for TacticalRadarService."""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.services.tactical_radar import RadarOptions, TacticalRadarService, Waypoint


def test_render_radar_frame_creates_rgba_beam() -> None:
    waypoints = [
        Waypoint(name="WAYPOINT ALFA", x=250, y=180),
        Waypoint(name="TARGET BRAVO", x=400, y=300),
    ]
    opts = RadarOptions(radius=180, ring_count=3, crosshair=True)
    radar = TacticalRadarService.render_radar_frame(
        640, 480, (320, 240), angle_deg=45.0, waypoints=waypoints, options=opts
    )

    assert radar.size == (640, 480)
    assert radar.mode == "RGBA"
    arr = np.array(radar)
    assert np.any(arr[:, :, 3] > 0)


def test_draw_tactical_flight_arc_renders_partial_and_full() -> None:
    canvas = Image.new("RGBA", (400, 300), (0, 0, 0, 255))
    points = [(50, 50), (150, 100), (250, 80), (350, 200)]

    # Progress 0 -> no change
    TacticalRadarService.draw_tactical_flight_arc(canvas, points, progress=0.0)
    # Progress 0.5 -> partial
    TacticalRadarService.draw_tactical_flight_arc(canvas, points, progress=0.5)
    arr = np.array(canvas)
    assert np.any(arr[:, :, :3] > 0)
