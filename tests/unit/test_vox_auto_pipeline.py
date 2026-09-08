"""Unit tests for VoxAutoPipeline 1-click autonomous engine."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.services.vox_auto_pipeline import VoxAutoPipeline


def test_vox_auto_pipeline_initializes_with_defaults(tmp_path: Path) -> None:
    pipeline = VoxAutoPipeline(output_base_dir=tmp_path)
    assert pipeline.fps == 30
    assert pipeline.output_base_dir == tmp_path
