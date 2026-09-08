from pathlib import Path

UI_PATH = Path("app/gui_native.py")


def test_reference_workflow_labels_are_present_in_native_shell() -> None:
    source = UI_PATH.read_text(encoding="utf-8-sig")
    required = (
        "CHỦ ĐỀ / Ý TƯỞNG",
        "KỊCH BẢN",
        "PHÂN TÍCH NỘI DUNG",
        "DANH SÁCH CẢNH",
        "PROMPT CHO CẢNH",
        "ẢNH ĐÃ TẠO",
        "KẾT QUẢ",
        "CHỌN STYLE",
        "TÙY CHỈNH STYLE HIỆN TẠI",
        "TẠO VOICE",
        "KẾT QUẢ VOICE",
        "CAPTION TỰ ĐỘNG",
        "THIẾT LẬP RENDER",
        "XEM TRƯỚC",
        "TIẾN TRÌNH RENDER",
    )
    missing = [label for label in required if label not in source]
    assert not missing, f"reference UI labels missing: {missing}"


def test_native_views_are_dense_reference_workspaces_not_placeholders() -> None:
    source = UI_PATH.read_text(encoding="utf-8-sig")
    for builder in (
        "_make_script_view",
        "_make_visuals_view",
        "_make_style_view",
        "_make_voice_view",
        "_make_render_view",
    ):
        assert f"def {builder}" in source
    assert "_make_placeholder_view(\"Visuals\"" not in source
    assert "_make_placeholder_view(\"Voice\"" not in source
    assert "_make_placeholder_view(\"Render\"" not in source
    assert "download_selected_image" in source
    assert "use_selected_image" in source
    assert "export_caption" in source


def test_reference_shell_exposes_reusable_visual_components() -> None:
    source = UI_PATH.read_text(encoding="utf-8-sig")
    for marker in (
        "scene rail",
        "analysis panel",
        "generated results",
        "style preset",
        "caption table",
        "render stages",
    ):
        assert marker in source.lower(), f"missing reusable component marker: {marker}"
