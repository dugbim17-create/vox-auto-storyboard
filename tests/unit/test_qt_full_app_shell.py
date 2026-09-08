from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_full_app_shell_exposes_complete_production_navigation() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    expected = {
        "overview": "Tổng quan",
        "projects": "Dự án",
        "script": "Kịch bản",
        "storyboard": "Storyboard",
        "quiz": "Quiz",
        "voice": "Giọng đọc",
        "visuals": "Hình ảnh",
        "music": "Nhạc",
        "video": "Video",
        "queue": "Hàng đợi",
        "acceptance": "Nghiệm thu",
        "publish": "Xuất bản",
        "settings": "Cài đặt",
    }
    try:
        assert set(expected).issubset(window.nav_buttons)
        for key, label in expected.items():
            assert label in window.nav_buttons[key].text()
        assert window.page_stack.currentWidget() is window.overview_page
        assert window.nav_buttons["overview"].property("active") is True
    finally:
        window.close()


def test_every_full_shell_navigation_item_owns_a_reachable_page() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    routes = (
        "overview",
        "projects",
        "script",
        "storyboard",
        "quiz",
        "voice",
        "visuals",
        "music",
        "video",
        "queue",
        "acceptance",
        "publish",
        "settings",
    )
    try:
        for route in routes:
            window.show_page(route)
            assert window.page_stack.currentWidget() is window.pages[route], route
            assert window.nav_buttons[route].property("active") is True
    finally:
        window.close()


def test_overview_has_one_primary_next_action_and_truthful_stage_state() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        primary = window.overview_page.findChildren(QPushButton)
        primary = [button for button in primary if button.property("kind") == "primary"]
        assert len(primary) == 1
        assert primary[0].objectName() == "OverviewNextActionButton"
        assert primary[0].text() == "Bắt đầu từ kịch bản"
        assert window.new_project_button.property("kind") != "primary"
        assert "Chưa chọn dự án" in window.overview_project_state.text()
        assert "Nguồn nội dung" in window.overview_workflow_text.text()
        assert "Nghiệm thu" in window.overview_workflow_text.text()
    finally:
        window.close()


def test_local_media_modules_are_truthful_project_gated_surfaces() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        for route in ("music", "video", "queue", "publish"):
            page = window.pages[route]
            assert page is not None, route
        assert not window.queue_music_button.isEnabled()
        assert not window.queue_video_button.isEnabled()
        assert not window.run_queue_button.isEnabled()
        assert not window.prepare_publish_button.isEnabled()
        assert "Không upload" in " ".join(
            label.text() for label in window.publish_page.findChildren(QLabel)
        )
        assert "0 network" in window.publish_status.text().lower()
    finally:
        window.close()


def test_existing_production_widgets_survive_full_shell_redesign() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "GenerateScriptButton",
            "CreateStoryboardButton",
            "GenerateImagesButton",
            "GenerateVoiceButton",
            "RenderQuizButton",
            "RenderFinalButton",
            "TechnicalLog",
        ):
            assert window.findChild(object, name) is not None, name
    finally:
        window.close()
