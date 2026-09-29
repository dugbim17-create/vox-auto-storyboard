# -*- mode: python ; coding: utf-8 -*-
"""Side-by-side v0.7.0 PyInstaller spec for Vox Studio Pro Max."""

import os
import sys
from pathlib import Path

block_cipher = None
ROOT = os.path.abspath(".")

hidden_imports = [
    "app", "app.cli", "app.config", "app.settings", "app.runtime_settings", "app.version",
    "app.gui_native", "app.gui_qt", "app.ui_qt", "app.ui_qt.theme", "app.ui_qt.components",
    "app.ui_qt.main_window", "app.api", "app.api.web_app", "app.launcher",
    "app.core", "app.core.job_runner", "app.core.state_machine",
    "app.models", "app.models.asset", "app.models.project", "app.models.quiz_project", "app.models.scene", "app.models.state",
    "app.providers", "app.providers.base", "app.providers.image", "app.providers.image.antigravity",
    "app.providers.image.cliproxy_image", "app.providers.image.flowkit",
    "app.providers.llm", "app.providers.llm.cliproxy", "app.providers.tts", "app.providers.tts.omnivoice",
    "app.render", "app.schemas", "app.schemas.motion_plan", "app.schemas.storyboard",
    "app.schemas.visual_events", "app.services", "app.services.ffmpeg_compiler",
    "app.services.final_composer", "app.services.image_generation", "app.services.layer_workflow",
    "app.services.local_media_workflow", "app.services.apply_style_service", "app.services.artifact_freshness",
    "app.services.motion_planner", "app.services.motion_templates", "app.services.project_manager",
    "app.services.render_coordinator", "app.services.render_lineage", "app.services.scene_renderer",
    "app.services.subtitle_generator", "app.services.visual_event_assets",
    "app.services.visual_event_renderer", "app.services.visual_event_scene_renderer",
    "app.services.visual_stage_lineage", "app.services.visual_stage_pipeline",
    "app.services.vox_asset_pack", "app.services.vox_event_stage", "app.services.vox_production_pipeline",
    "app.services.canonical_visual_planner", "app.services.semantic_scene_renderer",
    "app.schemas.semantic_scene", "app.schemas.semantic_visual_stage",
    "app.services.vox_scene_planner", "app.services.style_project_service", "app.services.style_resolver",
    "app.services.quiz_pilot", "app.services.quiz_question_unit", "app.services.quiz_research",
    "app.services.paper_craft", "app.services.document_highlighter", "app.services.sfx_service",
    "app.services.tactical_radar", "app.services.micro_beat_planner", "app.services.investigation_board",
    "app.services.vox_auto_pipeline",
    "app.storage", "app.storage.asset_store", "app.storage.database", "app.storage.repositories",
    "workers", "workers.omnivoice_worker", "workers.omnivoice_worker.main",
    "tkinter", "_tkinter", "PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "pydantic", "pydantic_settings", "sqlalchemy", "sqlalchemy.dialects.sqlite", "httpx",
    "structlog", "tenacity", "PIL", "PIL.Image", "numpy", "cv2", "jsonschema", "yaml",
    "uvicorn", "fastapi",
]

from PyInstaller.utils.hooks import collect_all

RUNTIME_PACKAGES = ("rembg", "onnxruntime", "scipy", "skimage", "pooch", "pymatting", "numpy", "piper")
runtime_datas = []
runtime_binaries = []
for package in RUNTIME_PACKAGES:
    package_datas, package_binaries, package_hidden = collect_all(package)
    runtime_datas += package_datas
    runtime_binaries += package_binaries
    hidden_imports += package_hidden

datas = [
    (os.path.join(ROOT, "config"), "config"),
    (os.path.join(ROOT, "presets"), "presets"),
    (os.path.join(ROOT, "prompts"), "prompts"),
    (os.path.join(ROOT, "app", "schemas", "storyboard.schema.json"), os.path.join("app", "schemas")),
    (os.path.join(ROOT, ".env.example"), "."),
] + runtime_datas

python_root = Path(sys.executable).resolve().parents[3]
for tk_dir in (python_root / "Python311" / "tcl" / "tcl8.6", python_root / "Python311" / "tcl" / "tk8.6"):
    if tk_dir.is_dir():
        datas.append((str(tk_dir), str(Path("tcl") / tk_dir.name)))

a = Analysis(
    [os.path.join(ROOT, "app", "launcher.py")],
    pathex=[ROOT],
    binaries=runtime_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests", "pytest", "ruff", "coverage", "torch", "torchvision", "torchaudio", "transformers",
        "diffusers", "safetensors", "accelerate", "sklearn",
        "onnx", "pandas", "botocore", "boto3", "matplotlib", "IPython", "jupyter", "yt_dlp",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="vox-studio-v0.7.0",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False,
    upx_exclude=[], name="vox-studio-v0.7.0-pro",
)
