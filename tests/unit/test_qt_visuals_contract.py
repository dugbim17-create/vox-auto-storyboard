from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_visuals_page_exposes_scene_prompt_generate_and_asset_selection() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "PageStack",
            "VisualsPage",
            "VisualSceneList",
            "VisualPromptEditor",
            "SavePromptButton",
            "GenerateImagesButton",
            "GeneratedAssetList",
            "UseImageButton",
            "ImagePreview",
        ):
            assert window.findChild(object, name) is not None, name
    finally:
        window.close()


def test_qt_visual_navigation_and_engine_actions_are_wired() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for marker in (
        'nav_buttons["visuals"].clicked.connect',
        "visual_scene_list.currentRowChanged.connect",
        "save_prompt_button.clicked.connect",
        "generate_images_button.clicked.connect",
        "use_image_button.clicked.connect",
        "VisualProjectService",
        "ImageGenerationService",
        "AssetRepo.list",
        "SceneRepo.set_selected_image",
    ):
        assert marker in source


def test_qt_visuals_has_no_demo_asset_success() -> None:
    source = Path("app/ui_qt/main_window.py").read_text(encoding="utf-8-sig")
    assert "ẢNH ĐÃ TẠO" in source
    assert "Chưa có ảnh được tạo" in source
    assert "qt_asset_demo" not in source
