from pathlib import Path


def test_every_sidebar_navigation_control_is_classified() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    for key in ("projects", "script", "visuals", "style", "voice", "caption", "render"):
        assert f'nav_buttons["{key}"].clicked.connect' in source


def test_guide_button_is_not_an_unwired_qpushbutton() -> None:
    window = Path("app/ui_qt/main_window.py").read_text(encoding="utf-8-sig")
    controller = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "GuideButton" in window
    assert "guide_button.clicked.connect" in controller
    assert "Hướng dẫn workflow" in controller


def test_blocked_library_controls_are_explicit_not_mock_success() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "Assets · Chưa sẵn sàng" in source
    assert "Templates · Chưa sẵn sàng" in source
    assert "đang bị chặn trung thực" in source
