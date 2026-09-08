from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_style_page_exposes_freshness_and_regeneration_controls() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "StyleFreshnessSummary",
            "RegenerateStyleSceneButton",
            "RegenerateAllStyleImagesButton",
        ):
            assert window.findChild(object, name) is not None, name
        assert window.regenerate_style_scene_button.text() == "Tạo lại scene hiện tại"
        assert window.regenerate_all_style_images_button.text() == "Tạo lại tất cả ảnh"
    finally:
        window.close()


def test_style_content_shows_applied_hashes_and_freshness_counts() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_style_content(
            {"style_preset": "editorial_collage"},
            {
                "preset": "editorial_collage",
                "style_revision": 3,
                "visual_hash": "visual-1234567890",
                "motion_hash": "motion-1234567890",
                "render_theme_hash": "theme-1234567890",
                "visual_language": "blue documentary",
                "palette": ["navy", "white"],
                "texture": ["film grain"],
                "freshness": {"fresh": 2, "stale": 3, "unknown": 1, "missing": 4},
            },
        )
        assert "visual-12345" in window.style_preview.text()
        assert "motion-12345" in window.style_preview.text()
        assert "fresh=2" in window.style_freshness_summary.text()
        assert "stale=3" in window.style_freshness_summary.text()
        assert "unknown=1" in window.style_freshness_summary.text()
        assert "missing=4" in window.style_freshness_summary.text()
    finally:
        window.close()


def test_bulk_regeneration_button_truthfully_shows_provider_call_budget() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_style_regeneration_budget(scene_count=4, role_count=5)
        assert "20 provider calls" in window.regenerate_all_style_images_button.text()
        assert window.regenerate_all_style_images_button.toolTip()
    finally:
        window.close()
