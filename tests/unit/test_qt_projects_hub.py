from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication
from app.ui_qt.main_window import VoxStudioWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_projects_hub_components_exist(qapp):
    window = VoxStudioWindow()
    assert hasattr(window, "projects_table")
    assert hasattr(window, "project_search_input")
    assert hasattr(window, "project_status_filter")
    assert hasattr(window, "refresh_projects_button")
    assert hasattr(window, "create_project_action_button")
    assert hasattr(window, "project_count_label")
    assert hasattr(window, "proj_inspector_title")
    assert hasattr(window, "proj_open_workspace_button")
    assert hasattr(window, "proj_open_folder_button")
    assert hasattr(window, "proj_play_video_button")


def test_projects_hub_populate_and_selection(qapp):
    window = VoxStudioWindow()
    sample_data = [
        {
            "project_id": "prj_001",
            "title": "Bí Ẩn Hố Đen",
            "status": "COMPLETED",
            "scenes_count": 5,
            "created_at": "2026-09-10 12:00",
            "has_video": True,
            "video_path": "output/fake.mp4",
            "script_text": "Kịch bản về hố đen vũ trụ...",
            "dir_path": "projects/prj_001",
        },
        {
            "project_id": "prj_002",
            "title": "Chiến Tranh Thế Giới",
            "status": "INGESTED",
            "scenes_count": 0,
            "created_at": "2026-09-09 10:00",
            "has_video": False,
            "video_path": "",
            "script_text": "Kịch bản thế chiến...",
            "dir_path": "projects/prj_002",
        },
    ]
    window.set_projects_hub_data(sample_data)
    assert window.projects_table.rowCount() == 2
    assert "2 dự án" in window.project_count_label.text()

    # Initial selection should be row 0
    assert window.proj_inspector_title.text() == "Bí Ẩn Hố Đen"
    assert "prj_001" in window.proj_inspector_id.text()
    assert "COMPLETED" in window.proj_inspector_status_badge.text()
    assert window.proj_open_workspace_button.isEnabled() is True

    # Switch selection to row 1
    window.set_inspector_project(sample_data[1])
    assert window.proj_inspector_title.text() == "Chiến Tranh Thế Giới"
    assert "prj_002" in window.proj_inspector_id.text()
    assert window.proj_play_video_button.isEnabled() is False


def test_projects_hub_filtering(qapp):
    window = VoxStudioWindow()
    sample_data = [
        {
            "project_id": "prj_001",
            "title": "Bí Ẩn Hố Đen",
            "status": "COMPLETED",
            "scenes_count": 5,
            "has_video": True,
        },
        {
            "project_id": "prj_002",
            "title": "Đại Dương Sâu Thẳm",
            "status": "INGESTED",
            "scenes_count": 2,
            "has_video": False,
        },
        {
            "project_id": "prj_003",
            "title": "Hệ Mặt Trời",
            "status": "IMAGES_READY",
            "scenes_count": 4,
            "has_video": False,
        },
    ]
    window.set_projects_hub_data(sample_data)
    assert window.projects_table.rowCount() == 3

    # Filter by search text
    window.filter_projects_hub("Hố Đen")
    assert window.projects_table.rowCount() == 1
    assert window.projects_table.item(0, 0).text() == "prj_001"

    # Reset search, filter by status
    window.filter_projects_hub("", "ingested")
    assert window.projects_table.rowCount() == 1
    assert window.projects_table.item(0, 0).text() == "prj_002"

    # Reset all filters
    window.filter_projects_hub("", "")
    assert window.projects_table.rowCount() == 3
