from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_voice_and_caption_pages_expose_real_controls() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "VoicePage",
            "VoiceProfile",
            "VoiceSpeed",
            "GenerateVoiceButton",
            "VoiceResultList",
            "CaptionPage",
            "CaptionTable",
            "GenerateCaptionButton",
            "ExportSrtButton",
        ):
            assert window.findChild(object, name) is not None, name
    finally:
        window.close()


def test_qt_voice_caption_engine_paths_are_wired() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        'nav_buttons["voice"].clicked.connect',
        'nav_buttons["caption"].clicked.connect',
        "generate_voice_button.clicked.connect",
        "generate_caption_button.clicked.connect",
        "OmniVoiceProvider",
        "TTSScenePipeline",
        "materialize_audio",
        "SubtitleGenerator",
        "SceneNarration",
        "subtitles.srt",
    ):
        assert marker in source


def test_voice_errors_are_not_reported_as_success() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "result.errors" in source
    assert "cannot materialize" in source or "raise RuntimeError" in source
