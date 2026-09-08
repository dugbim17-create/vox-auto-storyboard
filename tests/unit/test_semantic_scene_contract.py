from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from app.schemas.editorial_timeline import VoiceTimeline, WordTiming
from app.schemas.semantic_scene import build_semantic_scene_spec
from app.services.semantic_scene_compiler import compile_semantic_scene
from app.services.semantic_scene_renderer import render_semantic_frame


def test_character_scene_compiles_pose_action_from_measured_narration_anchor() -> None:
    voice = VoiceTimeline.build(
        scene_id="P01",
        duration_ms=2400,
        fps=30,
        words=(
            WordTiming("The", 0, 180),
            WordTiming("character", 200, 500),
            WordTiming("activates", 540, 850),
            WordTiming("the", 870, 990),
            WordTiming("machine", 1010, 1320),
            WordTiming("now", 1500, 1800),
        ),
    )
    spec = build_semantic_scene_spec(
        {
            "schema_version": "vox.scene/1.0",
            "project_id": "semantic-pilot",
            "scene_id": "P01",
            "revision": 1,
            "seed": 42001,
            "grammar": "character_demonstration",
            "duration_ms": 2400,
            "fps": 30,
            "motion_fps": 12,
            "assets": [
                {"asset_id": "character_neutral", "role": "subject", "kind": "rgba_image", "path": "neutral.png", "sha256": "a" * 64},
                {"asset_id": "character_operate", "role": "subject", "kind": "rgba_image", "path": "operate.png", "sha256": "b" * 64},
                {"asset_id": "machine", "role": "object", "kind": "rgba_image", "path": "machine.png", "sha256": "c" * 64},
            ],
            "beats": [
                {
                    "beat_id": "operate",
                    "anchor": "activates the machine",
                    "purpose": "action",
                    "hold_policy": "action_required",
                    "actions": [
                        {
                            "action_id": "operate_pose",
                            "type": "pose_sequence",
                            "subject": "character_neutral",
                            "variants": ["character_neutral", "character_operate"],
                            "end_state": "character_operate",
                            "duration_ms": 900,
                        }
                    ],
                }
            ],
        }
    )

    compiled = compile_semantic_scene(spec, voice)

    action = compiled["procedural_actions"][0]
    assert action["type"] == "pose_sequence"
    assert action["start_ms"] == 540
    assert action["end_ms"] == 1440
    assert action["start_frame"] == 16
    assert action["end_frame"] == 43
    assert compiled["scene_spec_sha256"] == spec.sha256


