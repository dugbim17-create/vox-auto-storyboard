"""Tests for ken_burns_validator (P6-T06)."""

from __future__ import annotations

import pytest

from app.services.ken_burns_validator import (
    KenBurnsError,
    validate,
    validate_or_raise,
)


def _one_layer_zoom_plan() -> dict:
    """Single layer with only scale + translate. Classic Ken Burns."""
    return {
        "scene_id": "scene_001",
        "duration_ms": 5000,
        "fps": 30,
        "canvas": {"width": 1920, "height": 1080},
        "camera": {},
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "x": [[0, 0], [5000, -20]],
                    "scale": [[0, 1.0], [5000, 1.06]],
                },
            }
        ],
        "text_animations": [],
        "effects": [],
    }


def _layered_motion_plan() -> dict:
    """Multi-layer plan with camera + subject + text. Not Ken Burns."""
    return {
        "scene_id": "scene_001",
        "duration_ms": 5000,
        "fps": 30,
        "canvas": {"width": 1920, "height": 1080},
        "camera": {
            "x": [[0, 0], [5000, -12]],
            "scale": [[0, 1.0], [5000, 1.025]],
        },
        "layers": [
            {
                "id": "background",
                "asset_role": "background",
                "z": 0,
                "transform": {
                    "x": [[0, 0], [5000, -20]],
                    "scale": [[0, 1.0], [5000, 1.04]],
                },
            },
            {
                "id": "subject",
                "asset_role": "subject",
                "z": 20,
                "transform": {
                    "x": [[0, -100], [500, 0], [5000, 14]],
                    "y": [[0, 20], [500, 0]],
                },
            },
        ],
        "text_animations": [
            {"text": "HEADLINE", "enter": "pop", "start_ms": 200}
        ],
        "effects": [{"type": "paper_grain", "amount": 0.12}],
    }


class TestOneLayerZoomFails:
    def test_is_ken_burns(self):
        result = validate(_one_layer_zoom_plan())
        assert result.is_ken_burns is True
        assert result.layer_count == 1

    def test_validate_or_raise(self):
        with pytest.raises(KenBurnsError, match="Ken Burns"):
            validate_or_raise(_one_layer_zoom_plan())


class TestLayeredMotionPasses:
    def test_not_ken_burns(self):
        result = validate(_layered_motion_plan())
        assert result.is_ken_burns is False
        assert result.layer_count >= 2
        assert result.transform_tracks >= 3
        assert result.has_local_event is True

    def test_validate_or_raise_no_error(self):
        result = validate_or_raise(_layered_motion_plan())
        assert result.is_ken_burns is False


class TestTwoLayersNoText:
    def test_two_layers_no_events_tracks_low(self):
        plan = {
            "scene_id": "scene_001",
            "duration_ms": 5000,
            "fps": 30,
            "canvas": {"width": 1920, "height": 1080},
            "camera": {},
            "layers": [
                {"id": "bg", "z": 0, "transform": {"scale": [[0, 1], [5000, 1.02]]}},
                {"id": "fg", "z": 10, "transform": {"x": [[0, 0], [5000, 10]]}},
            ],
            "text_animations": [],
            "effects": [],
        }
        result = validate(plan)
        # 2 layers but only 2 transform tracks + no events = Ken Burns
        assert result.is_ken_burns is True
        assert result.has_local_event is False


class TestEffectsCountAsEvent:
    def test_effects_only(self):
        plan = {
            "scene_id": "s1",
            "duration_ms": 5000,
            "fps": 30,
            "canvas": {"width": 1920, "height": 1080},
            "camera": {"x": [[0, 0], [5000, 10]], "y": [[0, 0], [5000, 5]]},
            "layers": [
                {"id": "bg", "z": 0, "transform": {"x": [[0, 0], [5000, -20]]}},
                {"id": "sub", "z": 10, "transform": {"x": [[0, -50], [5000, 0]],
                                                      "scale": [[0, 0.9], [5000, 1.0]]}},
            ],
            "text_animations": [],
            "effects": [{"type": "film_grain", "amount": 0.1}],
        }
        result = validate(plan)
        assert result.has_local_event is True


class TestTextAnimationsCountAsEvent:
    def test_text_anim_only(self):
        plan = {
            "scene_id": "s1",
            "duration_ms": 5000,
            "fps": 30,
            "canvas": {"width": 1920, "height": 1080},
            "camera": {"x": [[0, 0], [5000, 10]], "scale": [[0, 1], [5000, 1.02]]},
            "layers": [
                {"id": "bg", "z": 0, "transform": {"x": [[0, 0], [5000, -20]]}},
                {"id": "sub", "z": 10, "transform": {"y": [[0, 10], [5000, 0]]}},
            ],
            "text_animations": [{"text": "TITLE", "enter": "fade"}],
            "effects": [],
        }
        result = validate(plan)
        assert result.has_local_event is True


class TestEmptyPlan:
    def test_empty_is_ken_burns(self):
        result = validate({})
        assert result.is_ken_burns is True
        assert result.layer_count == 0
        assert result.transform_tracks == 0
        assert result.has_local_event is False

    def test_reasons_populated(self):
        result = validate({})
        assert len(result.reasons) >= 3
