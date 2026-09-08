from pathlib import Path


def test_existing_project_storyboard_path_saves_before_plan_instead_of_recreating() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "if self.project_id:" in source
    assert "manager.save_script(self.project_id, topic)" in source
    assert "manager.get_project(self.project_id)" in source


def test_new_project_storyboard_path_creates_then_plans() -> None:
    source = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "manager.create_project(" in source
    assert "result = await manager.plan(" in source


def test_provider_label_is_not_hardcoded_ready() -> None:
    source = Path("app/ui_qt/main_window.py").read_text(encoding="utf-8-sig")
    assert "CLIProxy sẵn sàng" not in source
    assert "ProviderStatus" in source
    controller = Path("app/gui_qt.py").read_text(encoding="utf-8-sig")
    assert "def _check_provider_health" in controller
    assert ".health()" in controller
