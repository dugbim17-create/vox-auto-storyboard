# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for auto-storyboard-vox.

Builds a single-folder EXE with all app modules, config, and presets bundled.
External deps (ffmpeg, ffprobe) are expected on PATH at runtime.
"""

import os
import sys
from pathlib import Path

block_cipher = None

ROOT = os.path.abspath(".")

# All app.* and workers.* modules as hidden imports
hidden_imports = [
    # app core
    "app", "app.cli", "app.config", "app.settings", "app.runtime_settings", "app.version",
    "app.gui_native", "app.gui_qt", "app.ui_qt",
    "app.ui_qt.theme", "app.ui_qt.components", "app.ui_qt.main_window",
    "app.api",
    "app.core", "app.core.job_runner", "app.core.state_machine",
    "app.models", "app.models.asset", "app.models.project",
    "app.models.quiz_project", "app.models.scene", "app.models.state",
    "app.providers", "app.providers.base",
    "app.providers.image", "app.providers.image.antigravity",
    "app.providers.image.cliproxy_image", "app.providers.image.flowkit",
    "app.providers.llm", "app.providers.llm.cliproxy",
    "app.providers.motion",
    "app.providers.tts", "app.providers.tts.omnivoice",
    "app.render",
    "app.schemas", "app.schemas.motion_plan", "app.schemas.storyboard", "app.schemas.quiz",
    "app.services", "app.services.bgm_service",
    "app.services.ffmpeg_compiler", "app.services.final_composer",
    "app.services.image_generation", "app.services.ken_burns_validator",
    "app.services.layer_validator", "app.services.layer_workflow",
    "app.services.motion_planner", "app.services.motion_templates",
    "app.services.project_manager", "app.services.prompts",
    "app.services.scene_audio_mux", "app.services.scene_image_prompt",
    "app.services.scene_renderer", "app.services.script_analysis",
    "app.services.segmentation", "app.services.subtitle_generator",
    "app.services.text_layout", "app.services.transition_service",
    "app.services.tts_pipeline", "app.services.vi_normalize",
    "app.services.voice_profiles", "app.services.quiz_timeline",
    "app.services.quiz_renderer", "app.services.quiz_research",
    "app.services.quiz_pilot", "app.services.quiz_question_unit",
    "app.storage", "app.storage.asset_store",
    "app.storage.database", "app.storage.repositories",
    "app.tooling", "app.tooling.doctor",
    "tkinter", "_tkinter",
    "PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    # workers
    "workers", "workers.omnivoice_worker", "workers.omnivoice_worker.main",
    # web app
    "app.api.web_app", "app.launcher",
    # common deps that PyInstaller may miss
    "pydantic", "pydantic_settings", "pydantic.deprecated.decorator",
    "sqlalchemy", "sqlalchemy.dialects.sqlite",
    "httpx", "httpx._transports.default",
    "structlog", "structlog.stdlib", "structlog.dev",
    "tenacity",
    "PIL", "PIL.Image",
    "numpy",
    "cv2",
    "jsonschema", "jsonschema.validators",
    "yaml",
    "uvicorn",
    "fastapi",
]

# Data files to bundle alongside the EXE
datas = [
    (os.path.join(ROOT, "config"), "config"),
    (os.path.join(ROOT, "presets"), "presets"),
    (os.path.join(ROOT, ".env.example"), "."),
]

python_root = Path(sys.executable).resolve().parents[3]
python_tcl_root = python_root / "Python311" / "tcl"
for tk_dir in (python_tcl_root / "tcl8.6", python_tcl_root / "tk8.6"):
    if tk_dir.is_dir():
        datas.append((str(tk_dir), str(Path("tcl") / tk_dir.name)))

a = Analysis(
    [os.path.join(ROOT, "app", "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests", "pytest", "ruff", "coverage",
        # Heavy libs NOT needed by auto-storyboard
        "torch", "torchvision", "torchaudio", "torchtext",
        "transformers", "diffusers", "safetensors", "accelerate",
        "scipy", "sklearn", "skimage", "scikit_learn", "scikit_image",
        "onnxruntime", "onnx",
        "pandas", "botocore", "boto3", "s3transfer",
        "llvmlite", "numba",
        "av",
        "lxml",
        "matplotlib",
        "IPython", "jupyter", "notebook",
        "cryptography",
        "hf_xet", "huggingface_hub",
        "tokenizers",
        "wandb",
        "yt_dlp",
        "manim",
        "Pythonwin", "pythoncom",
        "win32com", "win32api",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="vox-studio-v0.5.4",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="vox-studio-v0.5.4",
)
