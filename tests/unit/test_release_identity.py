from pathlib import Path

from app.version import APP_VERSION


def test_style_complete_release_identity_and_resources() -> None:
    spec = Path("auto_storyboard_v070.spec").read_text(encoding="utf-8")

    assert APP_VERSION == "0.7.0"
    assert 'name="vox-studio-v0.7.0"' in spec
    assert "storyboard.schema.json" in spec
    assert "prompts" in spec
    for package in ("rembg", "onnxruntime", "scipy", "skimage", "pooch", "pymatting"):
        assert f'"{package}"' in spec
    for module in (
        "app.models.quiz_project",
        "app.services.quiz_pilot",
        "app.services.quiz_question_unit",
        "app.services.quiz_research",
        "app.ui_qt.main_window",
        "app.services.local_media_workflow",
        "app.services.apply_style_service",
        "app.services.artifact_freshness",
        "app.services.render_coordinator",
        "app.services.render_lineage",
        "app.services.style_project_service",
        "app.services.style_resolver",
    ):
        assert module in spec
    assert Path("presets/quiz_30_vi_verified.json").is_file()


def test_live_rollback_candidates_remain_side_by_side() -> None:
    for version in ("0.5.7", "0.5.8"):
        assert Path(f"auto_storyboard_v{version.replace('.', '')}.spec").is_file()
        candidate = Path(f"dist/vox-studio-v{version}")
        if candidate.exists():
            assert candidate.is_dir()
            assert (candidate / f"vox-studio-v{version}.exe").is_file()


def test_current_candidate_path_matches_release_identity() -> None:
    candidate = Path(f"dist/vox-studio-v{APP_VERSION}")
    if not candidate.exists():
        return
    assert candidate.is_dir()
    assert (candidate / f"vox-studio-v{APP_VERSION}.exe").is_file()
    assert not (candidate / f"vox-studio-v{APP_VERSION}").exists()
