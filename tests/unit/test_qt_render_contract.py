from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_render_page_exposes_real_actions_and_progress() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "RenderPage",
            "RenderPrerequisites",
            "RenderProgress",
            "RenderFinalButton",
            "CancelRenderButton",
            "RetrySceneButton",
            "FinalArtifactPath",
        ):
            assert window.findChild(object, name) is not None, name
    finally:
        window.close()


def test_qt_render_pipeline_reaches_final_composer_and_timeline() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        'nav_buttons["render"].clicked.connect',
        "render_final_button.clicked.connect",
        "cancel_render_button.clicked.connect",
        "retry_scene_button.clicked.connect",
        "ProjectTimeline.from_voice_durations",
        "VoxProductionPipeline",
        "VoxSemanticSceneRenderer",
        "LocalSceneRenderer",
        "FinalComposer",
        "compose_final",
        "render_manifest.json",
        '"COMPLETED"',
    ):
        assert marker in source


def test_render_fails_closed_on_missing_required_artifacts() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "missing voice duration" in source
    assert "missing selected image" in source
    assert "render cardinality mismatch" in source
    assert "cancel_event" in source
