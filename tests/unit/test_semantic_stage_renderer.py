from __future__ import annotations

import numpy as np
from PIL import Image

from app.schemas.semantic_visual_stage import build_semantic_stage
from app.services.semantic_stage_renderer import compose_semantic_stage_frame


def asset(color: tuple[int, int, int], size: tuple[int, int] = (80, 80)) -> Image.Image:
    return Image.new("RGBA", size, (*color, 255))


def stage():
    return build_semantic_stage(
        {
            "stage_id": "return",
            "narration": "Apple mua NeXT; Jobs trở lại.",
            "duration_ms": 5000,
            "background": "background.png",
            "canvas": {"width": 640, "height": 360},
            "entities": [
                {"entity_id": "jobs", "kind": "character", "asset": "jobs.png", "x": 80, "y": 160, "z": 3},
                {"entity_id": "next", "kind": "company", "asset": "next.png", "x": 240, "y": 160, "z": 2},
                {"entity_id": "apple", "kind": "company", "asset": "apple.png", "x": 500, "y": 160, "z": 2},
            ],
            "events": [
                {"event_id": "jobs_on", "start_ms": 0, "duration_ms": 500, "action": "reveal", "target": "jobs"},
                {"event_id": "next_on", "start_ms": 400, "duration_ms": 500, "action": "reveal", "target": "next"},
                {"event_id": "apple_on", "start_ms": 800, "duration_ms": 500, "action": "reveal", "target": "apple"},
                {"event_id": "deal", "start_ms": 1400, "duration_ms": 800, "action": "connect", "source": "apple", "target": "next", "label": "1996"},
                {"event_id": "merge", "start_ms": 2400, "duration_ms": 900, "action": "merge", "source": "next", "target": "apple"},
                {"event_id": "return", "start_ms": 3500, "duration_ms": 900, "action": "move", "target": "jobs", "to_x": 420, "to_y": 160, "label": "1997"},
            ],
        }
    )


def test_renderer_draws_relationship_edge_after_connect_event() -> None:
    background = Image.new("RGBA", (640, 360), (240, 235, 220, 255))
    assets = {"jobs": asset((0, 0, 0)), "next": asset((60, 80, 180)), "apple": asset((180, 40, 40))}
    before = compose_semantic_stage_frame(background, assets, stage(), 1200)
    after = compose_semantic_stage_frame(background, assets, stage(), 2100)
    assert np.mean(np.abs(np.asarray(after, dtype=int) - np.asarray(before, dtype=int))) > 0.4
    red_pixels = np.count_nonzero((np.asarray(after)[:, :, 0] > 150) & (np.asarray(after)[:, :, 1] < 90))
    assert red_pixels > 100


def test_renderer_moves_jobs_toward_apple_and_keeps_prior_entities() -> None:
    background = Image.new("RGBA", (640, 360), (240, 235, 220, 255))
    assets = {"jobs": asset((0, 0, 0)), "next": asset((60, 80, 180)), "apple": asset((180, 40, 40))}
    frame = compose_semantic_stage_frame(background, assets, stage(), 4400)
    pixels = np.asarray(frame)
    assert pixels[180, 440, :3].mean() < 40  # Jobs moved right.
    assert pixels[180, 540, 0] > 150  # Apple remains.


def test_transform_action_swaps_entity_asset() -> None:
    data = stage().to_dict()
    data["entities"].append({"entity_id": "phone", "kind": "product", "asset": "old.png", "x": 280, "y": 120, "z": 4, "metadata": {"transform_asset": "new.png"}})
    data["events"].append({"event_id": "phone_on", "start_ms": 0, "duration_ms": 300, "action": "reveal", "target": "phone", "source": "", "to_x": None, "to_y": None, "label": "", "metadata": {}})
    data["events"].append({"event_id": "phone_transform", "start_ms": 4500, "duration_ms": 400, "action": "transform", "target": "phone", "source": "", "to_x": None, "to_y": None, "label": "", "metadata": {}})
    data["events"] = sorted(data["events"], key=lambda item: item["start_ms"])
    transformed = build_semantic_stage(data)
    background = Image.new("RGBA", (640, 360), (240, 235, 220, 255))
    assets = {"jobs": asset((0, 0, 0)), "next": asset((60, 80, 180)), "apple": asset((180, 40, 40)), "phone": asset((20, 180, 20)), "phone:transform": asset((200, 180, 20))}
    before = compose_semantic_stage_frame(background, assets, transformed, 4300)
    after = compose_semantic_stage_frame(background, assets, transformed, 4950)
    assert np.asarray(before)[150, 310, 1] > np.asarray(before)[150, 310, 0]
    assert np.asarray(after)[150, 310, 0] > 150


def test_reveal_animates_from_invisible_to_full_size() -> None:
    data = stage().to_dict()
    data["events"] = [data["events"][0]]
    reveal_stage = build_semantic_stage(data)
    background = Image.new("RGBA", (640, 360), (240, 235, 220, 255))
    assets = {"jobs": asset((0, 0, 0)), "next": asset((60, 80, 180)), "apple": asset((180, 40, 40))}
    start = np.asarray(compose_semantic_stage_frame(background, assets, reveal_stage, 0))
    middle = np.asarray(compose_semantic_stage_frame(background, assets, reveal_stage, 250))
    end = np.asarray(compose_semantic_stage_frame(background, assets, reveal_stage, 600))
    background_pixels = np.asarray(background.convert("RGB"))
    assert np.count_nonzero(np.any(start != background_pixels, axis=2)) == 0
    assert np.count_nonzero(np.any(middle != background_pixels, axis=2)) > 0
    assert np.count_nonzero(np.any(middle != background_pixels, axis=2)) < np.count_nonzero(
        np.any(end != background_pixels, axis=2)
    )


def test_disconnect_removes_edge_and_focus_dims_previous_entity() -> None:
    data = stage().to_dict()
    data["events"].extend(
        [
            {"event_id": "disconnect", "start_ms": 4500, "duration_ms": 200, "action": "disconnect", "source": "apple", "target": "next", "label": "", "to_x": None, "to_y": None, "metadata": {}},
            {"event_id": "focus", "start_ms": 4700, "duration_ms": 200, "action": "focus", "target": "apple", "source": "", "label": "", "to_x": None, "to_y": None, "metadata": {}},
        ]
    )
    updated = build_semantic_stage(data)
    background = Image.new("RGBA", (640, 360), (240, 235, 220, 255))
    assets = {"jobs": asset((0, 0, 0)), "next": asset((60, 80, 180)), "apple": asset((180, 40, 40))}
    connected = np.asarray(compose_semantic_stage_frame(background, assets, updated, 4400))
    focused = np.asarray(compose_semantic_stage_frame(background, assets, updated, 5000))
    assert np.count_nonzero(np.any(connected != focused, axis=2)) > 100
    assert np.mean(np.abs(focused.astype(int) - connected.astype(int))) > 1.0
