"""PySide6 entrypoint and thin service wiring for Vox Studio."""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.runtime_settings import load_runtime_settings, save_runtime_settings
from app.ui_qt.activity_log import ActivityLog, redact_log_text
from app.ui_qt.main_window import VoxStudioWindow
from app.ui_qt.settings_dialog import SettingsDialog


def resolve_packaged_resource(relative_path: str | Path) -> Path:
    """Resolve a bundled read-only resource without changing writable paths."""
    relative = Path(relative_path)
    source_path = Path.cwd() / relative
    if source_path.is_file():
        return source_path
    bundle_root = Path(str(getattr(sys, "_MEIPASS", Path.cwd())))
    bundled_path = bundle_root / relative
    if bundled_path.is_file():
        return bundled_path
    executable_path = Path(sys.executable).resolve().parent / "_internal" / relative
    return executable_path


def validate_image_generation_readback(
    outcome: Any,
    assets: list[Any],
) -> dict[str, Any]:
    """Require a successful engine outcome and a decodable selected asset."""
    if not bool(getattr(outcome, "ok", False)):
        raise RuntimeError(str(getattr(outcome, "error", "image generation failed")))
    selected_asset_id = str(getattr(outcome, "selected_asset_id", "") or "")
    if not selected_asset_id:
        raise RuntimeError("image generation produced no selected asset id")
    selected = next(
        (
            asset
            for asset in assets
            if bool(getattr(asset, "selected", False))
            and str(getattr(asset, "asset_id", "")) == selected_asset_id
        ),
        None,
    )
    if selected is None:
        raise RuntimeError(
            f"selected image asset not found after read-back: {selected_asset_id}"
        )
    path = Path(str(getattr(selected, "path", ""))).expanduser()
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"selected image file missing: {path}")
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.load()
            width, height = image.size
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"selected image is not decodable: {path}: {exc}") from exc
    return {
        "selected_asset_id": selected_asset_id,
        "selected_path": str(path),
        "width": int(width),
        "height": int(height),
        "generated": int(getattr(outcome, "generated", 0)),
        "cached": int(getattr(outcome, "cached", 0)),
    }


class QtWorkerBridge(QObject):
    """Run existing async/sync services outside the Qt UI thread."""

    succeeded = Signal(str, object)
    failed = Signal(str, str)
    activity = Signal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._active_count = 0
        self._active_lock = threading.Lock()

    @property
    def active_count(self) -> int:
        with self._active_lock:
            return self._active_count

    def run(self, label: str, function: Callable[[], Any]) -> None:
        with self._active_lock:
            self._active_count += 1

        def worker() -> None:
            started = time.monotonic()
            stopped = threading.Event()
            self.activity.emit("START", label, "Bắt đầu tác vụ")

            def heartbeat() -> None:
                while not stopped.wait(5.0):
                    elapsed = int(time.monotonic() - started)
                    self.activity.emit(
                        "INFO", label, f"heartbeat · đang xử lý ({elapsed}s)"
                    )

            threading.Thread(target=heartbeat, daemon=True).start()
            try:
                result = function()
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                elapsed = time.monotonic() - started
                self.activity.emit("DONE", label, f"Hoàn tất sau {elapsed:.1f}s")
                self.succeeded.emit(label, result)
            except Exception as exc:  # noqa: BLE001
                elapsed = time.monotonic() - started
                self.activity.emit(
                    "ERROR",
                    label,
                    f"{type(exc).__name__}: {exc} · elapsed={elapsed:.1f}s",
                )
                self.failed.emit(label, str(exc))
            finally:
                stopped.set()
                with self._active_lock:
                    self._active_count -= 1

        threading.Thread(target=worker, daemon=True).start()


