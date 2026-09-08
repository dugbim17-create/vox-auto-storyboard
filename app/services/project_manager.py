"""Project lifecycle service (P2-T06).

Creates a project from a script file (writes the input into the project's
``input/`` directory, computes a SHA-256, persists the project row) and wires
the CLI ``create-project`` / ``plan`` commands to the analysis pipeline.

Idempotency guarantee (AC: chạy lần hai không duplicate nếu input không đổi):
``create-project`` with the same script content and title returns the existing
project instead of duplicating it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.state_machine import StateMachine
from app.storage.asset_store import AssetStore, sha256_file
from app.storage.repositories import ProjectRepo

logger = logging.getLogger(__name__)


def _canvas_from_aspect(aspect: str) -> tuple[int, int]:
    """Map an aspect ratio string to a default 1080p canvas.

    The local renderer currently uses 1080p; portrait/9:16 keeps the same
    height scale but flips the axes to 1080x1920.
    """
    a = (aspect or "16:9").strip()
    if a in ("9:16", "vertical", "portrait"):
        return 1080, 1920
    if a in ("1:1", "square"):
        return 1080, 1080
    return 1920, 1080


class ProjectManagerError(Exception):
    """Raised when project creation or lookup fails."""


def generate_project_id(prefix: str = "prj") -> str:
    """Human-usable project id: ``prj_YYYYMMDD_NNNN`` using a short uid."""
    today = datetime.now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}_{today}_{suffix}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ProjectManager:
    """Creates projects, persists script text + input file, runs planning."""

    def __init__(
        self,
        session: Any,
        *,
        project_root: str | Path | None = None,
    ) -> None:
        self.session = session
        self.store = AssetStore(project_root)

    # ------------------------------------------------------------------ #
    # create-project
    # ------------------------------------------------------------------ #
    def create_project(
        self,
        script: str,
        *,
        title: str = "",
        project_id: str | None = None,
        style_preset: str = "editorial_collage",
        aspect_ratio: str = "16:9",
        fps: int = 30,
    ) -> tuple[dict, bool]:
        """Create a project and persist its script. Returns (project_dict, created).

        If a project with the same script content already exists, the existing
        project is returned with ``created=False`` (idempotent).
        """
        script = script.strip()
        if not script:
            raise ProjectManagerError("script is empty")

        digest = sha256_text(script)

        # Idempotency: same script + same title -> reuse existing project.
        existing = self._find_by_script_hash(digest)
        if existing is not None:
            return _project_dict(existing), False

        pid = project_id or generate_project_id()
        self.store.init_project(pid)
        # Write input script into the project's input/ dir (P1-T03 layout).
        rel = "input/script.txt"
        self.store.write_project_file(pid, rel, script.encode("utf-8"))

        proj = ProjectRepo.create(
            self.session,
            project_id=pid,
            title=title or _title_from_script(script),
            status="INGESTED",
            script_source=rel,
            script_hash=digest,
            script_text=script,
            aspect_ratio=aspect_ratio,
            fps=fps,
            style_preset=style_preset,
        )
        self.session.commit()
        return _project_dict(proj), True

    def get_project(self, project_id: str) -> dict:
        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")
        return _project_dict(proj)

    def save_script(self, project_id: str, script: str) -> dict:
        """Persist edited source text to the DB and canonical project input file."""
        script = script.strip()
        if not script:
            raise ProjectManagerError("script is empty")
        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")
        proj.script_text = script
        proj.script_hash = sha256_text(script)
        proj.script_source = "input/script.txt"
        self.store.write_project_file(
            project_id,
            proj.script_source,
            script.encode("utf-8"),
        )
        self.session.commit()
        return _project_dict(proj)

    def _find_by_script_hash(self, digest: str) -> Any:
        from sqlalchemy import select

        from app.models import Project

        return self.session.scalars(
            select(Project).where(Project.script_hash == digest)
        ).first()

    # ------------------------------------------------------------------ #
    # plan
    # ------------------------------------------------------------------ #
    async def plan(
        self,
        project_id: str,
        analyzer: Any,
        *,
        temperature: float = 0.2,
    ) -> dict:
        """Run the script-analysis pipeline for a project. Returns analysis dict."""
        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")
        script = proj.script_text or ""
        if not script:
            raise ProjectManagerError(f"project has no script: {project_id}")

        analysis = await analyzer.analyze(
            project_id,
            script,
            self.session,
            project_root=self.store.base,
            temperature=temperature,
        )
        # After a validated storyboard is persisted, advance to VALIDATED
        # (section 14 flow: SCRIPT_ANALYZED -> STORYBOARD_DRAFTED ->
        # STORYBOARD_VALIDATED). Re-planning when already VALIDATED is a no-op.
        current = ProjectRepo.get(self.session, project_id)
        if current is not None and current.status != "STORYBOARD_VALIDATED":
            StateMachine(self.session).transition_project(
                project_id, "STORYBOARD_VALIDATED", reason="storyboard validated"
            )
            self.session.commit()
        return {
            "project_id": project_id,
            "scene_count": analysis.scene_count,
            "word_count": analysis.word_count,
            "estimated_duration_seconds": analysis.estimated_duration_seconds,
            "storyboard_path": str(analysis.storyboard_path),
            "planner_calls": analysis.planner_calls,
            "repair_calls": analysis.repair_calls,
            "elapsed_ms": analysis.elapsed_ms,
        }

    # ------------------------------------------------------------------ #
    # render (Phase 7 / P7-T02)
    # ------------------------------------------------------------------ #
    async def render_project(
        self,
        project_id: str,
        *,
        renderer: Any,
        motion_planner: Any | None = None,
        image_service: Any | None = None,
        layer_workflow: Any | None = None,
        tts_pipeline: Any | None = None,
    ) -> dict:
        """Run the full render pipeline for a project.

        Steps (each is optional; only ``renderer`` is required):

        1. measured TTS narration per scene -> ``audio/{scene_id}.wav``;
        2. image generation (per scene/role);
        3. layer preparation (Direct layer);
        4. voice-timed motion planning per scene;
        5. render each scene to ``scenes/{scene_id}.mp4``.

        ``renderer`` is a ``LocalSceneRenderer`` (or compatible) and is the
        only mandatory dependency. Other steps are skipped when their service
        is ``None`` so unit tests can drive a single stage at a time.
        """
        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")

        scenes_dir = self.store.subdir(project_id, "scenes")
        layers_dir = self.store.subdir(project_id, "layers")

        # Step 1: TTS must run first. Its measured durations are the only
        # canonical clock accepted by motion planning and rendering.
        audio_files: list[str] = []
        narration_path = ""
        voice_timelines: dict[str, Any] = {}
        if tts_pipeline is not None:
            tts_result = await tts_pipeline.run(
                project_id, self.session, project_root=self.store.base
            )
            audio_files = [str(p) for p in (getattr(tts_result, "audio_paths", []) or [])]
            if hasattr(tts_pipeline, "materialize_audio"):
                narration = self.store.subdir(project_id, "audio") / "narration.wav"
                narration_path = str(tts_pipeline.materialize_audio(tts_result, narration))
            if motion_planner is not None:
                fps = int(proj.fps or 30)
                for scene_result in (getattr(tts_result, "scene_results", []) or []):
                    try:
                        voice_timelines[scene_result.scene_id] = scene_result.voice_timeline(
                            fps=fps
                        )
                    except Exception as exc:  # noqa: BLE001
                        raise ProjectManagerError(
                            f"scene {scene_result.scene_id} has no valid measured word timings"
                        ) from exc

        # Step 2: image generation (if service provided).
        if image_service is not None:
            await image_service.generate_project(project_id, session=self.session)
            # Provider/service seams may persist rows through this session with
            # autoflush disabled or return after updating scene references.
            # Flush and expire before the renderer performs authoritative
            # selected-asset read-back.
            self.session.flush()
            self.session.expire_all()

        # Step 3: layer preparation.
        scenes_index = self._load_scenes_index(project_id)
        if layer_workflow is not None:
            from app.storage.repositories import AssetRepo

            for scene_id in scenes_index:
                selected = AssetRepo.get_selected_for_scene(
                    self.session, project_id, scene_id
                )
                if selected is None:
                    raise ProjectManagerError(f"missing selected image: {scene_id}")
                layer_result = layer_workflow.prepare_composite(
                    project_id,
                    scene_id,
                    str(selected.path),
                    store=self.store,
                )
                if not getattr(layer_result, "ok", False):
                    raise ProjectManagerError(
                        f"layer prep {scene_id}: {getattr(layer_result, 'error', 'unknown error')}"
                    )

        # Step 4: segmentation + voice-timed motion planning.
        if motion_planner is not None:
            missing_timings = [scene_id for scene_id in scenes_index if scene_id not in voice_timelines]
            if missing_timings:
                raise ProjectManagerError(
                    f"measured word timings are required before motion: {missing_timings}"
                )
            contexts = self._build_motion_contexts(
                project_id,
                scenes_index,
                layers_dir,
                voice_timelines=voice_timelines,
            )
            planned = await motion_planner.plan_project(project_id, contexts)
            planned_by_scene = {
                result.scene_id: result.plan
                for result in (getattr(planned, "scenes", []) or [])
                if getattr(result, "plan", None) is not None
            }
            if set(planned_by_scene) != set(scenes_index):
                raise ProjectManagerError(
                    "motion planner cardinality mismatch: "
                    f"expected {scenes_index}, got {sorted(planned_by_scene)}"
                )
            motion_dir = self.store.subdir(project_id, "manifests") / "motion"
            motion_dir.mkdir(parents=True, exist_ok=True)
            storyboard = self._load_storyboard(project_id)
            style_snapshot = storyboard.get("style_snapshot")
            from app.services.render_lineage import (
                build_motion_lineage_envelope,
                write_lineage_manifest,
            )

            for scene_id in scenes_index:
                plan = planned_by_scene[scene_id]
                raw_plan = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
                write_lineage_manifest(
                    motion_dir / f"{scene_id}.json",
                    build_motion_lineage_envelope(
                        raw_plan,
                        style_snapshot=(
                            style_snapshot if isinstance(style_snapshot, dict) else None
                        ),
                    ),
                )

        # Step 5: render each scene.
        from app.services.render_coordinator import RenderCoordinator
        from app.storage.repositories import AssetRepo

        coordinator = RenderCoordinator(renderer=renderer, project_root=self.store.base)
        rendered: list[str] = []
        missing_plans = [
            scene_id
            for scene_id in scenes_index
            if self._load_scene_plan(project_id, scene_id) is None
        ]
        if missing_plans:
            raise ProjectManagerError(
                f"missing motion plan for scene: {missing_plans[0]}"
            )
        for scene_id in scenes_index:
            selected_asset = AssetRepo.get_selected_for_scene(
                self.session, project_id, scene_id
            )
            if selected_asset is None:
                raise ProjectManagerError(f"missing selected image for scene: {scene_id}")
            result = coordinator.render_scene(
                project_id=project_id,
                scene_id=scene_id,
                selected_asset=selected_asset,
            )
            rendered.append(str(result.output_path))

        # Advance state machine.
        if rendered:
            try:
                StateMachine(self.session).transition_project(
                    project_id, "SCENES_READY", reason="all scenes rendered"
                )
                self.session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("transition to SCENES_READY skipped: %s", exc)

        return {
            "project_id": project_id,
            "scenes_dir": str(scenes_dir),
            "rendered": rendered,
            "audio_files": audio_files,
            "narration_path": narration_path,
        }

    # ------------------------------------------------------------------ #
    # compose final (Phase 7 / P7-T03)
    # ------------------------------------------------------------------ #
    def compose_final(
        self,
        project_id: str,
        *,
        composer: Any,
        audio_path: str | Path | None = None,
        subtitle_path: str | Path | None = None,
        expected_duration_ms: int | None = None,
        bgm_path: str | Path | None = None,
        transition_service: Any | None = None,
    ) -> Path:
        """Compose all ``scenes/*.mp4`` (+ optional audio) into ``final/final.mp4``.

        ``audio_path`` overrides the auto-detected ``audio/narration.wav``
        (when present) so callers can supply a mixed track.

        ``subtitle_path`` overrides the auto-detected ``final/subtitles.srt``
        (when present) so callers can supply a custom SRT.

        Canvas size is taken from the storyboard scenes (first scene's
        canvas.width/height); falls back to the project aspect ratio when
        no scene exists.
        """
        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")

        scenes_dir = self.store.subdir(project_id, "scenes")
        audio_dir = self.store.subdir(project_id, "audio")
        final_dir = self.store.subdir(project_id, "final")

        expected_scene_ids = self._load_scenes_index(project_id)
        if not expected_scene_ids:
            raise ProjectManagerError("storyboard contains no scenes")
        scenes = [scenes_dir / f"{scene_id}.mp4" for scene_id in expected_scene_ids]
        missing_scenes = [str(path) for path in scenes if not path.is_file()]
        if missing_scenes:
            raise ProjectManagerError(f"missing scene MP4(s): {missing_scenes}")

        storyboard = self._load_storyboard(project_id)
        style_snapshot = storyboard.get("style_snapshot")
        if not isinstance(style_snapshot, dict):
            style_snapshot = {}
        expected_style = {
            key: str(style_snapshot.get(key) or "")
            for key in ("visual_hash", "motion_hash", "render_theme_hash")
        }
        render_lineage_dir = self.store.subdir(project_id, "manifests") / "render"
        for scene_id, scene_path in zip(expected_scene_ids, scenes, strict=True):
            lineage_path = render_lineage_dir / f"{scene_id}.json"
            if not lineage_path.is_file():
                continue  # legacy projects are allowed until they adopt applied style snapshots
            try:
                scene_lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ProjectManagerError(f"invalid scene render lineage: {scene_id}") from exc
            actual_style = scene_lineage.get("style") or {}
            if any(
                expected_style[key] and str(actual_style.get(key) or "") != expected_style[key]
                for key in expected_style
            ):
                raise ValueError(f"stale scene render lineage: {scene_id}")
            recorded_output = str((scene_lineage.get("output") or {}).get("sha256") or "")
            if recorded_output and recorded_output != sha256_file(scene_path):
                raise ValueError(f"scene artifact hash mismatch: {scene_id}")

        audio: Path | None = None
        if audio_path is not None:
            audio = Path(audio_path)
        else:
            candidate = audio_dir / "narration.wav"
            if candidate.is_file():
                audio = candidate

        if audio is not None and bgm_path is not None:
            from app.services.bgm_service import BGMService

            mixed = audio_dir / "narration_bgm.wav"
            audio = BGMService().mix(
                audio,
                bgm_path,
                mixed,
                duration_ms=expected_duration_ms or 0,
            ).output_path

        # Auto-detect subtitles.
        srt: Path | None = None
        if subtitle_path is not None:
            srt = Path(subtitle_path)
        else:
            srt_candidate = final_dir / "subtitles.srt"
            if srt_candidate.is_file():
                srt = srt_candidate

        if transition_service is not None and len(scenes) > 1:
            transition_output = final_dir / "transitioned.mp4"
            transition_result = transition_service.apply_transitions(
                scenes,
                ["hard_cut"] * (len(scenes) - 1),
                transition_output,
                fps=int(proj.fps or 30),
            )
            scenes = [transition_output]
            expected_duration_ms = expected_duration_ms or transition_result.total_duration_ms

        out_path = final_dir / "final.mp4"
        # Read canvas size from the first scene's motion plan when present.
        width, height = _canvas_from_aspect(str(proj.aspect_ratio or "16:9"))
        first_scene_id = scenes[0].stem
        first_plan = self._load_scene_plan(project_id, first_scene_id)
        if first_plan:
            canvas = first_plan.get("canvas") or {}
            if canvas.get("width") and canvas.get("height"):
                width = int(canvas["width"])
                height = int(canvas["height"])
        fps = int(proj.fps or 30)
        out_path, _ = composer.compose(
            scenes,
            audio,
            out_path,
            fps=fps,
            width=width,
            height=height,
            expected_duration_ms=expected_duration_ms,
            subtitle_path=srt,
        )

        # Write renderer-neutral final lineage only after the final artifact is verified.
        from app.services.render_lineage import (
            build_final_render_lineage,
            write_lineage_manifest,
        )

        scene_outputs = [
            {"scene_id": scene_id, "sha256": sha256_file(scene_path)}
            for scene_id, scene_path in zip(expected_scene_ids, scenes, strict=True)
        ]
        manifest = build_final_render_lineage(
            project_id=project_id,
            style_snapshot=style_snapshot,
            scene_outputs=scene_outputs,
            audio_sha256=sha256_file(audio) if audio is not None and audio.is_file() else "",
            subtitle_sha256=sha256_file(srt) if srt is not None and srt.is_file() else "",
            output_path=str(out_path),
            output_sha256=sha256_file(out_path),
        )
        manifest.update(
            fps=fps,
            width=width,
            height=height,
            codec="h264",
            audio_codec="aac",
            pixel_format="yuv420p",
            faststart=True,
        )
        manifest_path = self.store.subdir(project_id, "manifests") / "render_manifest.json"
        write_lineage_manifest(manifest_path, manifest)

        state = StateMachine(self.session)
        current_status = ProjectRepo.get(self.session, project_id).status
        if current_status != "COMPLETED":
            if current_status not in {"FINAL_RENDERING", "VALIDATING"}:
                if current_status not in {
                    "INGESTED", "SCRIPT_ANALYZED", "STORYBOARD_DRAFTED",
                    "STORYBOARD_VALIDATED", "STORYBOARD_APPROVED", "SCENES_READY",
                }:
                    raise ProjectManagerError(
                        f"cannot finalize project from state {current_status}"
                    )
                state.transition_project(
                    project_id, "FINAL_RENDERING", reason="final artifact rendered"
                )
                current_status = "FINAL_RENDERING"
            if current_status == "FINAL_RENDERING":
                state.transition_project(
                    project_id, "VALIDATING", reason="final artifact validation"
                )
            state.transition_project(
                project_id, "COMPLETED", reason="final mp4 composed and validated"
            )
            self.session.commit()

        return out_path

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _load_scenes_index(self, project_id: str) -> list[str]:
        """Read ``manifests/storyboard.json`` and return ordered scene ids."""
        import json

        path = self.store.subdir(project_id, "manifests") / "storyboard.json"
        if not path.is_file():
            return []
        sb = json.loads(path.read_text(encoding="utf-8"))
        return [s["scene_id"] for s in sb.get("scenes", [])]

    def _load_storyboard(self, project_id: str) -> dict:
        import json

        path = self.store.subdir(project_id, "manifests") / "storyboard.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _load_scene_plan(self, project_id: str, scene_id: str) -> dict | None:
        """Load a motion plan for a scene from the asset store.

        Plans are stored under ``manifests/motion/{scene_id}.json`` (within
        the allowed subdir set). Returns ``None`` when missing.
        """
        import json

        path = (
            self.store.subdir(project_id, "manifests")
            / "motion"
            / f"{scene_id}.json"
        )
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("kind") == "motion_plan":
                nested = payload.get("payload")
                return nested if isinstance(nested, dict) else None
            return payload
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("scene %s: motion plan read failed: %s", scene_id, exc)
            return None

    def _build_motion_contexts(
        self,
        project_id: str,
        scenes_index: list[str],
        layers_dir: Any,
        *,
        voice_timelines: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Build measured voice-first contexts; never invent scene duration."""
        from app.schemas.timeline import SceneTimeline
        from app.services.motion_planner import SceneMotionContext
        from app.storage.repositories import SceneRepo

        project = ProjectRepo.get(self.session, project_id)
        if project is None:
            raise ProjectManagerError(f"project not found: {project_id}")
        fps = int(project.fps or 30)
        canvas = _canvas_from_aspect(str(project.aspect_ratio or "16:9"))

        contexts: list[SceneMotionContext] = []
        for scene_id in scenes_index:
            scene = SceneRepo.get(self.session, project_id, scene_id)
            voice_duration_ms = int(scene.actual_voice_duration_ms or 0) if scene else 0
            if voice_duration_ms <= 0:
                raise ProjectManagerError(
                    f"scene {scene_id} has no measured voice duration; generate voice before motion"
                )
            available = frozenset(
                p.stem.replace(f"{scene_id}_", "", 1)
                for p in layers_dir.glob(f"{scene_id}_*.png")
            )
            contexts.append(
                SceneMotionContext(
                    scene_id=scene_id,
                    voice_duration_ms=voice_duration_ms,
                    canvas_size=canvas,
                    available_roles=available,
                    seed=42,
                    timeline=SceneTimeline.from_voice(
                        scene_id,
                        voice_duration_ms,
                        fps,
                    ),
                    voice_timeline=(voice_timelines or {}).get(scene_id),
                )
            )
        return contexts

    # ------------------------------------------------------------------ #
    # resume (P9-T02)
    # ------------------------------------------------------------------ #
    def get_pending_scenes(self, project_id: str) -> list[dict]:
        """Return scenes still needing work (for resume)."""
        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")
        pending = StateMachine.pending_scenes(self.session, project_id)
        return [
            {
                "scene_id": s.scene_id,
                "status": s.status,
                "order": s.order,
            }
            for s in pending
        ]

    # ------------------------------------------------------------------ #
    # retry-scene (P9-T03)
    # ------------------------------------------------------------------ #
    def retry_scene(
        self,
        project_id: str,
        scene_id: str,
        *,
        from_stage: str = "image",
    ) -> dict:
        """Reset a scene's state to retry from a specific stage.

        ``from_stage`` can be:
        - ``image`` → reset to PLANNED (re-generate image + all downstream)
        - ``voice`` → reset to PLANNED (re-generate voice + all downstream)
        - ``render`` → reset to MOTION_READY (re-render only)
        - ``layers`` → reset to IMAGE_READY (re-prepare layers + downstream)

        Only FAILED_RETRYABLE scenes or scenes at a later stage can be reset.
        """
        from app.storage.repositories import AssetRepo, RenderAttemptRepo, SceneRepo

        proj = ProjectRepo.get(self.session, project_id)
        if proj is None:
            raise ProjectManagerError(f"project not found: {project_id}")

        scene = SceneRepo.get(self.session, project_id, scene_id)
        if scene is None:
            raise ProjectManagerError(f"scene not found: {scene_id}")

        stage_map = {
            "image": "PLANNED",
            "voice": "PLANNED",
            "layers": "IMAGE_READY",
            "render": "MOTION_READY",
        }
        target_state = stage_map.get(from_stage)
        if target_state is None:
            raise ProjectManagerError(
                f"unknown retry stage: {from_stage!r}; valid: {list(stage_map)}"
            )

        old_status = scene.status
        StateMachine(self.session).retry_scene(
            project_id,
            scene_id,
            target_state,
            reason=f"retry from stage={from_stage}; downstream invalidated",
        )
        invalidated_assets = 0
        invalidated_renders = 0
        if from_stage in {"image", "voice", "layers"}:
            invalidated_assets = AssetRepo.mark_scene_stale(self.session, project_id, scene_id)
        if from_stage in {"image", "voice", "layers", "render"}:
            invalidated_renders = RenderAttemptRepo.mark_scene_stale(
                self.session, project_id, scene_id
            )
        self.session.commit()

        return {
            "project_id": project_id,
            "scene_id": scene_id,
            "previous_status": old_status,
            "new_status": target_state,
            "retry_from": from_stage,
            "invalidated_assets": invalidated_assets,
            "invalidated_renders": invalidated_renders,
        }


def _project_dict(proj: Any) -> dict:
    return {
        "project_id": proj.project_id,
        "title": proj.title,
        "status": proj.status,
        "script_source": proj.script_source,
        "script_hash": proj.script_hash,
        "script_text": proj.script_text,
        "style_preset": proj.style_preset,
        "created_at": proj.created_at.isoformat() if proj.created_at else None,
    }


def _title_from_script(script: str) -> str:
    """First non-empty line, truncated, as a default title."""
    first = next((ln.strip() for ln in script.splitlines() if ln.strip()), "")
    return first[:120] or "Untitled"
