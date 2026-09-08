from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui_qt.main_window import VoxStudioWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_music_video_queue_and_publish_are_real_project_gated_surfaces() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        for name in (
            "MusicSourcePath",
            "BrowseMusicButton",
            "QueueMusicButton",
            "MusicStatus",
            "VideoSourcePath",
            "BrowseVideoButton",
            "QueueVideoButton",
            "VideoStatus",
            "MediaQueueTable",
            "RunQueueButton",
            "RecoverQueueButton",
            "PublishSourcePath",
            "PreparePublishButton",
            "PublishStatus",
        ):
            assert window.findChild(object, name) is not None, name
        assert not window.queue_music_button.isEnabled()
        assert not window.queue_video_button.isEnabled()
        assert not window.run_queue_button.isEnabled()
        assert not window.prepare_publish_button.isEnabled()
        assert "0 network" in window.publish_status.text().lower()
    finally:
        window.close()


def test_selected_project_enables_local_media_actions_and_can_render_queue_rows() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_media_project_ready(True)
        assert window.queue_music_button.isEnabled()
        assert window.queue_video_button.isEnabled()
        assert window.run_queue_button.isEnabled()
        assert window.prepare_publish_button.isEnabled()

        window.set_media_queue_rows(
            [
                {
                    "job_id": "media_001",
                    "action": "import_music",
                    "status": "succeeded",
                    "attempts": 1,
                    "result": "D:/project/audio/imported.mp3",
                    "error": "",
                }
            ]
        )
        assert window.media_queue_table.rowCount() == 1
        assert window.media_queue_table.item(0, 1).text() == "import_music"
        assert window.media_queue_table.item(0, 2).text() == "succeeded"
    finally:
        window.close()


def test_local_media_pages_replace_unavailable_placeholders() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        for route in ("music", "video", "queue", "publish"):
            window.show_page(route)
            assert window.page_stack.currentWidget() is window.pages[route]
        assert window.music_page.objectName() == "MusicPage"
        assert window.video_page.objectName() == "VideoPage"
        assert window.queue_page.objectName() == "MediaQueuePage"
        assert window.publish_page.objectName() == "PublishPage"
    finally:
        window.close()


def test_project_load_updates_overview_identity_and_clear_resets_it() -> None:
    _app()
    window = VoxStudioWindow(autoload=False)
    try:
        window.set_project_content(
            {
                "project_id": "prj_media",
                "title": "Media acceptance",
                "status": "INGESTED",
            },
            [],
        )
        assert "Media acceptance" in window.overview_project_state.text()
        assert "INGESTED" in window.overview_project_state.text()
        window.clear_project_content()
        assert "Chưa chọn dự án" in window.overview_project_state.text()
    finally:
        window.close()
