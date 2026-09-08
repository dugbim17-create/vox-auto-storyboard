from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_qt_theme_uses_media_production_design_tokens() -> None:
    from app.ui_qt.theme import TOKENS, build_stylesheet

    assert TOKENS["canvas"] == "#08090A"
    assert TOKENS["sidebar"] == "#0D0E12"
    assert TOKENS["surface"] == "#121319"
    assert TOKENS["accent"] == "#705CF6"
    assert TOKENS["danger"] == "#F05252"
    assert TOKENS["success"] == "#35C48D"
    stylesheet = build_stylesheet()
    for marker in ("QFrame#Card", "QPushButton#PrimaryButton", "QListWidget#SceneList", "QFrame#AnalysisCard"):
        assert marker in stylesheet


def test_qt_script_shell_matches_reference_structure() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        assert window.objectName() == "VoxStudioWindow"
        assert window.minimumWidth() >= 1180
        assert window.findChild(type(window.sidebar), "Sidebar") is not None
        for name in (
            "NewProjectButton",
            "WorkflowNav",
            "ProjectSelector",
            "TopicInput",
            "GenerateScriptButton",
            "SceneList",
            "AnalysisCard",
            "TitleSuggestions",
            "GlobalStatusBar",
        ):
            assert window.findChild(object, name) is not None, name
        assert window.scene_list.count() == 0
        assert window.analysis_grid.rowCount() >= 4
    finally:
        window.close()


def test_qt_shell_has_visual_hierarchy_not_flat_ttk_layout() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        assert window.sidebar.width() >= 230
        assert window.analysis_card.minimumWidth() >= 285
        assert window.topic_card.property("elevation") == "raised"
        assert window.script_card.property("elevation") == "raised"
        assert window.generate_script_button.property("kind") == "primary"
        assert window.saved_badge.text() == "Chưa tải project"
        assert window.findChild(object, "PageHero") is None
    finally:
        window.close()


def test_qt_shell_removes_redundant_account_and_page_hero_sections() -> None:
    _app()
    from app.ui_qt.main_window import VoxStudioWindow

    window = VoxStudioWindow(autoload=False)
    try:
        labels = [label.text() for label in window.findChildren(type(window.saved_badge))]
        assert "Vox User" not in labels
        assert "Pro workspace" not in labels
        assert "Dung lượng" not in labels
        assert "TAB 2 / 6  ·  SCRIPT" not in labels
        assert "AI viết kịch bản" not in labels
        assert "1 / 6" not in labels
        assert window.generate_script_button.parent() is window.topic_card
    finally:
        window.close()
