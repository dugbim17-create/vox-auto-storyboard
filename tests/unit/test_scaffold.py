"""Smoke tests for the P0-T01 repository scaffold.

These only assert that the scaffold required by MASTER_PLAN section 4 exists and
is importable. Real unit tests arrive from P0-T02 onward.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_DIRS = [
    "app/api",
    "app/core",
    "app/models",
    "app/schemas",
    "app/providers/llm",
    "app/providers/image",
    "app/providers/tts",
    "app/providers/motion",
    "app/services",
    "app/render",
    "app/storage",
    "workers/omnivoice_worker",
    "prompts",
    "presets",
    "scripts",
    "tests/unit",
    "tests/integration",
    "tests/e2e",
    "tests/fixtures",
    "projects",
    "config/discovered",
]

EXPECTED_FILES = [
    "pyproject.toml",
    ".env.example",
    ".gitignore",
    "README.md",
    "MASTER_PROGRESS.md",
    "MASTER_PLAN_AUTO_STORYBOARD_VOX_WORKFLOW.md",
]


def test_expected_directories_exist() -> None:
    missing = [d for d in EXPECTED_DIRS if not (REPO_ROOT / d).is_dir()]
    assert not missing, f"missing directories: {missing}"


def test_expected_files_exist() -> None:
    missing = [f for f in EXPECTED_FILES if not (REPO_ROOT / f).is_file()]
    assert not missing, f"missing files: {missing}"


def test_app_package_importable() -> None:
    import app  # noqa: F401

    assert app.__name__ == "app"


def test_env_example_has_no_hardcoded_venv() -> None:
    """MASTER_PLAN forbids hard-coding venv paths in source.

    .env.example is allowed to carry placeholder values, but must not contain a
    real absolute path.
    """
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "C:/PATH/TO/" in text, "expected placeholder token to remain a placeholder"
    assert "Scripts/python.exe" in text
