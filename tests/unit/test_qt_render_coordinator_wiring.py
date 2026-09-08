from __future__ import annotations

from pathlib import Path


def test_qt_final_render_uses_shared_render_coordinator() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "RenderCoordinator" in source
    assert "coordinator.render_scene" in source
    render_slice = source[source.index("async def _render_final_async") : source.index("def _save_script", source.index("async def _render_final_async"))]
    assert "renderer.render_scene" not in render_slice


def test_qt_motion_manifest_uses_style_lineage_envelope() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    render_slice = source[source.index("async def _render_final_async") : source.index("def _save_script", source.index("async def _render_final_async"))]
    assert "VoxProductionPipeline" in render_slice
    assert "prepared.canonical_scenes" in render_slice
    assert "VoxSemanticSceneRenderer" in render_slice
    pipeline_source = Path("app/services/vox_production_pipeline.py").read_text(encoding="utf-8-sig")
    assert "build_motion_lineage_envelope" in pipeline_source
    assert "write_lineage_manifest" in pipeline_source
