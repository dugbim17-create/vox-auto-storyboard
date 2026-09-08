"""Tests for transition_service (P8-T03)."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from app.services.transition_service import (
    TransitionService,
)


class FakeRunner:
    def __init__(self, rc: int = 0) -> None:
        self.rc = rc
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_: Any) -> Any:
        self.calls.append(list(cmd))
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-transition-output")

        class P:
            returncode = self.rc
            stderr = ""
        return P()


@pytest.fixture()
def scenes(tmp_path: Path) -> list[Path]:
    files = []
    for i in range(3):
        f = tmp_path / f"scene_{i+1:03d}.mp4"
        f.write_bytes(b"fake-video")
        files.append(f)
    return files


class TestHardCut:
    def test_hard_cut_is_concat(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner)
        result = svc.apply_transitions(
            scenes, ["hard_cut", "hard_cut"], tmp_path / "out.mp4"
        )
        assert result.output_path.is_file()
        assert result.transition_count == 0
        cmd = runner.calls[0]
        assert "concat" in cmd


class TestCrossfade:
    def test_crossfade_has_xfade(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner, scene_duration_ms=5000)
        result = svc.apply_transitions(
            scenes, ["crossfade", "crossfade"], tmp_path / "out.mp4"
        )
        assert result.transition_count == 2
        cmd_str = " ".join(runner.calls[0])
        assert "xfade" in cmd_str
        assert "transition=fade" in cmd_str


class TestPaperWipe:
    def test_paper_wipe_has_xfade(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner, scene_duration_ms=5000)
        result = svc.apply_transitions(
            scenes, ["paper_wipe", "paper_wipe"], tmp_path / "out.mp4"
        )
        assert result.transition_count == 2
        cmd_str = " ".join(runner.calls[0])
        assert "xfade" in cmd_str
        assert "transition=wipeleft" in cmd_str


class TestDipToColor:
    def test_dip_to_color_has_xfade(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner, scene_duration_ms=5000)
        svc.apply_transitions(
            scenes, ["dip_to_color", "hard_cut"], tmp_path / "out.mp4"
        )
        cmd_str = " ".join(runner.calls[0])
        assert "xfade" in cmd_str
        assert "fadeblack" in cmd_str


class TestFallback:
    def test_unknown_transition_falls_back_hard_cut(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner)
        result = svc.apply_transitions(
            scenes, ["banana_flip", "unknown"], tmp_path / "out.mp4"
        )
        # Unknown transitions resolve to hard_cut → concat.
        assert result.transition_count == 0


class TestSingleScene:
    def test_single_scene_no_transition(self, tmp_path: Path):
        scene = tmp_path / "only.mp4"
        scene.write_bytes(b"single")
        runner = FakeRunner()
        svc = TransitionService(runner=runner)
        result = svc.apply_transitions([scene], [], tmp_path / "out.mp4")
        assert result.transition_count == 0
        assert result.output_path.is_file()


class TestSafety:
    def test_no_shell_true(self):
        import app.services.transition_service as mod
        source = inspect.getsource(mod)
        assert "shell=True" not in source

    def test_command_is_list(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner, scene_duration_ms=5000)
        svc.apply_transitions(scenes, ["crossfade", "crossfade"], tmp_path / "out.mp4")
        assert isinstance(runner.calls[0], list)


class TestDurationAccounting:
    def test_total_duration_accounts_for_overlap(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(runner=runner, scene_duration_ms=5000)
        result = svc.apply_transitions(
            scenes, ["crossfade", "crossfade"], tmp_path / "out.mp4",
            transition_duration=0.34,
        )
        # 3 scenes × 5000ms - 2 × 340ms overlap = 14320ms
        assert result.total_duration_ms == 14320

    def test_variable_scene_durations_drive_total_duration(self, scenes: list[Path], tmp_path: Path):
        runner = FakeRunner()
        svc = TransitionService(
            runner=runner,
            scene_durations_ms=[3000, 5000, 7000],
        )
        result = svc.apply_transitions(
            scenes, ["hard_cut", "hard_cut"], tmp_path / "out.mp4"
        )
        assert result.total_duration_ms == 15000