class VoxQtApp:
    def __init__(
        self,
        window: VoxStudioWindow,
        *,
        start_provider_health: bool = True,
    ) -> None:
        self.window = window
        self.settings = load_runtime_settings()
        self.project_id: str | None = None
        self.quiz_document: dict[str, Any] | None = None
        self.semantic_pilot_final: Path | None = None
        self.cancel_event = threading.Event()
        self.activity_log = ActivityLog(Path("logs") / "vox-studio.log")
        self.bridge = QtWorkerBridge()
        self.bridge.succeeded.connect(self._on_success)
        self.bridge.failed.connect(self._on_failure)
        self.bridge.activity.connect(self._on_activity)
        self._connect_actions()
        self._load_projects()
        persisted = self.activity_log.read()
        if persisted:
            self.window.technical_log.setPlainText(persisted)
        if start_provider_health:
            self.bridge.run("provider_health", self._check_provider_health)

    def _connect_actions(self) -> None:
        self.window.new_project_button.clicked.connect(self._new_project)
        self.window.generate_script_button.clicked.connect(self._generate_script)
        self.window.auto_pipeline_button.clicked.connect(self._run_1click_auto_pipeline)
        self.window.project_selector.currentIndexChanged.connect(self._select_project)
        self.window.open_project_button.clicked.connect(self._open_selected_project)
        self.window.save_script_button.clicked.connect(self._save_script)
        self.window.create_storyboard_button.clicked.connect(self._create_storyboard)
        self.window.regenerate_storyboard_button.clicked.connect(self._create_storyboard)
        self.window.nav_buttons["overview"].clicked.connect(
            lambda: self.window.show_page("overview")
        )
        self.window.nav_buttons["projects"].clicked.connect(self._show_projects)
        self.window.nav_buttons["script"].clicked.connect(lambda: self.window.show_page("script"))
        self.window.nav_buttons["storyboard"].clicked.connect(
            lambda: self.window.show_page("storyboard")
        )
        self.window.nav_buttons["visuals"].clicked.connect(lambda: self.window.show_page("visuals"))
        self.window.nav_buttons["style"].clicked.connect(lambda: self.window.show_page("style"))
        self.window.nav_buttons["voice"].clicked.connect(lambda: self.window.show_page("voice"))
        self.window.nav_buttons["caption"].clicked.connect(lambda: self.window.show_page("caption"))
        self.window.nav_buttons["quiz"].clicked.connect(lambda: self.window.show_page("quiz"))
        self.window.nav_buttons["render"].clicked.connect(lambda: self.window.show_page("render"))
        self.window.nav_buttons["logs"].clicked.connect(lambda: self.window.show_page("logs"))
        for route in ("music", "video", "queue", "acceptance", "publish", "settings"):
            self.window.nav_buttons[route].clicked.connect(
                lambda checked=False, name=route: self.window.show_page(name)
            )
        self.window.overview_next_action_button.clicked.connect(
            lambda: self.window.show_page("script")
        )
        self.window.open_settings_from_page_button.clicked.connect(self._open_settings)
        self.window.browse_music_button.clicked.connect(self._browse_music)
        self.window.browse_video_button.clicked.connect(self._browse_video)
        self.window.browse_publish_button.clicked.connect(self._browse_publish)
        self.window.queue_music_button.clicked.connect(
            lambda: self._enqueue_local_media("import_music")
        )
        self.window.queue_video_button.clicked.connect(
            lambda: self._enqueue_local_media("import_video")
        )
        self.window.run_queue_button.clicked.connect(self._run_media_queue)
        self.window.recover_queue_button.clicked.connect(self._recover_media_queue)
        self.window.prepare_publish_button.clicked.connect(self._prepare_local_publish)
        self.window.visual_scene_list.currentRowChanged.connect(self._select_visual_scene)
        self.window.generated_asset_list.currentRowChanged.connect(self._preview_selected_asset)
        self.window.save_prompt_button.clicked.connect(self._save_visual_prompt)
        self.window.generate_images_button.clicked.connect(self._generate_scene_images)
        self.window.use_image_button.clicked.connect(self._use_selected_image)
        self.window.save_style_button.clicked.connect(self._save_style)
        self.window.apply_style_button.clicked.connect(self._apply_style)
        self.window.regenerate_style_scene_button.clicked.connect(
            self._regenerate_style_scene
        )
        self.window.regenerate_all_style_images_button.clicked.connect(
            self._regenerate_all_style_images
        )
        self.window.generate_voice_button.clicked.connect(self._generate_voice)
        self.window.generate_caption_button.clicked.connect(self._generate_caption)
        self.window.export_srt_button.clicked.connect(self._export_srt)
        self.window.load_quiz_button.clicked.connect(self._load_quiz)
        self.window.research_quiz_button.clicked.connect(self._research_quiz)
        self.window.save_quiz_draft_button.clicked.connect(self._save_quiz_draft)
        self.window.quiz_generate_assets_button.clicked.connect(self._generate_quiz_assets)
        self.window.approve_quiz_button.clicked.connect(self._approve_quiz)
        self.window.quiz_preview_button.clicked.connect(self._preview_quiz_style)
        self.window.quiz_save_style_button.clicked.connect(self._save_quiz_style)
        self.window.quiz_cancel_style_button.clicked.connect(self._cancel_quiz_style)
        self.window.quiz_question_table.currentCellChanged.connect(
            self._select_quiz_question
        )
        self.window.render_quiz_button.clicked.connect(self._render_quiz)
        self.window.render_final_button.clicked.connect(self._render_final)
        self.window.render_semantic_pilot_button.clicked.connect(
            self._render_semantic_pilot
        )
        self.window.open_semantic_pilot_button.clicked.connect(
            self._open_semantic_pilot
        )
        self.window.cancel_render_button.clicked.connect(self._cancel_render)
        self.window.retry_scene_button.clicked.connect(self._retry_selected_scene)
        self.window.settings_button.clicked.connect(self._open_settings)
        self.window.guide_button.clicked.connect(self._show_guide)
        self.window.clear_logs_button.clicked.connect(self._clear_logs)
        self.window.open_log_folder_button.clicked.connect(self._open_log_folder)
        if hasattr(self.window, "load_preset_quick_button"):
            self.window.load_preset_quick_button.clicked.connect(self._on_load_preset_quick)
        if hasattr(self.window, "open_output_folder_button"):
            self.window.open_output_folder_button.clicked.connect(self._on_open_quiz_output_folder)
        if hasattr(self.window, "play_latest_video_button"):
            self.window.play_latest_video_button.clicked.connect(self._on_play_latest_quiz_video)
        if hasattr(self.window, "paste_json_button"):
            self.window.paste_json_button.clicked.connect(self._on_paste_json_clicked)
        self.window.assets_button.clicked.connect(
            lambda: QMessageBox.information(
                self.window,
                "Assets · Chưa sẵn sàng",
                "Assets sẽ chỉ được bật khi có asset browser đọc từ AssetRepo.",
            )
        )
        self.window.templates_button.clicked.connect(
            lambda: QMessageBox.information(
                self.window,
                "Templates · Chưa sẵn sàng",
                "Templates chưa có repository contract nên đang bị chặn trung thực.",
            )
        )

    @Slot(str, str, str)
    def _on_activity(self, level: str, action: str, message: str) -> None:
        safe_message = redact_log_text(message)
        line = self.activity_log.write(level, action, safe_message)
        friendly = self._friendly_activity(level, action, safe_message)
        self.window.append_activity_log(friendly, line)

    @staticmethod
    def _friendly_activity(level: str, action: str, message: str) -> str:
        labels = {
            "generate_images": "Tạo ảnh",
            "save_prompt": "Lưu prompt",
            "plan": "Tạo storyboard",
            "generate_voice": "Tạo voice",
            "generate_caption": "Tạo caption",
            "render_final": "Render final",
            "provider_health": "Kiểm tra provider",
            "settings_health": "Kiểm tra toàn bộ provider",
        }
        label = labels.get(action, action.replace("_", " "))
        icons = {"START": "▶", "DONE": "✓", "ERROR": "✕", "INFO": "…"}
        return f"{icons.get(level, '•')} {label}: {message}"

    @Slot()
    def _clear_logs(self) -> None:
        self.window.clear_activity_logs()
        self.activity_log.clear()
        self.window.statusBar().showMessage("Đã xóa log ứng dụng")

    @Slot()
    def _open_log_folder(self) -> None:
        import os

        os.startfile(str(self.activity_log.path.parent.resolve()))

    @Slot()
    def _render_semantic_pilot(self) -> None:
        """Render a provider-free candidate into an isolated acceptance root."""
        from app.settings import get_data_root

        output_root = get_data_root() / "acceptance" / "semantic-v061"
        self.window.render_semantic_pilot_button.setEnabled(False)
        self.window.semantic_pilot_status.setText("Đang render 6 semantic scene...")
        self.bridge.run(
            "render_semantic_pilot",
            lambda: self._render_semantic_pilot_sync(output_root),
        )

    @staticmethod
    def _render_semantic_pilot_sync(output_root: Path) -> dict[str, Any]:
        import json

        from app.services.semantic_pilot import render_semantic_pilot

        result = render_semantic_pilot(output_root)
        final_path = Path(str(result.get("final_mp4") or ""))
        report_path = Path(str(result.get("qa_report") or ""))
        if not final_path.is_file() or not report_path.is_file():
            raise RuntimeError("semantic pilot artifact read-back failed")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "PASS" or int(result.get("provider_calls") or 0) != 0:
            raise RuntimeError("semantic pilot QA/provider gate failed")
        result["final_sha256"] = str((report.get("final") or {}).get("sha256") or "")
        return result

    @Slot()
    def _open_semantic_pilot(self) -> None:
        import os

        if self.semantic_pilot_final and self.semantic_pilot_final.is_file():
            os.startfile(str(self.semantic_pilot_final))

    @Slot()
    def _browse_music(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Chọn nhạc local", "", "Audio (*.mp3 *.wav *.m4a *.aac)"
        )
        if path:
            self.window.music_source_path.setText(path)

    @Slot()
    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Chọn video local", "", "Video (*.mp4 *.mov *.mkv)"
        )
        if path:
            self.window.video_source_path.setText(path)

    @Slot()
    def _browse_publish(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Chọn final MP4", "", "Video (*.mp4)"
        )
        if path:
            self.window.publish_source_path.setText(path)

    def _enqueue_local_media(self, action: str) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        field = (
            self.window.music_source_path
            if action == "import_music"
            else self.window.video_source_path
        )
        source = field.text().strip()
        if not source:
            QMessageBox.warning(self.window, "Thiếu file", "Hãy chọn file local trước.")
            return
        from app.services.local_media_workflow import DurableMediaQueue
        from app.storage import database

        database.init_schema()
        with database.create_session() as session:
            DurableMediaQueue(session).enqueue(
                project_id=str(self.project_id),
                action=action,
                payload={"source_path": source},
            )
            session.commit()
        self._refresh_media_queue()
        self.window.show_page("queue")
        self.window.statusBar().showMessage("Đã thêm vào hàng đợi local")

    @Slot()
    def _recover_media_queue(self) -> None:
        if not self.project_id:
            return
        from app.services.local_media_workflow import DurableMediaQueue
        from app.storage import database

        with database.create_session() as session:
            recovered = DurableMediaQueue(session).recover_interrupted()
            session.commit()
        self._refresh_media_queue()
        self.window.statusBar().showMessage(f"Đã khôi phục {recovered} job dở")

    @Slot()
    def _run_media_queue(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        self._set_busy(True, "Đang chạy một job local...")
        self.bridge.run("run_media_queue", self._run_media_queue_sync)

    def _run_media_queue_sync(self) -> dict[str, Any]:
        from app.services.local_media_workflow import (
            DurableMediaQueue,
            LocalMediaWorkflow,
        )
        from app.storage import database

        with database.create_session() as session:
            row = DurableMediaQueue(session).execute_next(
                workflow=LocalMediaWorkflow(
                    project_root=self.settings.project_root or None
                )
            )
            session.commit()
            if row is None:
                return {"status": "empty"}
            return {
                "job_id": row.job_id,
                "action": row.action,
                "status": row.status,
                "result_json": row.result_json,
                "error": row.error,
            }

    @Slot()
    def _prepare_local_publish(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        source = self.window.publish_source_path.text().strip()
        if not source:
            QMessageBox.warning(self.window, "Thiếu final.mp4", "Hãy chọn final.mp4.")
            return
        self._set_busy(True, "Đang chuẩn bị package local...")
        self.bridge.run(
            "prepare_local_publish",
            lambda: self._prepare_local_publish_sync(source),
        )

    def _prepare_local_publish_sync(self, source: str) -> dict[str, Any]:
        from app.services.local_media_workflow import LocalPublishPackager

        result = LocalPublishPackager(
            project_root=self.settings.project_root or None
        ).prepare(str(self.project_id), source)
        return {
            "video_path": str(result.video_path),
            "manifest_path": str(result.manifest_path),
            "sha256": result.sha256,
            "media": result.media,
            "network_calls": 0,
        }

    def _refresh_media_queue(self) -> None:
        if not self.project_id:
            self.window.set_media_queue_rows([])
            return
        import json

        from app.services.local_media_workflow import DurableMediaQueue
        from app.storage import database

        with database.create_session() as session:
            rows = DurableMediaQueue(session).list(project_id=str(self.project_id))
            payload = []
            for row in rows:
                result = json.loads(row.result_json) if row.result_json else {}
                payload.append(
                    {
                        "job_id": row.job_id,
                        "action": row.action,
                        "status": row.status,
                        "attempts": row.attempts,
                        "result": result,
                        "error": row.error,
                    }
                )
        self.window.set_media_queue_rows(payload)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        for button in (
            self.window.generate_script_button,
            self.window.save_script_button,
            self.window.create_storyboard_button,
            self.window.regenerate_storyboard_button,
            self.window.save_prompt_button,
            self.window.generate_images_button,
            self.window.use_image_button,
            self.window.save_style_button,
            self.window.generate_voice_button,
            self.window.generate_caption_button,
            self.window.export_srt_button,
            self.window.render_final_button,
            self.window.retry_scene_button,
        ):
            button.setEnabled(not busy)
        for button in (
            self.window.queue_music_button,
            self.window.queue_video_button,
            self.window.run_queue_button,
            self.window.recover_queue_button,
            self.window.prepare_publish_button,
        ):
            button.setEnabled(not busy and bool(self.project_id))
        if message:
            self.window.statusBar().showMessage(message)

    @Slot()
    def _show_projects(self) -> None:
        self._load_projects()
        self.window.show_page("script")
        self.window.project_selector.setFocus()
        self.window.statusBar().showMessage(
            "Dự án · Chọn project trong thanh trên hoặc tạo project mới"
        )

    @Slot()
    def _show_guide(self) -> None:
        QMessageBox.information(
            self.window,
            "Hướng dẫn workflow",
            "1. Tạo/mở project\n"
            "2. Lưu script và tạo storyboard\n"
            "3. Tạo/chọn ảnh thật cho từng scene\n"
            "4. Lưu style\n"
            "5. Tạo voice và caption\n"
            "6. Render final; pipeline sẽ kiểm tra đủ prerequisite.",
        )

    @Slot()
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.window)
        dialog.saved.connect(self._settings_saved)
        dialog.test_requested.connect(
            lambda settings: self.bridge.run(
                "settings_health",
                lambda: self._check_all_providers(settings),
            )
        )
        self._settings_dialog = dialog
        dialog.open()

    @Slot(object)
    def _settings_saved(self, settings: object) -> None:
        from app.runtime_settings import RuntimeSettings

        if not isinstance(settings, RuntimeSettings):
            return
        save_runtime_settings(settings)
        self.settings = settings
        self.window.voice_profile.setCurrentText(settings.voice_profile_id)
        self.window.statusBar().showMessage("Đã lưu Runtime Settings")
        self.bridge.run("provider_health", self._check_provider_health)

    async def _check_all_providers(self, settings: object) -> dict[str, Any]:
        from app.providers.image.cliproxy_image import CliproxyImageProvider
        from app.providers.image.flowkit import FlowKitImageProvider
        from app.providers.llm.cliproxy import CliproxyLLMProvider
        from app.providers.tts.omnivoice import OmniVoiceProvider
        from app.runtime_settings import RuntimeSettings

        if not isinstance(settings, RuntimeSettings):
            raise TypeError("invalid RuntimeSettings")
        llm = CliproxyLLMProvider(
            base_url=settings.cliproxy_base_url,
            model=settings.cliproxy_model,
            api_key=settings.cliproxy_api_key,
            timeout_seconds=min(settings.cliproxy_timeout_seconds, 20),
        )
        image = CliproxyImageProvider(
            base_url=settings.cliproxy_base_url,
            model="gpt-image-2",
            api_key=settings.cliproxy_api_key,
            timeout_seconds=min(settings.cliproxy_timeout_seconds, 20),
        )
        flowkit = FlowKitImageProvider(
            base_url=settings.flowkit_base_url,
            health_path=settings.flowkit_health_path,
            submit_path=settings.flowkit_submit_path,
            status_path_template=settings.flowkit_status_path_template,
            result_path_template=settings.flowkit_result_path_template,
            token=settings.flowkit_token,
            timeout_seconds=min(settings.flowkit_timeout_seconds, 20),
            poll_interval_seconds=settings.flowkit_poll_interval_seconds,
        )
        voice = OmniVoiceProvider(
            base_url=f"http://{settings.omnivoice_worker_host}:{settings.omnivoice_worker_port}",
            timeout_seconds=min(settings.omnivoice_timeout_seconds, 20),
        )
        try:
            llm_health, image_health, flowkit_health, voice_health = await asyncio.gather(
                llm.health(), image.health(), flowkit.health(), voice.health()
            )
            return {
                "llm": llm_health.status,
                "image": image_health.status,
                "flowkit": flowkit_health.status,
                "voice": voice_health.status,
            }
        finally:
            await llm.aclose()
            await image.aclose()
            await flowkit.aclose()
            await voice.aclose()

    def _load_projects(self) -> None:
        from app.storage import database
        from app.storage.repositories import ProjectRepo

        database.init_schema()
        with database.create_session() as session:
            projects = [
                {
                    "project_id": project.project_id,
                    "title": project.title,
                    "status": project.status,
                }
                for project in ProjectRepo.list(session)
            ]
        self.window.set_projects(projects, self.project_id)

    @Slot(int)
    def _select_project(self, _index: int) -> None:
        selected = self.window.project_selector.currentData()
        if selected:
            self._load_project(str(selected))
        else:
            self.project_id = None
            self.window.clear_project_content()
            self.window.set_media_project_ready(False)
            self.window.set_media_queue_rows([])
            self.window.statusBar().showMessage("Chưa chọn project")

    @Slot()
    def _open_selected_project(self) -> None:
        selected = self.window.project_selector.currentData()
        if not selected:
            QMessageBox.information(self.window, "Vox Studio", "Hãy chọn project cần mở.")
            return
        self._load_project(str(selected))

    def _load_project(self, project_id: str) -> None:
        from app.services.project_manager import ProjectManager
        from app.storage import database
        from app.storage.repositories import SceneRepo

        database.init_schema()
        with database.create_session() as session:
            project = ProjectManager(
                session,
                project_root=self.settings.project_root or None,
            ).get_project(project_id)
            script_text = project.get("script_text") or ""
            project["script_text"] = script_text
            scenes = [
                {
                    "scene_id": scene.scene_id,
                    "purpose": scene.purpose,
                    "narration_text": scene.narration_text,
                    "visual_summary": scene.visual_summary,
                    "estimated_duration_seconds": scene.estimated_duration_seconds,
                    "image_prompt": scene.image_prompt,
                }
                for scene in SceneRepo.list(session, project_id)
            ]
        self.project_id = project_id
        self.window.set_project_content(project, scenes)
        self.window.set_media_project_ready(True)
        self._recover_media_queue()
        from app.services.style_project_service import StyleProjectService

        style = StyleProjectService(
            project_root=self.settings.project_root or None,
        ).load(project_id)
        self.window.set_style_content(project, style)
        self.window.statusBar().showMessage(f"Đã mở project · {project.get('title') or project_id}")
        if scenes:
            self.window.visual_scene_list.setCurrentRow(0)

    @Slot(int)
    def _select_visual_scene(self, _row: int) -> None:
        scene_id = self.window.selected_visual_scene_id()
        if self.project_id and scene_id:
            self._refresh_visual_scene(scene_id)

    def _refresh_visual_scene(self, scene_id: str) -> None:
        from app.storage import database
        from app.storage.repositories import AssetRepo, SceneRepo

        with database.create_session() as session:
            scene = SceneRepo.get(session, str(self.project_id), scene_id)
            assets = AssetRepo.list(session, str(self.project_id), scene_id)
            scene_data = {
                "scene_id": scene.scene_id,
                "image_prompt": scene.image_prompt,
            } if scene is not None else {"scene_id": scene_id, "image_prompt": ""}
            asset_data = [
                {
                    "id": asset.id,
                    "asset_id": asset.asset_id,
                    "role": asset.role,
                    "path": asset.path,
                    "provider": asset.provider,
                    "version": asset.version,
                    "selected": asset.selected,
                }
                for asset in assets
            ]
        self.window.set_visual_scene(scene_data, asset_data)

    @Slot(int)
    def _preview_selected_asset(self, row: int) -> None:
        if row < 0:
            return
        item = self.window.generated_asset_list.item(row)
        asset = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if isinstance(asset, dict):
            self.window.set_image_preview(str(asset.get("path") or ""))

    @Slot()
    def _save_visual_prompt(self) -> None:
        scene_id = self.window.selected_visual_scene_id()
        prompt = self.window.visual_prompt_editor.toPlainText().strip()
        if not self.project_id or not scene_id:
            QMessageBox.warning(self.window, "Chưa chọn scene", "Hãy mở project và chọn scene.")
            return
        if not prompt:
            QMessageBox.warning(self.window, "Prompt rỗng", "Prompt ảnh không được để trống.")
            return
        self._set_busy(True, "Đang lưu prompt ảnh...")
        self.bridge.run("save_prompt", lambda: self._save_visual_prompt_sync(scene_id, prompt))

    def _save_visual_prompt_sync(self, scene_id: str, prompt: str) -> dict[str, Any]:
        from app.services.visual_project_service import VisualProjectService
        from app.storage import database
        from app.storage.repositories import SceneRepo

        VisualProjectService(
            project_root=self.settings.project_root or None,
        ).update_storyboard_prompt(str(self.project_id), scene_id, prompt)
        with database.create_session() as session:
            scene = SceneRepo.update_image_prompt(
                session,
                str(self.project_id),
                scene_id,
                prompt,
            )
            if scene is None:
                raise ValueError(f"scene not found: {scene_id}")
            session.commit()
        return {"scene_id": scene_id, "prompt": prompt}

    @Slot()
    def _generate_scene_images(self) -> None:
        scene_id = self.window.selected_visual_scene_id()
        if not self.project_id or not scene_id:
            QMessageBox.warning(self.window, "Chưa chọn scene", "Hãy mở project và chọn scene.")
            return
        prompt = self.window.visual_prompt_editor.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self.window, "Prompt rỗng", "Hãy nhập prompt ảnh trước.")
            return
        self._set_busy(True, "Đang tạo ảnh thật qua provider đã cấu hình...")
        self.bridge.run(
            "generate_images",
            lambda: self._generate_scene_images_async(scene_id, prompt),
        )

    async def _generate_scene_images_async(
        self,
        scene_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        from app.providers.image.antigravity import AntigravityImageProvider
        from app.providers.image.cliproxy_image import CliproxyImageProvider
        from app.providers.image.flowkit import FlowKitImageProvider
        from app.services.image_generation import ImageGenerationService
        from app.storage import database
        from app.storage.repositories import AssetRepo

        await asyncio.to_thread(self._save_visual_prompt_sync, scene_id, prompt)
        selected_provider = self.settings.image_provider
        if selected_provider == "auto":
            selected_provider = "flowkit" if self.settings.flowkit_enabled else "cliproxy_image"
        cliproxy = CliproxyImageProvider(
            base_url=self.settings.cliproxy_base_url,
            model="gpt-image-2",
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=self.settings.cliproxy_timeout_seconds,
        )
        flowkit = FlowKitImageProvider(
            base_url=self.settings.flowkit_base_url,
            health_path=self.settings.flowkit_health_path,
            submit_path=self.settings.flowkit_submit_path,
            status_path_template=self.settings.flowkit_status_path_template,
            result_path_template=self.settings.flowkit_result_path_template,
            token=self.settings.flowkit_token,
            timeout_seconds=self.settings.flowkit_timeout_seconds,
            poll_interval_seconds=self.settings.flowkit_poll_interval_seconds,
        )
        antigravity = AntigravityImageProvider(
            base_url=self.settings.antigravity_image_base_url,
            model=self.settings.antigravity_image_model,
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=self.settings.cliproxy_timeout_seconds,
        )
        primary = {
            "flowkit": flowkit,
            "cliproxy_image": cliproxy,
            "antigravity_image": antigravity,
        }[selected_provider]
        service = ImageGenerationService(
            primary,
            aspect_ratio=self.settings.default_aspect_ratio,
            project_root=self.settings.project_root or None,
            provider_name=selected_provider,
            flowkit_provider=flowkit,
            cliproxy_provider=cliproxy,
            model=str(getattr(primary, "model", "")),
        )
        try:
            with database.create_session() as session:
                outcome = await service.generate_scene(
                    str(self.project_id),
                    scene_id,
                    session,
                    project_root=self.settings.project_root or None,
                    provider_name=selected_provider,
                )
                # Expire the identity map and prove the selected artifact from
                # persisted rows before the GUI is allowed to report success.
                session.expire_all()
                assets = AssetRepo.list(session, str(self.project_id), scene_id)
                readback = validate_image_generation_readback(outcome, assets)
                return {
                    "scene_id": scene_id,
                    "provider": selected_provider,
                    **readback,
                }
        finally:
            await cliproxy.aclose()
            await flowkit.aclose()
            await antigravity.aclose()

    @Slot()
    def _use_selected_image(self) -> None:
        scene_id = self.window.selected_visual_scene_id()
        item = self.window.generated_asset_list.currentItem()
        asset = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not self.project_id or not scene_id or not isinstance(asset, dict):
            QMessageBox.warning(self.window, "Chưa chọn ảnh", "Hãy chọn một asset ảnh thật.")
            return
        from app.storage import database
        from app.storage.repositories import AssetRepo, SceneRepo

        with database.create_session() as session:
            assets = AssetRepo.list(session, str(self.project_id), scene_id)
            for row in assets:
                AssetRepo.set_selected(session, row.id, row.id == int(asset["id"]))
            SceneRepo.set_selected_image(
                session,
                str(self.project_id),
                scene_id,
                str(asset["asset_id"]),
            )
            session.commit()
        self._refresh_visual_scene(scene_id)
        self.window.statusBar().showMessage("Đã chọn asset ảnh và đọc lại scene")

    @Slot()
    def _regenerate_style_scene(self) -> None:
        scene_id = self.window.selected_visual_scene_id()
        if not self.project_id or not scene_id:
            QMessageBox.warning(self.window, "Chưa chọn scene", "Hãy mở project và chọn scene.")
            return
        prompt = self.window.visual_prompt_editor.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self.window, "Prompt rỗng", "Hãy nhập prompt ảnh trước.")
            return
        self.window.set_style_regeneration_running(True, current=0, total=1)
        self._set_busy(True, "Đang tạo lại ảnh cho scene hiện tại...")
        self.bridge.run(
            "generate_style_scene_images",
            lambda: self._generate_scene_images_async(scene_id, prompt),
        )

    @Slot()
    def _regenerate_all_style_images(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        scenes = list(getattr(self.window, "_visual_scenes", []) or [])
        scene_count = len(scenes)
        if scene_count <= 0:
            QMessageBox.warning(self.window, "Chưa có scene", "Project chưa có scene để tạo ảnh.")
            return
        message = self.window.style_regeneration_confirmation_text(
            scene_count=scene_count,
            role_count=5,
        )
        if QMessageBox.question(
            self.window,
            "Xác nhận provider calls",
            message,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.cancel_event.clear()
        self.window.set_style_regeneration_running(True, current=0, total=scene_count)
        self._set_busy(True, "Đang tạo lại tất cả ảnh theo style đã áp dụng...")
        self.bridge.run("generate_style_all_images", self._regenerate_all_style_images_async)

    async def _regenerate_all_style_images_async(self) -> dict[str, Any]:
        from app.providers.image.antigravity import AntigravityImageProvider
        from app.providers.image.cliproxy_image import CliproxyImageProvider
        from app.providers.image.flowkit import FlowKitImageProvider
        from app.services.image_generation import ImageGenerationService
        from app.storage import database
        from app.storage.repositories import AssetRepo, SceneRepo

        project_id = str(self.project_id)
        selected_provider = self.settings.image_provider
        if selected_provider == "auto":
            selected_provider = (
                "flowkit" if self.settings.flowkit_enabled else "cliproxy_image"
            )
        cliproxy = CliproxyImageProvider(
            base_url=self.settings.cliproxy_base_url,
            model="gpt-image-2",
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=self.settings.cliproxy_timeout_seconds,
        )
        flowkit = FlowKitImageProvider(
            base_url=self.settings.flowkit_base_url,
            health_path=self.settings.flowkit_health_path,
            submit_path=self.settings.flowkit_submit_path,
            status_path_template=self.settings.flowkit_status_path_template,
            result_path_template=self.settings.flowkit_result_path_template,
            token=self.settings.flowkit_token,
            timeout_seconds=self.settings.flowkit_timeout_seconds,
            poll_interval_seconds=self.settings.flowkit_poll_interval_seconds,
        )
        antigravity = AntigravityImageProvider(
            base_url=self.settings.antigravity_image_base_url,
            model=self.settings.antigravity_image_model,
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=self.settings.cliproxy_timeout_seconds,
        )
        primary = {
            "flowkit": flowkit,
            "cliproxy_image": cliproxy,
            "antigravity_image": antigravity,
        }[selected_provider]
        service = ImageGenerationService(
            primary,
            aspect_ratio=self.settings.default_aspect_ratio,
            project_root=self.settings.project_root or None,
            provider_name=selected_provider,
            flowkit_provider=flowkit,
            cliproxy_provider=cliproxy,
            fallback_provider=(
                antigravity if selected_provider != "antigravity_image" else None
            ),
            model=str(getattr(primary, "model", "")),
        )
        generated = 0
        cached = 0
        succeeded = 0
        errors: list[str] = []
        try:
            with database.create_session() as session:
                scenes = SceneRepo.list(session, project_id)
                total = len(scenes)
                for index, scene in enumerate(scenes, start=1):
                    if self.cancel_event.is_set():
                        break
                    outcome = await service.generate_scene(
                        project_id,
                        scene.scene_id,
                        session,
                        project_root=self.settings.project_root or None,
                        provider_name=selected_provider,
                    )
                    generated += outcome.generated
                    cached += outcome.cached
                    if outcome.ok:
                        succeeded += 1
                    else:
                        errors.append(f"{scene.scene_id}: {outcome.error}")
                    session.expire_all()
                    selected = AssetRepo.get_selected_for_scene(
                        session, project_id, scene.scene_id
                    )
                    self.bridge.activity.emit(
                        "INFO",
                        "generate_style_all_images",
                        (
                            f"{index}/{total} · {scene.scene_id} · "
                            f"generated={outcome.generated} cached={outcome.cached} · "
                            f"asset={getattr(selected, 'asset_id', '')}"
                        ),
                    )
            return {
                "project_id": project_id,
                "total": total,
                "succeeded": succeeded,
                "generated": generated,
                "cached": cached,
                "cancelled": self.cancel_event.is_set(),
                "errors": errors,
            }
        finally:
            await cliproxy.aclose()
            await flowkit.aclose()
            await antigravity.aclose()

    @Slot()
    def _save_style(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        item = self.window.style_preset_list.currentItem()
        preset = item.text() if item is not None else ""
        if not preset:
            QMessageBox.warning(self.window, "Thiếu style", "Hãy chọn một style preset.")
            return
        self._set_busy(True, "Đang lưu style project...")
        self.bridge.run("save_style", lambda: self._save_style_sync(preset))

    def _save_style_sync(self, preset: str) -> dict[str, Any]:
        from app.services.style_project_service import StyleProjectService
        from app.storage import database
        from app.storage.repositories import ProjectRepo

        with database.create_session() as session:
            style = StyleProjectService(
                project_root=self.settings.project_root or None,
            ).save_draft(
                str(self.project_id),
                session,
                preset=preset,
                visual_language=self.window.style_visual_language.text(),
                palette=self.window.style_palette.text(),
                texture=self.window.style_texture.text(),
            )
            project = ProjectRepo.get(session, str(self.project_id))
            return {
                "style": style,
                "project": {
                    "style_preset": project.style_preset if project else preset,
                },
            }

    @Slot()
    def _apply_style(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        self._set_busy(True, "Đang áp dụng style vào storyboard...")
        self.bridge.run("apply_style", self._apply_style_sync)

    def _apply_style_sync(self) -> dict[str, Any]:
        from app.services.apply_style_service import ApplyStyleService
        from app.services.prompts import load_presets
        from app.storage import database
        from app.storage.repositories import ProjectRepo

        with database.create_session() as session:
            applied = ApplyStyleService(
                project_root=self.settings.project_root or None,
                presets=load_presets(),
            ).apply(str(self.project_id), session)
            project = ProjectRepo.get(session, str(self.project_id))
            return {
                "style": applied,
                "project": {"style_preset": project.style_preset if project else applied["preset"]},
            }

    @Slot()
    def _generate_voice(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        self._set_busy(True, "Đang tạo WAV qua OmniVoice...")
        self.bridge.run("generate_voice", self._generate_voice_async)

    async def _generate_voice_async(self) -> dict[str, Any]:
        from app.providers.tts.omnivoice import OmniVoiceProvider
        from app.services.tts_pipeline import TTSScenePipeline
        from app.storage import database
        from app.storage.asset_store import AssetStore

        base_url = (
            f"http://{self.settings.omnivoice_worker_host}:"
            f"{self.settings.omnivoice_worker_port}"
        )
        provider = OmniVoiceProvider(
            base_url=base_url,
            timeout_seconds=self.settings.omnivoice_timeout_seconds,
        )
        pipeline = TTSScenePipeline(
            provider,
            voice_profile_id=self.window.voice_profile.currentText(),
            speed=float(self.window.voice_speed.value()),
        )
        try:
            health = await provider.health()
            if health.status != "ok":
                raise RuntimeError(f"OmniVoice unavailable: {health.detail}")
            with database.create_session() as session:
                result = await pipeline.run(
                    str(self.project_id),
                    session,
                    project_root=self.settings.project_root or None,
                )
                if result.errors:
                    raise RuntimeError("; ".join(result.errors))
                narration_path = AssetStore(
                    self.settings.project_root or None,
                ).subdir(str(self.project_id), "audio") / "narration.wav"
                pipeline.materialize_audio(result, narration_path)
                return {
                    "results": [item.__dict__ for item in result.scene_results],
                    "narration_path": str(narration_path),
                }
        finally:
            await provider.aclose()

    @Slot()
    def _generate_caption(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        self._set_busy(True, "Đang tạo SRT từ narration và voice timing...")
        self.bridge.run("generate_caption", self._generate_caption_sync)

    def _generate_caption_sync(self) -> dict[str, Any]:
        from app.services.subtitle_generator import SceneNarration, SubtitleGenerator
        from app.storage import database
        from app.storage.asset_store import AssetStore
        from app.storage.repositories import SceneRepo

        with database.create_session() as session:
            scenes = SceneRepo.list(session, str(self.project_id))
            narrations = []
            for scene in scenes:
                duration = int(scene.actual_voice_duration_ms or 0)
                if duration <= 0:
                    raise RuntimeError(
                        f"scene {scene.scene_id} chưa có voice duration; tạo voice trước"
                    )
                narrations.append(
                    SceneNarration(
                        scene_id=scene.scene_id,
                        narration=scene.narration_text,
                        voice_duration_ms=duration,
                        order=scene.order,
                    )
                )
        output = AssetStore(self.settings.project_root or None).subdir(
            str(self.project_id),
            "final",
        ) / "subtitles.srt"
        result = SubtitleGenerator().generate(str(self.project_id), narrations, output)
        entries = self._parse_srt(output)
        return {"result": result.__dict__, "entries": entries}

    @staticmethod
    def _parse_srt(path: Any) -> list[dict[str, Any]]:
        from pathlib import Path

        text = Path(path).read_text(encoding="utf-8")
        entries: list[dict[str, Any]] = []
        for block in text.strip().split("\n\n"):
            lines = block.splitlines()
            if len(lines) < 3 or " --> " not in lines[1]:
                continue
            start, end = lines[1].split(" --> ", 1)
            entries.append(
                {
                    "index": int(lines[0]),
                    "start": start,
                    "end": end,
                    "text": " ".join(lines[2:]),
                }
            )
        return entries

    @Slot()
    def _export_srt(self) -> None:
        from pathlib import Path

        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        from app.storage.asset_store import AssetStore

        path = AssetStore(self.settings.project_root or None).subdir(
            str(self.project_id),
            "final",
        ) / "subtitles.srt"
        if not path.is_file():
            QMessageBox.warning(self.window, "Chưa có SRT", "Hãy tạo caption trước.")
            return
        self.window.statusBar().showMessage(f"SRT: {Path(path)}")

    @Slot()
    def _research_quiz(self) -> None:
        topic = self.window.quiz_topic_input.text().strip()
        path = Path(self.window.quiz_file_path.text().strip()).expanduser()
        if not topic:
            QMessageBox.warning(self.window, "Thiếu chủ đề", "Hãy nhập chủ đề quiz.")
            return
        self.bridge.run("research_quiz", lambda: self._research_quiz_sync(topic, path))

    def _research_quiz_sync(self, topic: str, candidate_path: Path) -> dict[str, Any]:
        import hashlib
        import json

        from app.services.quiz_research import research_quiz_fixture
        from app.storage import database
        from app.storage.repositories import QuizProjectRepo

        normalized = " ".join(topic.casefold().split())
        project_id = f"quiz_{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]}"
        database.init_schema()
        with database.create_session() as session:
            existing = QuizProjectRepo.get_document(session, project_id)
            if existing is not None:
                return existing
            if not candidate_path.is_file():
                raise FileNotFoundError(f"candidate bank not found: {candidate_path}")
            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
            candidates = payload.get("questions") if isinstance(payload, dict) else payload
            if not isinstance(candidates, list):
                raise ValueError("candidate bank must contain questions")
            project = research_quiz_fixture(
                candidates, topic=topic, project_id=project_id
            ).project
            QuizProjectRepo.upsert(session, project)
            session.commit()
            readback = QuizProjectRepo.get_document(session, project_id)
            if readback is None:
                raise RuntimeError("quiz draft missing after save")
            return readback

    @Slot()
    def _save_quiz_draft(self) -> None:
        try:
            saved = self._save_quiz_draft_sync()
        except Exception as exc:  # noqa: BLE001
            self.window.quiz_status.setText(f"Lưu nháp lỗi: {exc}")
            return
        self.quiz_document = saved
        self.window.set_quiz_document(saved)

    def _save_quiz_draft_sync(self) -> dict[str, Any]:
        from app.schemas.quiz import validate_quiz_project
        from app.storage import database
        from app.storage.repositories import QuizProjectRepo

        if self.quiz_document is None:
            raise RuntimeError("quiz document is not loaded")
        if self.quiz_document.get("engine_v2"):
            from app.services.quiz_v2_runtime import save_document, load_document
            draft = self.window.read_quiz_review(self.quiz_document)
            path = save_document(draft, Path(self.window.quiz_output_dir.text().strip() or "output/quiz"))
            self.window.quiz_file_path.setText(str(path.resolve()))
            return load_document(path)
        draft = validate_quiz_project(self.window.read_quiz_review(self.quiz_document))
        with database.create_session() as session:
            QuizProjectRepo.upsert(session, draft)
            session.commit()
            readback = QuizProjectRepo.get_document(session, str(draft["project_id"]))
            if readback is None:
                raise RuntimeError("quiz draft missing after save")
            return readback

    @Slot()
    def _approve_quiz(self) -> None:
        try:
            if self.quiz_document and self.quiz_document.get("engine_v2"):
                import asyncio
                from app.services.quiz_asset_resolver import resolve_quiz_assets
                from app.services.quiz_v2_runtime import content_fingerprint
                draft = self.window.read_quiz_review(self.quiz_document)
                draft["questions"] = asyncio.run(resolve_quiz_assets(draft["questions"], Path(self.window.quiz_output_dir.text().strip() or "output/quiz") / "assets", allow_generation=False))
                before = content_fingerprint(draft)
                if not self.window.confirm_quiz_visual_review(draft):
                    return
                if content_fingerprint(draft) != before:
                    raise ValueError("Ảnh đã đổi trong khi review; hãy xem lại")
                self.quiz_document = draft
            approved = self._approve_quiz_sync()
        except Exception as exc:  # noqa: BLE001
            self.window.quiz_status.setText(f"Duyệt quiz lỗi: {exc}")
            return
        self.quiz_document = approved
        self.window.set_quiz_document(approved)

    def _approve_quiz_sync(self, *, approved_at: str | None = None) -> dict[str, Any]:
        from datetime import UTC, datetime

        from app.schemas.quiz import approve_quiz_project
        from app.storage import database
        from app.storage.repositories import QuizProjectRepo

        if self.quiz_document is None:
            raise RuntimeError("quiz document is not loaded")
        draft = self.window.read_quiz_review(self.quiz_document)
        if draft.get("engine_v2"):
            from app.services.quiz_v2_runtime import approve_document, save_document
            approved = approve_document(draft)
            path = save_document(approved, Path(self.window.quiz_output_dir.text().strip() or "output/quiz"))
            self.window.quiz_file_path.setText(str(path.resolve()))
            return approved
        approved = approve_quiz_project(
            draft, approved_at=approved_at or datetime.now(UTC).isoformat()
        )
        with database.create_session() as session:
            QuizProjectRepo.upsert(session, approved)
            session.commit()
            readback = QuizProjectRepo.get_document(session, str(approved["project_id"]))
            if readback is None:
                raise RuntimeError("approved quiz missing after save")
            return readback

    def _generate_quiz_assets(self) -> None:
        if not self.quiz_document or not self.quiz_document.get("engine_v2"):
            self.window.quiz_status.setText("Nạp JSON Quiz V2 trước khi sinh ảnh")
            return
        if QMessageBox.question(self.window, "Quyền sinh ảnh có phí", "Dùng gpt-image-2 qua CLIProxy, tối đa 6 request trong thư mục output này, tính cả lỗi. Không fallback model hoặc tự retry request chưa rõ kết quả. Tiếp tục?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        from copy import deepcopy
        document = deepcopy(self.window.read_quiz_review(self.quiz_document))
        output = Path(self.window.quiz_output_dir.text().strip() or "output/quiz")
        self.window.quiz_generate_assets_button.setEnabled(False)
        def work():
            from app.services.quiz_asset_resolver import resolve_quiz_assets
            from app.services.quiz_v2_runtime import save_document
            document["questions"] = asyncio.run(resolve_quiz_assets(document["questions"], output / "assets", image_model="gpt-image-2", allow_generation=True))
            document["approval"] = {"status": "draft"}
            path = save_document(document, output)
            return {"document": document, "path": str(path.resolve())}
        self.bridge.run("quiz_assets", work)

    @Slot()
    def _load_quiz(self) -> None:
        import json

        from app.schemas.quiz import validate_quiz_project

        path = resolve_packaged_resource(
            self.window.quiz_file_path.text().strip()
        ).expanduser()
        if not path.is_file():
            self.window.quiz_status.setText(f"Không tìm thấy quiz: {path}")
            return
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(document, dict) and document.get("engine_v2"):
                from app.services.quiz_v2_runtime import load_document
                self.quiz_document = load_document(path)
            else:
                self.quiz_document = validate_quiz_project(document)
        except Exception as exc:  # noqa: BLE001
            self.quiz_document = None
            self.window.render_quiz_button.setEnabled(False)
            self.window.quiz_status.setText(f"Quiz không hợp lệ: {exc}")
            return
        self.window.set_quiz_document(self.quiz_document)
        count = len(self.quiz_document.get("questions") or [])
        label = "Pilot 5 câu" if count == 5 else f"Quiz {count} câu"
        self.window.statusBar().showMessage(
            f"{label} đã được kiểm tra · chưa gọi provider/TTS"
        )

    @Slot()
    def _on_load_preset_quick(self) -> None:
        if not hasattr(self.window, "quiz_preset_combo"):
            return
        idx = self.window.quiz_preset_combo.currentIndex()
        if idx == 0:
            self.window.quiz_topic_input.setText("QuizMystra 4-Cards Comparison (Pregnant / Dating / Killer)")
            self.window.quiz_output_dir.setText("output/quizmystra_4cards_production")
            self.window.quiz_status.setText("⚡ Mẫu QuizMystra 4-Cards: 4 ảnh so sánh (Ai mang bầu, ai hẹn hò, ai sát hại)")
            self.window.quiz_artifact_path.setText("output/quizmystra_4cards_production/quizmystra_4cards_riddles_16_9.mp4")
            self.window.quiz_preview.setText(
                "QUIZMYSTRA 4-CARDS COMPARISON\n"
                "------------------------------\n"
                "• Câu 1: WHO IS PREGNANT? (Uống rượu vs Cà phê vs Thèm dưa chua đồ ngọt vs Ăn cá sống)\n"
                "• Câu 2: WHO IS GOING ON A DATE? (Ôn thi vs Nước hoa váy đầm vs Tập tạ vs Ngủ nướng)\n"
                "• Câu 3: WHO IS THE DANGEROUS KILLER? (Đầu bếp vs Bác sĩ vs Kẻ tình nghi chột dạ vs Nhân viên)\n\n"
                "Định dạng: 4 ảnh song song + Huy hiệu 1, 2, 3, 4 + Đồng hồ báo thức đếm ngược + Viền xanh neon chiến thắng!"
            )
        elif idx == 1:
            self.window.quiz_topic_input.setText("QuizMystra Visual Logic Riddle (Sleepwalker, Lab, Gallery, Poison)")
            self.window.quiz_output_dir.setText("output/quizmystra_style_production")
            self.window.quiz_status.setText("🕵️ Mẫu QuizMystra Visual Riddle: Bối cảnh phá án toàn màn hình (Vòng tròn đỏ manh mối)")
            self.window.quiz_artifact_path.setText("output/quizmystra_style_production/quizmystra_master_riddles_16_9.mp4")
            self.window.quiz_preview.setText(
                "QUIZMYSTRA VISUAL LOGIC RIDDLES\n"
                "-------------------------------\n"
                "• Câu 1: WHO IS THE SLEEPWALKER? (4 căn phòng nửa đêm, dép cọc cạch)\n"
                "• Câu 2: WHICH LAB HAS A CHEMICAL LEAK? (Trạm B rò rỉ axit)\n"
                "• Câu 3: WHO IS THE SNEAKY THIEF AT THE MANSION?\n"
                "• Câu 4: WHICH PAINTING IS A FORGERY? (Hiệp sĩ đeo đồng hồ số thế kỷ 16)\n"
                "• Câu 5: WHICH GLASS CONTAINS THE DEADLY POISON? (Đá chìm dưới đáy)\n\n"
                "Định dạng: Tranh toàn cảnh Cinematic + Vòng tròn đỏ và mũi tên vạch trần điểm bất thường!"
            )
        elif idx == 2:
            self.window.quiz_topic_input.setText("The Ultimate World Flag Challenge (30 câu Master)")
            self.window.quiz_output_dir.setText("output/us_flag_quiz_5min")
            self.window.quiz_status.setText("🇺🇸 Mẫu US Flag Quiz: 30 quốc kỳ tăng dần độ khó (Easy -> God Level)")
            self.window.quiz_artifact_path.setText("output/us_flag_quiz_5min/us_world_flag_quiz_master_16_9.mp4")
            self.window.quiz_preview.setText(
                "US & WORLD FLAG MASTER QUIZ (5.5 - 6.5 PHÚT)\n"
                "---------------------------------------------\n"
                "• Level 1: Cờ phổ thông (Mỹ, Canada, Nhật Bản, Pháp, Anh, Đức, Mexico, Tây Ban Nha)\n"
                "• Level 2: Cờ bẫy (Hà Lan, Ireland, New Zealand, Brazil, Thụy Sĩ, Nam Phi)\n"
                "• Level 3: Cờ khó (Aland, Tajikistan, Uganda, Malawi, Barbados, Kazakhstan, Nepal)\n"
                "• Level 4: Bất khả thi (Mozambique súng AK-47, Bhutan rồng sấm, Dominica vẹt tím, Nauru)\n\n"
                "Giọng đọc: Piper Native US English Ryan + Viền vàng hoàng kim + Cyber HUD."
            )
        elif idx == 3:
            self.window.quiz_topic_input.setText("Multi-Mode Dynamic Quiz (Travel Battle, Mystery Box, Rebus)")
            self.window.quiz_output_dir.setText("output/us_multimode_quiz_5min")
            self.window.quiz_status.setText("🎁 Mẫu Multi-Mode: 6 chế độ câu đố biến đổi liên tục giữ chân người xem")
            self.window.quiz_artifact_path.setText("output/us_multimode_quiz_5min/us_multimode_world_quiz_16_9.mp4")
            self.window.quiz_preview.setText(
                "MULTI-MODE DYNAMIC QUIZ (6 CHẾ ĐỘ XOAY VÒNG)\n"
                "-------------------------------------------\n"
                "1. Flag Identification (Cờ đóng khung vàng kim)\n"
                "2. Capital City Rapid Fire (Bẫy thủ đô: Úc -> Canberra, Brazil -> Brasilia)\n"
                "3. Symbol Decoder (Giải mã 3 manh mối biểu tượng)\n"
                "4. This or That Travel Battle (Đại chiến Tokyo vs Paris: Like vs Comment)\n"
                "5. Mystery Lucky Travel Box (Hộp A, B, C)\n"
                "6. Odd One Out (Nước không có biển - Thụy Sĩ)\n\n"
                "Âm thanh: Studio Cyber Trap Beat 48kHz + Dynamic Ducking trong RAM."
            )
        elif idx == 4:
            self.window.quiz_file_path.setText("presets/quiz_5_vi_candidates_verified.json")
            self._load_quiz()
        elif idx == 5:
            self.window.quiz_file_path.setText("presets/quiz_30_vi_fixture.json")
            self._load_quiz()

    @Slot()
    def _on_open_quiz_output_folder(self) -> None:
        import os
        out_dir = Path(self.window.quiz_output_dir.text().strip()).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(out_dir.resolve()))
        except Exception as exc:
            QMessageBox.warning(self.window, "Mở thư mục", f"Không thể mở thư mục: {exc}")

    @Slot()
    def _on_play_latest_quiz_video(self) -> None:
        import os
        art_text = self.window.quiz_artifact_path.text().strip()
        candidate = Path(art_text).expanduser() if art_text and art_text != "Chưa có MP4" else None
        if not candidate or not candidate.is_file():
            out_dir = Path(self.window.quiz_output_dir.text().strip()).expanduser()
            if out_dir.is_dir():
                mp4s = sorted(out_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
                if mp4s:
                    candidate = mp4s[0]
        if candidate and candidate.is_file():
            try:
                os.startfile(str(candidate.resolve()))
                self.window.statusBar().showMessage(f"Đang phát video: {candidate.name}")
            except Exception as exc:
                QMessageBox.warning(self.window, "Phát video", f"Lỗi mở video: {exc}")
        else:
            QMessageBox.information(
                self.window,
                "Chưa có Video",
                "Chưa tìm thấy file MP4 trong thư mục kết quả. Hãy nạp preset hoặc render video trước!",
            )

    @Slot()
    def _on_paste_json_clicked(self) -> None:
        from app.ui_qt.quiz_json_dialog import QuizJsonDialog

        if self.quiz_document and self.quiz_document.get("engine_v2"):
            from app.ui_qt.quiz_episode_dialog import QuizEpisodeDialog
            choice = QMessageBox.question(self.window, "Biên tập tập", "Sửa tập hiện tại bằng form? Chọn No để tạo/nạp JSON mới.")
            if choice == QMessageBox.StandardButton.Yes:
                editor = QuizEpisodeDialog(self.quiz_document, self.window)
                if editor.exec():
                    self.quiz_document = editor.document
                    self.window.set_quiz_document(self.quiz_document)
                return

        dlg = QuizJsonDialog(self.window)
        dlg.channel_profile = self.window.quiz_channel_combo.currentData() or ""
        if dlg.exec():
            if dlg.parsed_document:
                self.quiz_document = dlg.parsed_document
                self.window.set_quiz_document(self.quiz_document)
                count = len(self.quiz_document.get("questions") or [])
                self.window.statusBar().showMessage(
                    f"Đã nạp {count} câu hỏi JSON (Bản nháp) · Chờ kiểm tra trước khi Render"
                )

    @Slot(int, int, int, int)
    def _select_quiz_question(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if not self.quiz_document or current_row < 0:
            return
        questions = self.quiz_document.get("questions") or []
        if current_row < len(questions):
            self.window.set_quiz_preview(questions[current_row])

    def _style_preview_document(self) -> dict[str, Any]:
        from copy import deepcopy

        if not self.quiz_document:
            raise RuntimeError("Hãy tải quiz trước khi preview style")
        document = deepcopy(self.quiz_document)
        questions = list(document.get("questions") or [])
        if not questions:
            raise RuntimeError("Quiz chưa có câu hỏi để preview")
        style_id = str(self.window.quiz_style_combo.currentData() or "")
        motion = str(self.window.quiz_motion_combo.currentData() or "medium")
        if style_id:
            from app.services.quiz_style_packs import resolve_style_snapshot

            existing = document.get("visual_style") if isinstance(document.get("visual_style"), dict) else {}
            document["visual_style"] = resolve_style_snapshot(
                style_id,
                locale=str(document.get("language") or "en-US"),
                motion=motion,
                mascot=False,
                snapshot_override=(existing.get("snapshot") if existing.get("id") == style_id else None),
            )
        else:
            document.pop("visual_style", None)
        document["questions"] = questions
        return document

    def _sync_style_controls_from_document(self, document: dict[str, Any]) -> None:
        style = document.get("visual_style") if isinstance(document.get("visual_style"), dict) else {}
        self.window.quiz_style_combo.blockSignals(True)
        self.window.quiz_motion_combo.blockSignals(True)
        self.window.quiz_style_combo.setCurrentIndex(max(0, self.window.quiz_style_combo.findData(str(style.get("id") or ""))))
        self.window.quiz_motion_combo.setCurrentIndex(max(0, self.window.quiz_motion_combo.findData(str(style.get("motion") or "medium"))))
        self.window.quiz_style_combo.blockSignals(False)
        self.window.quiz_motion_combo.blockSignals(False)

    @Slot()
    def _preview_quiz_style(self) -> None:
        try:
            document = self._style_preview_document()
            aspect = str(self.window.quiz_preview_aspect_combo.currentData() or "16:9")
            state = str(self.window.quiz_preview_state_combo.currentData() or "question")
            result = self._render_quiz_style_preview_sync(
                document=document,
                aspect=aspect,
                state=state,
            )
            self.window.set_quiz_style_preview(result)
        except Exception as exc:  # noqa: BLE001
            self.window.set_quiz_style_preview_error(str(exc))

    def _render_quiz_style_preview_sync(
        self,
        *,
        document: dict[str, Any],
        aspect: str,
        state: str,
    ) -> dict[str, Any]:
        from PIL import Image, ImageDraw

        from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2

        questions = list(document.get("questions") or [])
        style = document.get("visual_style")
        options = QuizRenderOptions(
            aspect_ratio=aspect,
            language=str(document.get("language") or "auto"),
            channel_profile=str(document.get("channel_profile") or ""),
            visual_style=style,
        )
        engine = QuizVideoEngineV2(options)
        width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
        canvas = Image.new("RGB", (width, height), "black")
        event = {
            "idx": 1,
            "total_q": len(questions),
            "q_start": 0,
            "cd_start": 2,
            "rev_start": 8,
            "rev_dur": 4,
            "data": questions[0],
        }
        time_value = 9 if state == "reveal" else 3
        frame = engine._render_question_card(
            canvas,
            ImageDraw.Draw(canvas),
            time_value,
            event,
        )
        output = Path(self.window.quiz_output_dir.text().strip() or "output/quiz")
        preview_dir = output / "style-preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        style_id = str((style or {}).get("id") or "baseline") if isinstance(style, dict) else "baseline"
        motion = str((style or {}).get("motion") or "medium") if isinstance(style, dict) else "medium"
        import time
        path = preview_dir / f"preview-{style_id}-{motion}-{aspect.replace(':', '_')}-{state}-{time.time_ns()}.png"
        frame.save(path, format="PNG")
        with Image.open(path) as decoded:
            decoded.load()
            if decoded.format != "PNG" or decoded.size != (width, height):
                raise RuntimeError("style preview readback mismatch")
        return {
            "path": str(path.resolve()),
            "style_id": (style or {}).get("id", "baseline") if isinstance(style, dict) else "baseline",
            "motion": (style or {}).get("motion", "medium") if isinstance(style, dict) else "medium",
            "aspect": aspect,
            "state": state,
            "provider_calls": 0,
            "tts_calls": 0,
        }

    @Slot()
    def _save_quiz_style(self) -> None:
        try:
            document = self._style_preview_document()
            if "visual_style" not in document:
                document.pop("visual_style", None)
            from app.services.quiz_v2_runtime import save_document, load_document

            output = Path(self.window.quiz_output_dir.text().strip() or "output/quiz")
            path = save_document(document, output)
            self.quiz_document = load_document(path)
            self._sync_style_controls_from_document(self.quiz_document)
            self.window.set_quiz_document(self.quiz_document)
            self.window.statusBar().showMessage(f"Đã lưu style snapshot · {path.resolve()}")
        except Exception as exc:  # noqa: BLE001
            self.window.set_quiz_style_preview_error(str(exc))

    @Slot()
    def _cancel_quiz_style(self) -> None:
        self.window.restore_quiz_style_controls(self.quiz_document or {})

    @Slot()
    def _render_quiz(self) -> None:
        if self.quiz_document is None:
            self.window.quiz_status.setText("Hãy tải và kiểm tra quiz trước khi render")
            return
        self.window.render_quiz_button.setEnabled(False)
        self.window.quiz_progress.setRange(0, 0)
        count = len(self.quiz_document.get("questions") or [])
        self.window.quiz_status.setText(
            f"Đang xử lý xuất xưởng bản {count} câu..."
        )
        # Snapshot UI values on main thread before background execution
        output_dir_str = self.window.quiz_output_dir.text().strip()
        aspect_choice = self.window.quiz_aspect_combo.currentText() if hasattr(self.window, "quiz_aspect_combo") else "16:9"
        from copy import deepcopy
        document_snapshot = deepcopy(self.window.read_quiz_review(self.quiz_document))
        self.bridge.run("render_quiz", lambda: self._render_quiz_sync(output_dir_str=output_dir_str, aspect_choice=aspect_choice, document_snapshot=document_snapshot))

    def _render_quiz_sync(self, output_dir_str: str = "", aspect_choice: str = "16:9", document_snapshot: dict | None = None) -> dict[str, Any]:
        import hashlib
        import json
        import shutil
        import uuid
        from pathlib import Path
        from app.services.quiz_pilot import QuizPilotComposer, QuizPilotLedger

        if self.quiz_document is None:
            raise RuntimeError("quiz document is not loaded")

        document = document_snapshot if document_snapshot is not None else self.quiz_document
        if document.get("engine_v2"):
            from copy import deepcopy
            import asyncio
            import time
            from app.services.quiz_v2_runtime import require_review, save_document
            from app.services.quiz_asset_resolver import resolve_quiz_assets
            started = time.perf_counter()
            document = deepcopy(document)
            require_review(document)
            from app.services.quiz_engine_v2 import QuizVideoEngineV2, QuizRenderOptions
            output_dir = Path(output_dir_str or "output/quiz").expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            aspect_ratio = "9:16" if "9:16" in aspect_choice else "16:9"
            out_mp4 = output_dir / f"quiz_custom_master_{uuid.uuid4().hex[:12]}_{aspect_ratio.replace(':', '_')}.mp4"
            temp_out_mp4 = output_dir / f"temp_{uuid.uuid4().hex[:8]}_{aspect_ratio.replace(':', '_')}.mp4"
            questions = asyncio.run(resolve_quiz_assets(document["questions"], output_dir / "assets", allow_generation=False))
            archetype = document.get("archetype") or ("riddle_mystra" if any("cards" in q or "scene_image" in q for q in questions) else "classic")
            settings = document.get("settings") or {}

            from copy import deepcopy
            opt = QuizRenderOptions(
                aspect_ratio=aspect_ratio,
                fps=30,
                language=document.get("language") or "auto",
                channel_profile=document.get("channel_profile", ""),
                visual_style=deepcopy(document.get("visual_style")),
                archetype=archetype,
                output_path=temp_out_mp4,
                bgm_path=Path("assets/bgm/bgm_cyber_trap.wav"),
                tts_engine="piper",
                piper_voice=settings.get("piper_voice") or ("en_US-ryan-high" if document.get("language") == "en" else "manh_dung"),
                piper_speed=float(settings.get("piper_speed", 1.05)),
                piper_model_dir=Path("D:/ALL AI/TestProjects/Voice/assets/models/piper"),
                piper_exe=Path("D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe"),
            )
            engine = QuizVideoEngineV2(opt)
            try:
                rendered_path = engine.render_quiz_video(questions, title=document.get("title", "Custom Quiz"))
                if not rendered_path.exists() or rendered_path.stat().st_size == 0:
                    raise RuntimeError(f"Rendered video missing or empty: {rendered_path}")
                dur = engine._probe_dur(rendered_path)
                if dur <= 0:
                    raise RuntimeError(f"Rendered video duration invalid: {dur}")
                shutil.move(str(rendered_path), str(out_mp4))
            finally:
                if temp_out_mp4.exists():
                    try:
                        temp_out_mp4.unlink()
                    except Exception:
                        pass

            actual_sha256 = hashlib.sha256(out_mp4.read_bytes()).hexdigest() if out_mp4.exists() else ""
            duration_ms = int(engine._probe_dur(out_mp4) * 1000) if out_mp4.exists() else 0
            manifest_path = out_mp4.with_suffix(".manifest.json")
            manifest_data = {
                "schema_version": "quiz_v2_dynamic",
                "channel_profile": document.get("channel_profile", ""),
                "visual_style": document.get("visual_style"),
                "editorial_qa": document.get("editorial_qa", {}),
                "title": document.get("title", "Custom Quiz"),
                "archetype": archetype,
                "aspect_ratio": aspect_ratio,
                "question_count": len(questions),
                "sha256": actual_sha256,
                "final_mp4": str(out_mp4.resolve()),
                "duration_ms": duration_ms,
                "settings": {"piper_voice": opt.piper_voice, "piper_speed": opt.piper_speed, "language": opt.language},
                "elapsed_seconds": time.perf_counter() - started,
                "tts_calls": getattr(engine, "tts_calls", 0),
                "tts_cache_hits": getattr(engine, "tts_cache_hits", 0),
                "document_path": str(save_document(document, output_dir)),
            }
            manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
            return {
                "final_mp4": str(out_mp4.resolve()),
                "manifest": str(manifest_path.resolve()),
                "sha256": actual_sha256,
                "duration_ms": duration_ms,
                "question_count": len(questions),
                "pending_items": [],
                "provider_calls": 0,
                "tts_calls": getattr(engine, "tts_calls", 0),
                "tts_cache_hits": getattr(engine, "tts_cache_hits", 0),
            }

        questions = list(self.quiz_document.get("questions") or [])
        approval = self.quiz_document.get("approval") or {}
        fingerprint = str(approval.get("content_fingerprint") or "")
        if (
            len(questions) not in {5, 30}
            or approval.get("status") != "approved"
            or len(fingerprint) != 64
        ):
            raise RuntimeError("quiz render requires 5 or 30 approved questions")
        question_ids = [str(item.get("question_id") or "") for item in questions]
        output_dir = Path(self.window.quiz_output_dir.text().strip()).expanduser()
        ledger = QuizPilotLedger.load(
            output_dir / "pilot-ledger.json",
            expected_content_fingerprint=fingerprint,
        )
        if ledger.document.get("question_ids") != question_ids:
            raise RuntimeError("pilot ledger question order does not match approved quiz")
        item_ids = ["intro", *question_ids, "outro"]
        pending: list[str] = []
        clips: list[tuple[str, Path]] = []
        for item_id in item_ids:
            item = ledger.item(item_id)
            candidate = output_dir / f"{item_id}.mp4"
            matches = (
                item.get("status") == "validated"
                and candidate.is_file()
                and candidate.stat().st_size == item.get("bytes")
                and hashlib.sha256(candidate.read_bytes()).hexdigest()
                == item.get("sha256")
            )
            if not matches:
                pending.append(item_id)
            else:
                clips.append((item_id, candidate))
        if pending:
            raise RuntimeError(f"pending pilot artifacts: {pending}")
        composer = QuizPilotComposer(fps=30)
        result = composer.compose_embedded_clips(
            clips,
            output_dir / "final.mp4",
            manifest_path=output_dir / "pilot-manifest.json",
            expected_question_ids=question_ids,
        )
        return {
            "final_mp4": str(result.output_path),
            "manifest": str(result.manifest_path),
            "sha256": result.sha256,
            "duration_ms": result.duration_ms,
            "question_count": len(questions),
            "pending_items": [],
            "provider_calls": 0,
            "tts_calls": 0,
        }

    @Slot()
    def _render_final(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy mở project trước.")
            return
        self.cancel_event.clear()
        self._set_busy(True, "Đang kiểm tra và render pipeline...")
        self.window.set_render_state(progress=5, prerequisites="Đang kiểm tra prerequisites...")
        self.bridge.run("render_final", self._render_final_async)

    @Slot()
    def _cancel_render(self) -> None:
        self.cancel_event.set()
        self.window.statusBar().showMessage(
            "Đã yêu cầu dừng; pipeline sẽ dừng trước stage kế tiếp"
        )

    @Slot()
    def _retry_selected_scene(self) -> None:
        scene_id = self.window.selected_visual_scene_id()
        if not self.project_id or not scene_id:
            QMessageBox.warning(self.window, "Chưa chọn scene", "Hãy chọn scene cần retry.")
            return
        from app.services.project_manager import ProjectManager
        from app.storage import database

        with database.create_session() as session:
            result = ProjectManager(
                session,
                project_root=self.settings.project_root or None,
            ).retry_scene(str(self.project_id), scene_id, from_stage="render")
        self.window.statusBar().showMessage(
            f"Retry {scene_id}: {result['previous_status']} → {result['new_status']}"
        )

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise RuntimeError("render cancelled by user before next stage")

    async def _render_final_async(self) -> dict[str, Any]:
        import json

        from app.models import Asset
        from app.schemas.timeline import ProjectTimeline
        from app.services.final_composer import FinalComposer
        from app.services.project_manager import ProjectManager
        from app.services.render_coordinator import RenderCoordinator
        from app.services.scene_renderer import LocalSceneRenderer
        from app.services.script_analysis import ScriptAnalyzer
        from app.services.semantic_scene_renderer import VoxSemanticSceneRenderer
        from app.services.vox_production_pipeline import (
            VoxProductionPipeline,
        )
        from app.storage import database
        from app.storage.asset_store import AssetStore
        from app.storage.repositories import AssetRepo, ProjectRepo, SceneRepo

        project_id = str(self.project_id)
        store = AssetStore(self.settings.project_root or None)
        storyboard_path = store.subdir(project_id, "manifests") / "storyboard.json"
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        style_snapshot = storyboard.get("style_snapshot")
        if not isinstance(style_snapshot, dict):
            style_snapshot = {}
        with database.create_session() as session:
            project = ProjectRepo.get(session, project_id)
            scenes = SceneRepo.list(session, project_id)
            if project is None or not scenes:
                raise RuntimeError("project has no persisted scenes")
            durations: list[tuple[str, int]] = []
            selected_assets: dict[str, Asset] = {}
            for scene in scenes:
                duration = int(scene.actual_voice_duration_ms or 0)
                if duration <= 0:
                    raise RuntimeError(f"missing voice duration: {scene.scene_id}")
                durations.append((scene.scene_id, duration))
                candidates = [
                    asset
                    for asset in AssetRepo.list(session, project_id, scene.scene_id)
                    if asset.selected
                ]
                if not candidates:
                    raise RuntimeError(f"missing selected image: {scene.scene_id}")
                selected_assets[scene.scene_id] = candidates[0]
            timeline = ProjectTimeline.from_voice_durations(
                durations,
                int(project.fps or self.settings.default_fps),
            )

        canvas = (
            (1080, 1920)
            if str(project.aspect_ratio) == "9:16"
            else (1920, 1080)
        )
        if not all(
            isinstance(scene, dict) and isinstance(scene.get("canonical_visual_scene"), dict)
            for scene in storyboard.get("scenes", [])
        ):
            from app.providers.llm.cliproxy import CliproxyLLMProvider

            provider = CliproxyLLMProvider(
                base_url=self.settings.cliproxy_base_url,
                model=self.settings.cliproxy_model,
                api_key=self.settings.cliproxy_api_key,
                timeout_seconds=self.settings.cliproxy_timeout_seconds,
            )
            try:
                storyboard = await ScriptAnalyzer(provider).plan_canonical_visuals(
                    storyboard,
                    project_id=project_id,
                    voice_durations_ms={key: value + 340 for key, value in durations},
                    project_root=store.base,
                )
                store.write_manifest(project_id, "storyboard.json", storyboard)
            finally:
                await provider.aclose()
        prepared = await asyncio.to_thread(
            VoxProductionPipeline(
                project_root=store.base,
                canvas_size=canvas,
                fps=int(project.fps or self.settings.default_fps),
            ).prepare,
            project_id,
            storyboard=storyboard,
            selected_assets=selected_assets,
            voice_durations_ms=dict(durations),
            store=store,
        )
        self._check_cancelled()
        if prepared.scene_ids != [scene.scene_id for scene in scenes]:
            raise RuntimeError("VOX preparation cardinality mismatch")
        renderer = VoxSemanticSceneRenderer.for_production(
            LocalSceneRenderer(project_root=store.base),
            prepared.canonical_scenes,
        )
        coordinator = RenderCoordinator(renderer=renderer, project_root=store.base)
        rendered: list[str] = []
        for scene_id in prepared.scene_ids:
            output = await asyncio.to_thread(
                coordinator.render_scene,
                project_id=project_id,
                scene_id=scene_id,
                selected_asset=selected_assets[scene_id],
            )
            rendered.append(str(output.output_path))
            self._check_cancelled()
        if len(rendered) != len(scenes):
            raise RuntimeError(
                f"render cardinality mismatch: {len(rendered)} / {len(scenes)}"
            )

        audio_path = store.subdir(project_id, "audio") / "narration.wav"
        subtitle_path = store.subdir(project_id, "final") / "subtitles.srt"
        if not audio_path.is_file():
            raise RuntimeError("narration.wav missing; generate voice first")
        if not subtitle_path.is_file():
            raise RuntimeError("subtitles.srt missing; generate caption first")
        with database.create_session() as session:
            output = ProjectManager(session, project_root=store.base).compose_final(
                project_id,
                composer=FinalComposer(),
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                expected_duration_ms=timeline.duration_ms,
            )
            state = ProjectManager(session, project_root=store.base).get_project(project_id)
        manifest_path = store.subdir(project_id, "manifests") / "render_manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError("render_manifest.json missing after compose")
        if state["status"] != "COMPLETED":
            raise RuntimeError(f"project state not COMPLETED: {state['status']}")
        return {
            "final_path": str(output),
            "rendered": len(rendered),
            "status": state["status"],
        }

    @Slot()
    def _save_script(self) -> None:
        if not self.project_id:
            QMessageBox.warning(self.window, "Chưa có project", "Hãy tạo hoặc mở project trước.")
            return
        script = self.window.script_editor.toPlainText().strip()
        if not script:
            QMessageBox.warning(self.window, "Thiếu kịch bản", "Nội dung kịch bản không được để trống.")
            return
        self._set_busy(True, "Đang lưu script...")
        self.bridge.run("save_script", lambda: self._save_script_sync(script))

    def _save_script_sync(self, script: str) -> dict[str, Any]:
        from app.services.project_manager import ProjectManager
        from app.storage import database

        with database.create_session() as session:
            return ProjectManager(
                session,
                project_root=self.settings.project_root or None,
            ).save_script(str(self.project_id), script)

    @Slot()
    def _create_storyboard(self) -> None:
        topic = self.window.script_editor.toPlainText().strip() or self.window.topic_input.text().strip()
        if not topic:
            QMessageBox.warning(self.window, "Thiếu kịch bản", "Hãy nhập nội dung kịch bản trước.")
            return
        self._set_busy(True, "Đang tạo storyboard bằng CLIProxy...")
        self.bridge.run("plan", lambda: self._plan_topic(topic))

    @Slot()
    def _new_project(self) -> None:
        self.project_id = None
        self.window.topic_input.clear()
        self.window.script_editor.clear()
        self.window.scene_list.clear()
        self.window.statusBar().showMessage("Dự án mới · Nhập chủ đề rồi bấm AI Viết kịch bản")
        self.window.topic_input.setFocus()

    @Slot()
    def _generate_script(self) -> None:
        topic = self.window.topic_input.text().strip()
        if not topic:
            QMessageBox.warning(self.window, "Thiếu chủ đề", "Hãy nhập chủ đề hoặc ý tưởng video trước.")
            return
        self._set_busy(True, "Đang dùng AI viết kịch bản phóng sự tài liệu...")
        self.bridge.run("ai_write_script", lambda: self._write_script_async(topic))

    async def _write_script_async(self, topic: str) -> dict[str, str]:
        import httpx
        system_prompt = (
            "Bạn là biên kịch video tài liệu phóng sự phong cách Vox, Johnny Harris chuyên nghiệp. "
            "QUY TẮC BẮT BUỘC: Chỉ trả về nội dung lời đọc (voiceover narration) tiếng Việt, "
            "tuyệt đối không kèm lời chào, lời dẫn, ghi chú kỹ thuật, tiêu đề hay bất kỳ ký tự giải thích nào."
        )
        user_prompt = (
            f"Hãy viết một kịch bản phóng sự tài liệu giải thích hấp dẫn về chủ đề: \"{topic}\".\n"
            "Yêu cầu:\n"
            "- Viết từ 4 đến 6 phân đoạn ngắn (mỗi đoạn 2-3 câu, cách nhau đúng 1 dòng trống).\n"
            "- Phong cách cuốn hút, dồn dập, có mốc thời gian và số liệu cụ thể.\n"
            "- Không dùng dấu gạch đầu dòng, chỉ là các đoạn văn bản lời đọc thuần túy."
        )
        payload = {
            "model": self.settings.cliproxy_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {self.settings.cliproxy_api_key}"} if self.settings.cliproxy_api_key else {}
        clean_base = self.settings.cliproxy_base_url.rstrip("/")
        if clean_base.endswith("/v1"):
            endpoint = f"{clean_base}/chat/completions"
        else:
            endpoint = f"{clean_base}/v1/chat/completions"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            script_text = data["choices"][0]["message"]["content"].strip()
            return {"topic": topic, "script": script_text}

    @Slot()
    def _run_1click_auto_pipeline(self) -> None:
        script = self.window.script_editor.toPlainText().strip()
        topic = self.window.topic_input.text().strip()
        if not script and not topic:
            QMessageBox.warning(self.window, "Thiếu kịch bản", "Hãy nhập chủ đề hoặc dán kịch bản vào trước khi chạy 1-Click.")
            return
        self._set_busy(True, "Đang chạy 1-Click Auto Full Pipeline từ A đến Z...")
        self.bridge.run("1click_auto_pipeline", lambda: self._auto_pipeline_async(topic, script))

    async def _auto_pipeline_async(self, topic: str, script: str) -> dict[str, Any]:
        from app.services.vox_auto_pipeline import VoxAutoPipeline
        final_script = script
        if not final_script:
            script_data = await self._write_script_async(topic)
            final_script = script_data["script"]

        pipeline = VoxAutoPipeline(
            output_base_dir=self.settings.project_root or "projects",
        )
        res = await pipeline.run_from_script(
            final_script,
            project_title=topic or "Vox_Project",
        )
        return {
            "video_path": str(res.video_path),
            "subtitles_path": str(res.subtitles_path),
            "duration": res.duration_seconds,
            "script": final_script,
            "project_id": res.project_id,
        }

    async def _plan_topic(self, topic: str) -> dict[str, Any]:
        from app.providers.llm.cliproxy import CliproxyLLMProvider
        from app.services.project_manager import ProjectManager
        from app.services.prompts import load_presets
        from app.services.script_analysis import ScriptAnalyzer
        from app.storage import database

        database.init_schema()
        provider = CliproxyLLMProvider(
            base_url=self.settings.cliproxy_base_url,
            model=self.settings.cliproxy_model,
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=self.settings.cliproxy_timeout_seconds,
        )
        try:
            with database.create_session() as session:
                manager = ProjectManager(session, project_root=self.settings.project_root or None)
                if self.project_id:
                    manager.save_script(self.project_id, topic)
                    project = manager.get_project(self.project_id)
                else:
                    project, _created = manager.create_project(topic, title=topic[:80])
                    self.project_id = project["project_id"]
                result = await manager.plan(
                    self.project_id,
                    ScriptAnalyzer(provider, style_preset=load_presets().get("editorial_collage")),
                )
                return {"project": project, "result": result}
        finally:
            await provider.aclose()

    async def _check_provider_health(self) -> dict[str, str]:
        from app.providers.llm.cliproxy import CliproxyLLMProvider

        provider = CliproxyLLMProvider(
            base_url=self.settings.cliproxy_base_url,
            model=self.settings.cliproxy_model,
            api_key=self.settings.cliproxy_api_key,
            timeout_seconds=min(self.settings.cliproxy_timeout_seconds, 20),
        )
        try:
            health = await provider.health()
            return {"status": health.status, "model": self.settings.cliproxy_model}
        finally:
            await provider.aclose()

    @Slot(str, object)
    def _on_success(self, label: str, payload: object) -> None:
        if label == "quiz_assets":
            self.window.quiz_generate_assets_button.setEnabled(True)
            self.quiz_document = payload["document"]
            self.window.quiz_file_path.setText(payload["path"])
            self.window.set_quiz_document(self.quiz_document)
            self.window.quiz_status.setText("Ảnh đã tải và decode · cần xem manh mối trước khi duyệt")
            return
        self._set_busy(False)
        if label == "ai_write_script" and isinstance(payload, dict):
            script_text = str(payload.get("script") or "")
            self.window.script_editor.setPlainText(script_text)
            self.window.saved_badge.setText("Đã sinh kịch bản AI")
            self.window.statusBar().showMessage("✦ Đã viết xong kịch bản bằng AI!")
            self._on_script_changed()
        elif label == "1click_auto_pipeline" and isinstance(payload, dict):
            video_path = str(payload.get("video_path") or "")
            dur = float(payload.get("duration") or 0.0)
            self.window.statusBar().showMessage(f"🚀 Video 1-Click hoàn tất: {video_path}")
            msg = QMessageBox(self.window)
            msg.setWindowTitle("🚀 1-Click Video Hoàn Tất!")
            msg.setText(f"Video Full HD ({dur:.1f}s) đã được sản xuất tự động thành công!\n\nĐường dẫn:\n{video_path}")
            open_btn = msg.addButton("▶ Mở Video", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == open_btn:
                import os
                try:
                    os.startfile(video_path)
                except Exception:
                    pass
        elif label == "plan" and isinstance(payload, dict):
            project = payload.get("project", {})
            title = project.get("title") if isinstance(project, dict) else ""
            self._load_projects()
            if self.project_id:
                self._refresh_project_view()
            self.window.statusBar().showMessage(f"Đã tạo storyboard · {title or self.project_id}")
        elif label == "research_quiz" and isinstance(payload, dict):
            self.quiz_document = payload
            self.window.set_quiz_document(payload)
            self.window.quiz_status.setText("Đã tạo pilot 5 câu · chưa duyệt")
            self.window.statusBar().showMessage("Đã lưu và đọc lại pilot 5 câu")
        elif label == "save_script":
            self.window.saved_badge.setText("Đã lưu")
            self.window.statusBar().showMessage("Đã lưu script và đọc lại project")
            self._refresh_project_view()
        elif label == "provider_health" and isinstance(payload, dict):
            status = str(payload.get("status") or "unknown")
            model = str(payload.get("model") or "")
            self.window.set_provider_status(
                f"●  CLIProxy {status} · {model}",
                ok=status == "ok",
            )
        elif label == "save_prompt" and isinstance(payload, dict):
            scene_id = str(payload.get("scene_id") or "")
            if scene_id:
                self._refresh_visual_scene(scene_id)
            self.window.statusBar().showMessage(
                "Đã lưu prompt vào DB và storyboard manifest"
            )
        elif label in {"generate_images", "generate_style_scene_images"} and isinstance(
            payload, dict
        ):
            self.window.set_style_regeneration_running(False)
            scene_id = str(payload.get("scene_id") or "")
            selected_path = str(payload.get("selected_path") or "")
            if scene_id:
                self._refresh_visual_scene(scene_id)
            if selected_path and not self.window.set_image_preview(selected_path):
                raise RuntimeError(f"Qt preview failed to decode selected image: {selected_path}")
            self._on_activity(
                "INFO",
                "generate_images",
                (
                    f"preview={selected_path} · asset={payload.get('selected_asset_id')} · "
                    f"size={payload.get('width')}x{payload.get('height')}"
                ),
            )
            self.window.statusBar().showMessage(
                f"Ảnh hoàn tất · generated={payload.get('generated', 0)} "
                f"cached={payload.get('cached', 0)} · preview đã đọc lại"
            )
        elif label == "save_style" and isinstance(payload, dict):
            project = payload.get("project") or {}
            style = payload.get("style") or {}
            self.window.set_style_content(project, style)
            self.window.style_state.setText(
                "Đã lưu bản nháp · chưa ảnh hưởng ảnh/render cho đến khi áp dụng."
            )
            self.window.statusBar().showMessage("Đã lưu bản nháp style và đọc lại")
        elif label == "apply_style" and isinstance(payload, dict):
            project = payload.get("project") or {}
            style = payload.get("style") or {}
            self.window.set_style_content(project, style)
            self.window.style_state.setText(
                f"Đã áp dụng revision {style.get('style_revision')} · "
                f"visual {str(style.get('visual_hash') or '')[:12]}"
            )
            self.window.statusBar().showMessage("Đã áp dụng style vào storyboard và đọc lại")
        elif label == "generate_style_all_images" and isinstance(payload, dict):
            self.window.set_style_regeneration_running(False)
            total = int(payload.get("total") or 0)
            succeeded = int(payload.get("succeeded") or 0)
            generated = int(payload.get("generated") or 0)
            cached = int(payload.get("cached") or 0)
            errors = list(payload.get("errors") or [])
            state = "đã dừng" if bool(payload.get("cancelled")) else "hoàn tất"
            self.window.statusBar().showMessage(
                f"Tạo lại ảnh {state} · scene={succeeded}/{total} · "
                f"generated={generated} cached={cached} lỗi={len(errors)}"
            )
            self._load_project(str(payload.get("project_id") or self.project_id))
        elif label == "generate_voice" and isinstance(payload, dict):
            self.window.set_voice_results(
                list(payload.get("results") or []),
                str(payload.get("narration_path") or ""),
            )
            self.window.statusBar().showMessage("Đã tạo WAV và narration.wav")
        elif label == "generate_caption" and isinstance(payload, dict):
            self.window.set_caption_entries(list(payload.get("entries") or []))
            result = payload.get("result") or {}
            self.window.statusBar().showMessage(
                f"Đã tạo SRT · {result.get('entry_count', 0)} caption"
            )
        elif label == "render_quiz" and isinstance(payload, dict):
            self.window.quiz_progress.setRange(0, 100)
            self.window.render_quiz_button.setEnabled(True)
            self.window.set_quiz_render_result(payload)
            count = int(payload.get("question_count") or 0)
            self.window.statusBar().showMessage(
                f"Bản {count} câu hoàn tất: {payload.get('final_mp4')}"
            )
        elif label == "render_final" and isinstance(payload, dict):
            final_path = str(payload.get("final_path") or "")
            self.window.set_render_state(
                progress=100,
                prerequisites="Render, compose, manifest và trạng thái COMPLETED đã được xác minh.",
                artifact=final_path,
            )
            self.window.statusBar().showMessage(f"Final MP4: {final_path}")
        elif label == "render_semantic_pilot" and isinstance(payload, dict):
            final_path = Path(str(payload.get("final_mp4") or ""))
            self.semantic_pilot_final = final_path
            self.window.render_semantic_pilot_button.setEnabled(True)
            self.window.open_semantic_pilot_button.setEnabled(final_path.is_file())
            self.window.semantic_pilot_status.setText(
                "PASS · 6/6 grammar · provider calls=0 · Semantic candidate"
            )
            self.window.semantic_pilot_artifact.setText(
                f"{final_path}\nSHA-256: {str(payload.get('final_sha256') or '')}"
            )
            self.window.statusBar().showMessage(f"Semantic pilot PASS: {final_path}")
        elif label == "run_media_queue" and isinstance(payload, dict):
            self._refresh_media_queue()
            action = str(payload.get("action") or "")
            status = str(payload.get("status") or "empty")
            if action == "import_music" and status == "succeeded":
                self.window.music_status.setText("Đã nhập nhạc vào project · FFprobe PASS")
            elif action == "import_video" and status == "succeeded":
                self.window.video_status.setText("Đã nhập video vào project · FFprobe PASS")
            self.window.statusBar().showMessage(
                f"Hàng đợi local · {action or 'không có job'} · {status}"
            )
        elif label == "prepare_local_publish" and isinstance(payload, dict):
            self.window.publish_status.setText(
                "Package local hoàn tất · 0 network calls\n"
                f"Video: {payload.get('video_path')}\n"
                f"Manifest: {payload.get('manifest_path')}"
            )
            self.window.statusBar().showMessage(
                f"Package local: {payload.get('video_path')}"
            )
        elif label == "settings_health" and isinstance(payload, dict):
            dialog = getattr(self, "_settings_dialog", None)
            if dialog is not None:
                dialog.set_test_complete()
            summary = " · ".join(f"{key}={value}" for key, value in payload.items())
            self.window.statusBar().showMessage(f"Provider health · {summary}")

    def _refresh_project_view(self) -> None:
        if self.project_id:
            self._load_project(self.project_id)

    @Slot(str, str)
    def _on_failure(self, label: str, error: str) -> None:
        if label == "quiz_assets":
            self.window.quiz_generate_assets_button.setEnabled(True)
            self.window.quiz_status.setText(f"Sinh ảnh dừng: {error}")
            return
        if self.bridge.active_count == 0:
            self._set_busy(False)
        if label == "provider_health":
            self.window.set_provider_status("●  CLIProxy không khả dụng", ok=False)
            return
        if label == "render_quiz":
            self.window.quiz_progress.setRange(0, 100)
            approval = (self.quiz_document or {}).get("approval") or {}
            count = len((self.quiz_document or {}).get("questions") or [])
            approved = (
                count in {5, 30}
                and approval.get("status") == "approved"
                and len(str(approval.get("content_fingerprint") or "")) == 64
            )
            self.window.render_quiz_button.setEnabled(approved)
            self.window.quiz_status.setText(f"Render bản {count} câu lỗi: {error}")
            return
        if label == "render_semantic_pilot":
            self.window.render_semantic_pilot_button.setEnabled(True)
            self.window.open_semantic_pilot_button.setEnabled(False)
            self.window.semantic_pilot_status.setText(f"Semantic pilot FAIL: {error}")
        if label == "settings_health":
            dialog = getattr(self, "_settings_dialog", None)
            if dialog is not None:
                dialog.set_test_complete()
        self.window.statusBar().showMessage(f"Lỗi {label}: {error}")
        QMessageBox.critical(self.window, "Vox Studio", error)


def launch_qt() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Vox Studio")
    app.setOrganizationName("Vox Studio")
    window = VoxStudioWindow()
    controller = VoxQtApp(window)
    window._controller = controller  # keep QObject/controller alive
    window.show_page("quiz")
    window.show()
    app.exec()


__all__ = ["QtWorkerBridge", "VoxQtApp", "launch_qt"]
