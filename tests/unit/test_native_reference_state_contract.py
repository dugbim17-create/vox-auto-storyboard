from pathlib import Path


def test_reference_state_variables_and_actions_are_present() -> None:
    source = Path("app/gui_native.py").read_text(encoding="utf-8-sig")
    for marker in (
        "topic_var",
        "selected_scene_var",
        "prompt_var",
        "style_var",
        "voice_var",
        "caption_enabled_var",
        "render_ratio_var",
        "render_resolution_var",
        "selected_image_asset_id",
        "self.prompt_var.set(self.visual_prompt.get",
        "self._run_async(\"generate_images\"",
    ):
        assert marker in source


def test_primary_reference_buttons_have_service_or_truthful_recovery() -> None:
    source = Path("app/gui_native.py").read_text(encoding="utf-8-sig")
    assert "Tạo ảnh" in source and "command=self.generate_images" in source
    assert "Tạo voice" in source and "command=self.generate_voice" in source
    assert "Tạo caption" in source and "command=self.generate_caption" in source
    assert "Render video" in source and "command=self.render_project" in source
    assert "cần tạo và chọn asset thật trước" in source
    assert "Tải ảnh: chưa có asset được chọn" in source


def test_reference_shell_keeps_legacy_web_as_explicit_only() -> None:
    source = Path("app/launcher.py").read_text(encoding="utf-8-sig")
    assert 'if argv == ["--web"]' in source
    assert "launch_qt()" in source
    assert "webbrowser.open(url)" in source
    assert "if not argv" not in source
