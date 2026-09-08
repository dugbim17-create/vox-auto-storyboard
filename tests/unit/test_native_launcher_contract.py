from __future__ import annotations

from pathlib import Path


def test_launcher_defaults_to_native_gui_and_web_is_explicit() -> None:
    text = Path("app/launcher.py").read_text(encoding="utf-8-sig")
    assert "if argv == [\"--web\"]" in text
    assert "from app.gui_qt import launch_qt" in text
    assert "launch_qt()" in text
    assert "webbrowser.open(url)" in text


def test_legacy_tk_shell_remains_available_as_rollback() -> None:
    text = Path("app/gui_native.py").read_text(encoding="utf-8-sig")
    for label in ("Projects", "Script", "Visuals", "Vox Style", "Voice", "Caption", "Render"):
        assert f'"{label}"' in text
    assert "class SettingsDialog" in text
    assert "CLIProxy Base URL" in text
    assert "FlowKit Base URL" in text
    assert "Image provider" in text
    assert "Vox Studio v" in text


def test_spec_bundles_native_and_image_provider_modules() -> None:
    text = Path("auto_storyboard.spec").read_text(encoding="utf-8-sig")
    for module in ("app.gui_native", "app.runtime_settings", "app.providers.image.flowkit", "app.providers.image.cliproxy_image"):
        assert module in text


def test_image_service_can_select_flowkit_or_cliproxy_provider() -> None:
    text = Path("app/services/image_generation.py").read_text(encoding="utf-8-sig")
    assert '"flowkit"' in text
    assert '"cliproxy_image"' in text
    assert "flowkit_provider" in text
    assert "cliproxy_provider" in text


def test_native_primary_actions_have_real_service_methods() -> None:
    text = Path("app/gui_native.py").read_text(encoding="utf-8-sig")
    for name in ("_generate_images", "_save_style", "_generate_voice", "_generate_caption", "_render_project"):
        assert f"def {name}" in text
    assert "phase style action" not in text
    assert "future-phase" not in text