def test_pose_sequence_changes_character_and_machine_pixels_independently(tmp_path: Path) -> None:
    background = Image.new("RGBA", (320, 180), "#eee4ce")
    neutral = Image.new("RGBA", (80, 120), (0, 0, 0, 0))
    ImageDraw.Draw(neutral).rectangle((20, 15, 60, 115), fill="#222222")
    operate = Image.new("RGBA", (80, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(operate)
    draw.rectangle((20, 15, 60, 115), fill="#222222")
    draw.line((40, 50, 78, 28), fill="#cf2637", width=8)
    machine = Image.new("RGBA", (90, 80), (0, 0, 0, 0))
    ImageDraw.Draw(machine).rectangle((5, 10, 85, 75), fill="#525b66")
    paths = {}
    for name, image in {"bg": background, "neutral": neutral, "operate": operate, "machine": machine}.items():
        path = tmp_path / f"{name}.png"
        image.save(path)
        paths[name] = str(path)
    plan = {
        "duration_ms": 2000,
        "fps": 30,
        "motion_fps": 12,
        "canvas": {"width": 320, "height": 180},
        "assets": {
            "background": paths["bg"],
            "character_neutral": paths["neutral"],
            "character_operate": paths["operate"],
            "machine": paths["machine"],
        },
        "placements": {
            "character_neutral": [45, 45],
            "character_operate": [45, 45],
            "machine": [190, 70],
        },
        "procedural_actions": [
            {
                "action_id": "operate",
                "type": "pose_sequence",
                "subject": "character_neutral",
                "variants": ["character_neutral", "character_operate"],
                "start_ms": 500,
                "end_ms": 1400,
            },
            {
                "action_id": "activate",
                "type": "state_swap",
                "subject": "machine",
                "start_ms": 900,
                "end_ms": 1300,
                "active_tint": "#f6c445",
            },
        ],
    }

    before = render_semantic_frame(plan, 300)
    during = render_semantic_frame(plan, 1000)

    assert before.getpixel((120, 73)) != during.getpixel((120, 73))
    assert before.getpixel((230, 105)) != during.getpixel((230, 105))
    assert before.getpixel((10, 10)) == during.getpixel((10, 10))


def test_map_route_draws_progressively_and_moves_marker(tmp_path: Path) -> None:
    background = Image.new("RGBA", (320, 180), "#d9d2bf")
    marker = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
    ImageDraw.Draw(marker).ellipse((1, 1, 17, 17), fill="#cf2637")
    bg_path = tmp_path / "map.png"
    marker_path = tmp_path / "marker.png"
    background.save(bg_path)
    marker.save(marker_path)
    plan = {
        "canvas": {"width": 320, "height": 180},
        "assets": {"background": str(bg_path), "route_marker": str(marker_path)},
        "placements": {"route_marker": [0, 0]},
        "procedural_actions": [
            {
                "action_id": "route",
                "type": "path_draw",
                "subject": "route_marker",
                "path": [[35, 135], [120, 50], [270, 95]],
                "start_ms": 200,
                "end_ms": 1600,
                "color": "#161616",
                "width": 6,
            },
            {
                "action_id": "marker",
                "type": "traveling_marker",
                "subject": "route_marker",
                "path": [[35, 135], [120, 50], [270, 95]],
                "start_ms": 200,
                "end_ms": 1600,
            },
        ],
    }

    early = render_semantic_frame(plan, 450)
    late = render_semantic_frame(plan, 1450)

    assert early.getpixel((45, 125)) != background.convert("RGB").getpixel((45, 125))
    assert early.getpixel((245, 88)) == background.convert("RGB").getpixel((245, 88))
    assert late.getpixel((245, 88)) != background.convert("RGB").getpixel((245, 88))
    def red_centroid(image: Image.Image) -> tuple[float, float]:
        points = [
            (x, y)
            for y in range(image.height)
            for x in range(image.width)
            if (lambda pixel: pixel[0] > 150 and pixel[0] > pixel[1] * 1.8)(image.getpixel((x, y)))
        ]
        return (
            sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points),
        )

    early_marker = red_centroid(early)
    late_marker = red_centroid(late)
    assert late_marker[0] - early_marker[0] > 120


def test_text_reveal_has_readable_visual_footprint(tmp_path: Path) -> None:
    background = Image.new("RGBA", (640, 360), "#e9e0cb")
    background_path = tmp_path / "background.png"
    background.save(background_path)
    plan = {
        "canvas": {"width": 640, "height": 360},
        "assets": {"background": str(background_path)},
        "placements": {},
        "procedural_actions": [
            {
                "action_id": "label",
                "type": "text_reveal",
                "text": "RESULT STATE — HOLD TO EXPLAIN",
                "position": [100, 280],
                "start_ms": 200,
                "end_ms": 800,
                "font_size": 24,
                "color": "#161616",
            }
        ],
    }

    before = render_semantic_frame(plan, 100)
    after = render_semantic_frame(plan, 900)
    changed = [
        (x, y)
        for y in range(after.height)
        for x in range(after.width)
        if before.getpixel((x, y)) != after.getpixel((x, y))
    ]

    assert max(x for x, _ in changed) - min(x for x, _ in changed) >= 300
    assert max(y for _, y in changed) - min(y for _, y in changed) >= 16


def test_object_path_is_absent_before_start_and_present_during_action(tmp_path: Path) -> None:
    background = Image.new("RGBA", (220, 120), "#f4f0e5")
    subject = Image.new("RGBA", (30, 30), "#cf2637")
    background_path = tmp_path / "background.png"
    subject_path = tmp_path / "subject.png"
    background.save(background_path)
    subject.save(subject_path)
    plan = {
        "canvas": {"width": 220, "height": 120},
        "assets": {"background": str(background_path), "subject": str(subject_path)},
        "placements": {},
        "procedural_actions": [{
            "type": "object_path",
            "subject": "subject",
            "path": [[20, 60], [190, 60]],
            "start_ms": 500,
            "end_ms": 1500,
        }],
    }

    before = render_semantic_frame(plan, 200)
    during = render_semantic_frame(plan, 900)

    assert ImageChops.difference(before, background.convert("RGB")).getbbox() is None
    assert ImageChops.difference(during, background.convert("RGB")).getbbox() is not None


def test_chart_series_draws_no_zero_height_baseline_before_start(tmp_path: Path) -> None:
    background = Image.new("RGBA", (220, 120), "#f4f0e5")
    background_path = tmp_path / "background.png"
    background.save(background_path)
    plan = {
        "canvas": {"width": 220, "height": 120},
        "assets": {"background": str(background_path)},
        "placements": {},
        "procedural_actions": [{
            "type": "chart_series",
            "values": [2, 5, 8],
            "origin": [20, 100],
            "start_ms": 500,
            "end_ms": 1500,
        }],
    }

    before = render_semantic_frame(plan, 200)

    assert ImageChops.difference(before, background.convert("RGB")).getbbox() is None
