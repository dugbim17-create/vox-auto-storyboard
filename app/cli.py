"""CLI entry point: ``python -m app.cli <command>``.

Commands:
- ``doctor`` — system health check (P0-T02)
- ``create-project --script <file>`` — create a project from a script (P2-T06)
- ``plan --project <id>`` — run the script -> storyboard pipeline (P2-T06)
- ``generate-voice --project <id>`` — TTS per scene (P3-T05)
- ``generate-images --project <id>`` — image generation per scene (P4-T05)
- ``render --project <id>`` — render all scenes to MP4 (P7-T02)
- ``compose --project <id>`` — concat scenes (+ audio) -> final.mp4 (P7-T03)
- ``status --project <id>`` — show project status & scene states
- ``run --script <file>`` — full end-to-end pipeline (P9-T01)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from pathlib import Path

from app.runtime_settings import load_runtime_settings
from app.settings import get_settings


def _cliproxy_config() -> dict[str, object]:
    runtime = load_runtime_settings()
    discovered = get_settings()
    return {
        "base_url": runtime.cliproxy_base_url,
        "model": runtime.cliproxy_model,
        "api_key": runtime.cliproxy_api_key or discovered.cliproxy_api_key,
        "timeout_seconds": runtime.cliproxy_timeout_seconds,
    }


def _cmd_doctor(_args: argparse.Namespace) -> int:  # noqa: ARG001
    from app.tooling.doctor import doctor_main

    return doctor_main()


def _cmd_render_quiz(args: argparse.Namespace) -> int:
    """Render an exact 30-question quiz fully offline."""
    from app.services.quiz_renderer import QuizOfflineRenderer

    quiz_path = Path(args.quiz)
    if not quiz_path.is_file():
        print(f"error: quiz file not found: {quiz_path}", file=sys.stderr)
        return 2
    quiz = json.loads(quiz_path.read_text(encoding="utf-8"))
    renderer = QuizOfflineRenderer(
        width=args.width,
        height=args.height,
        fps=args.fps,
    )
    result = renderer.render(
        quiz,
        Path(args.output_dir),
        audio_policy=args.audio_policy,
    )
    print(
        json.dumps(
            {
                "final_mp4": str(result.output_path),
                "manifest": str(result.manifest_path),
                "probe": str(result.probe_path),
                "sha256": result.sha256,
                "duration_ms": result.duration_ms,
                "provider_calls": 0,
                "tts_calls": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_render_semantic_pilot(args: argparse.Namespace) -> int:
    """Render the isolated six-scene semantic pilot without providers or DB."""
    from app.services.semantic_pilot import render_semantic_pilot

    result = render_semantic_pilot(args.output_root)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _cmd_render_vox_style_bundle(args: argparse.Namespace) -> int:
    """Render four distinct provider-free VOX visual families."""
    from app.services.semantic_style_bundle import render_vox_style_bundle

    result = render_vox_style_bundle(args.output_root)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _open_session() -> None:
    from app.storage import database

    database.init_schema()


def _cmd_create_project(args: argparse.Namespace) -> int:
    from app.services.project_manager import ProjectManager

    script_path = Path(args.script)
    if not script_path.is_file():
        print(f"error: script file not found: {script_path}", file=sys.stderr)
        return 2
    script = script_path.read_text(encoding="utf-8")

    _open_session()
    from app.storage import database

    with database.create_session() as session:
        manager = ProjectManager(session)
        project, created = manager.create_project(
            script,
            title=args.title or "",
            style_preset=args.style,
            aspect_ratio=args.aspect_ratio,
            fps=args.fps,
        )
        status = "created" if created else "reused (same script content)"
        print(json.dumps({"project_id": project["project_id"], "status": status}, ensure_ascii=False))
        return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    from app.providers.llm.cliproxy import CliproxyLLMProvider
    from app.services.project_manager import ProjectManager
    from app.services.prompts import load_presets
    from app.services.script_analysis import ScriptAnalyzer

    _open_session()
    from app.storage import database

    with database.create_session() as session:
        manager = ProjectManager(session)
        project = manager.get_project(args.project)

        presets = load_presets()
        preset = presets.get(project["style_preset"])

        planner = CliproxyLLMProvider(**_cliproxy_config())
        analyzer = ScriptAnalyzer(planner, style_preset=preset)

        async def _run() -> dict:
            try:
                return await manager.plan(args.project, analyzer, temperature=args.temperature)
            finally:
                await planner.aclose()

        result = asyncio.run(_run())
        print(json.dumps(result, ensure_ascii=False))
        return 0


def _cmd_generate_voice(args: argparse.Namespace) -> int:
    """Generate TTS per scene via OmniVoice worker (P3-T05)."""
    from app.providers.tts.omnivoice import OmniVoiceProvider
    from app.services.tts_pipeline import TTSScenePipeline
    from app.storage.asset_store import AssetStore

    _open_session()
    from app.storage import database

    provider = OmniVoiceProvider()
    pipeline = TTSScenePipeline(provider)

    with database.create_session() as session:

        async def _run() -> dict:
            result = await pipeline.run(
                args.project, session, project_root=AssetStore().base,
            )
            return {
                "project_id": result.project_id,
                "total_scenes": result.total_scenes,
                "generated": result.generated,
                "cached": result.cached,
                "errors": result.errors,
            }

        result = asyncio.run(_run())
        print(json.dumps(result, ensure_ascii=False))
        return 0


def _cmd_generate_images(args: argparse.Namespace) -> int:
    """Generate images per scene/role (P4-T05)."""
    from app.providers.image.antigravity import AntigravityImageProvider
    from app.providers.image.cliproxy_image import CliproxyImageProvider
    from app.providers.image.flowkit import FlowKitImageProvider
    from app.runtime_settings import load_runtime_settings
    from app.services.image_generation import ImageGenerationService

    _open_session()
    from app.storage import database

    runtime = load_runtime_settings()
    cliproxy_config = _cliproxy_config()
    providers = {
        "flowkit": FlowKitImageProvider(
            base_url=runtime.flowkit_base_url,
            health_path=runtime.flowkit_health_path,
            submit_path=runtime.flowkit_submit_path,
            status_path_template=runtime.flowkit_status_path_template,
            timeout_seconds=runtime.flowkit_timeout_seconds,
        ),
        "cliproxy_image": CliproxyImageProvider(
            base_url=runtime.cliproxy_base_url,
            model="gpt-image-2",
            api_key=str(cliproxy_config["api_key"]),
            timeout_seconds=runtime.cliproxy_timeout_seconds,
        ),
        "antigravity_image": AntigravityImageProvider(),
    }
    provider_name = args.image_provider or runtime.image_provider
    if provider_name == "auto":
        provider_name = "flowkit" if runtime.flowkit_enabled else "cliproxy_image"
    provider = providers[provider_name]
    service = ImageGenerationService(
        image_provider=provider,
        provider_name=provider_name,
        flowkit_provider=providers["flowkit"],
        cliproxy_provider=providers["cliproxy_image"],
    )

    with database.create_session() as session:

        async def _run() -> dict:
            result = await service.generate_project(args.project, session=session)
            return {
                "project_id": result.project_id,
                "total_scenes": result.total_scenes,
                "generated": result.generated,
                "cached": result.cached,
                "errors": result.errors,
            }

        result = asyncio.run(_run())
        print(json.dumps(result, ensure_ascii=False))
        return 0


def _cmd_render(args: argparse.Namespace) -> int:
    """Render every scene to ``scenes/*.mp4`` (P7-T02)."""
    from app.services.project_manager import ProjectManager
    from app.services.scene_renderer import LocalSceneRenderer

    _open_session()
    from app.storage import database

    renderer = LocalSceneRenderer()
    with database.create_session() as session:
        manager = ProjectManager(session)

        async def _run() -> dict:
            return await manager.render_project(
                args.project,
                renderer=renderer,
            )

        result = asyncio.run(_run())
        print(json.dumps(result, ensure_ascii=False))
        return 0


def _cmd_compose(args: argparse.Namespace) -> int:
    """Concat scenes + audio -> ``final/final.mp4`` (P7-T03)."""
    from app.services.final_composer import FinalComposer
    from app.services.project_manager import ProjectManager

    _open_session()
    from app.storage import database

    composer = FinalComposer()
    with database.create_session() as session:
        manager = ProjectManager(session)
        out = manager.compose_final(
            args.project,
            composer=composer,
            audio_path=args.audio,
        )
        print(json.dumps({"project_id": args.project, "final_mp4": str(out)}, ensure_ascii=False))
        return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """Show project status and per-scene states."""
    from app.services.project_manager import ProjectManager
    from app.storage.repositories import SceneRepo

    _open_session()
    from app.storage import database

    with database.create_session() as session:
        manager = ProjectManager(session)
        project = manager.get_project(args.project)

        scenes_index = manager._load_scenes_index(args.project)
        scene_states = []
        for sid in scenes_index:
            scene = SceneRepo.get(session, args.project, sid)
            if scene:
                scene_states.append({
                    "scene_id": sid,
                    "status": scene.status,
                    "voice_duration_ms": scene.actual_voice_duration_ms,
                    "selected_image": scene.selected_image_asset_id,
                })
            else:
                scene_states.append({"scene_id": sid, "status": "NOT_IN_DB"})

        result = {
            "project_id": project["project_id"],
            "title": project["title"],
            "status": project["status"],
            "style_preset": project["style_preset"],
            "scene_count": len(scenes_index),
            "scenes": scene_states,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Full end-to-end pipeline: script -> final.mp4 (P9-T01).

    Orchestrates all steps in sequence:
    1. create-project
    2. plan (storyboard via LLM)
    3. generate-voice (TTS per scene)
    4. generate-images (per scene/role)
    5. prepare layers
    6. motion planning
    7. render scenes
    8. generate subtitles
    9. compose final video
    """
    from app.providers.image.antigravity import AntigravityImageProvider
    from app.providers.image.cliproxy_image import CliproxyImageProvider
    from app.providers.image.flowkit import FlowKitImageProvider
    from app.providers.llm.cliproxy import CliproxyLLMProvider
    from app.providers.tts.omnivoice import OmniVoiceProvider
    from app.runtime_settings import load_runtime_settings
    from app.services.final_composer import FinalComposer
    from app.services.image_generation import ImageGenerationService
    from app.services.project_manager import ProjectManager
    from app.services.prompts import load_presets
    from app.services.scene_renderer import LocalSceneRenderer
    from app.services.script_analysis import ScriptAnalyzer
    from app.services.semantic_scene_renderer import VoxSemanticSceneRenderer
    from app.services.subtitle_generator import SceneNarration, SubtitleGenerator
    from app.services.tts_pipeline import TTSScenePipeline
    from app.services.vox_production_pipeline import (
        VoxProductionPipeline,
    )
    from app.storage.asset_store import AssetStore
    from app.storage.repositories import AssetRepo, SceneRepo

    script_path = Path(args.script)
    if not script_path.is_file():
        print(f"error: script file not found: {script_path}", file=sys.stderr)
        return 2
    script = script_path.read_text(encoding="utf-8")

    _open_session()
    from app.storage import database

    aspect_ratio = args.aspect_ratio
    style = args.style
    fps = args.fps

    async def _pipeline() -> str:
        # Step 1: create project
        _step("1/9", "Create project")
        with database.create_session() as session:
            manager = ProjectManager(session)
            project, created = manager.create_project(
                script, title=args.title or "",
                style_preset=style, aspect_ratio=aspect_ratio, fps=fps,
            )
            project_id = project["project_id"]
            _info(f"project_id={project_id} {'created' if created else 'reused'}")

        # Step 2: plan
        _step("2/9", "Generate storyboard via LLM")
        planner = CliproxyLLMProvider(**_cliproxy_config())
        presets = load_presets()
        preset = presets.get(style)
        analyzer = ScriptAnalyzer(planner, style_preset=preset)
        with database.create_session() as session:
            manager = ProjectManager(session)
            try:
                plan_result = await manager.plan(project_id, analyzer, temperature=0.2)
            finally:
                await planner.aclose()
            _info(f"scenes={plan_result['scene_count']}")

        # Step 3: generate voice (voice-first!)
        _step("3/9", "Generate TTS per scene")
        tts_provider = OmniVoiceProvider()
        tts_pipeline = TTSScenePipeline(tts_provider)
        store = AssetStore()
        with database.create_session() as session:
            tts_result = await tts_pipeline.run(
                project_id, session, project_root=store.base,
            )
            narration_path = store.subdir(project_id, "audio") / "narration.wav"
            tts_pipeline.materialize_audio(tts_result, narration_path)
            _info(f"generated={tts_result.generated} cached={tts_result.cached}")
            _info(f"narration={narration_path}")

        # Step 3b: the same CLIProxy model now owns the canonical visual plan.
        _step("3b/9", "Generate canonical visual scenes via CLIProxy")
        planner = CliproxyLLMProvider(**_cliproxy_config())
        try:
            storyboard_path = store.subdir(project_id, "manifests") / "storyboard.json"
            storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
            voice_durations_ms = {
                item.scene_id: item.duration_ms + 340 for item in tts_result.scene_results
            }
            storyboard = await ScriptAnalyzer(planner).plan_canonical_visuals(
                storyboard,
                project_id=project_id,
                voice_durations_ms=voice_durations_ms,
                project_root=store.base,
            )
            store.write_manifest(project_id, "storyboard.json", storyboard)
            _info(f"canonical_scenes={len(voice_durations_ms)}")
        finally:
            await planner.aclose()

        # Step 4: generate images
        _step("4/9", "Generate images per scene/role")
        runtime = load_runtime_settings()
        cliproxy_config = _cliproxy_config()
        flowkit_provider = FlowKitImageProvider(
            base_url=runtime.flowkit_base_url,
            health_path=runtime.flowkit_health_path,
            submit_path=runtime.flowkit_submit_path,
            status_path_template=runtime.flowkit_status_path_template,
            timeout_seconds=runtime.flowkit_timeout_seconds,
        )
        cliproxy_provider = CliproxyImageProvider(
            base_url=runtime.cliproxy_base_url,
            model="gpt-image-2",
            api_key=str(cliproxy_config["api_key"]),
            timeout_seconds=runtime.cliproxy_timeout_seconds,
        )
        antigravity_provider = AntigravityImageProvider()
        selected_provider = args.image_provider
        if selected_provider == "auto":
            selected_provider = "flowkit" if runtime.flowkit_enabled else "cliproxy_image"
        providers = {
            "flowkit": flowkit_provider,
            "cliproxy_image": cliproxy_provider,
            "antigravity_image": antigravity_provider,
        }
        image_service = ImageGenerationService(
            image_provider=providers[selected_provider],
            provider_name=selected_provider,
            flowkit_provider=flowkit_provider,
            cliproxy_provider=cliproxy_provider,
        )
        with database.create_session() as session:
            img_result = await image_service.generate_project(project_id, session=session)
            _info(f"generated={img_result.generated} cached={img_result.cached}")

        # Steps 5-6: benchmark-derived VOX asset packs + semantic motion.
        _step("5-6/9", "Prepare semantic VOX assets and motion")
        canvas = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
        with database.create_session() as session:
            manager = ProjectManager(session)
            scenes_index = manager._load_scenes_index(project_id)
            storyboard = json.loads(
                (store.subdir(project_id, "manifests") / "storyboard.json").read_text("utf-8")
            )
            selected_assets = {}
            voice_durations_ms = {}
            for scene_id in scenes_index:
                scene = SceneRepo.get(session, project_id, scene_id)
                asset = AssetRepo.get_selected_for_scene(session, project_id, scene_id)
                if scene is None or asset is None:
                    raise RuntimeError(f"missing scene/selected asset: {scene_id}")
                selected_assets[scene_id] = asset
                voice_durations_ms[scene_id] = int(scene.actual_voice_duration_ms or 0)
            prepared = VoxProductionPipeline(
                project_root=store.base,
                canvas_size=canvas,
                fps=fps,
            ).prepare(
                project_id,
                storyboard=storyboard,
                selected_assets=selected_assets,
                voice_durations_ms=voice_durations_ms,
                store=store,
            )
        _info(
            f"vox_scenes={len(prepared.scene_ids)} "
            f"visual_changes={prepared.visual_change_budget}"
        )

        # Step 7: render scenes
        _step("7/9", "Render scenes to MP4")
        renderer = VoxSemanticSceneRenderer.for_production(
            LocalSceneRenderer(project_root=store.base),
            prepared.canonical_scenes,
        )
        with database.create_session() as session:
            manager = ProjectManager(session)
            render_result = await manager.render_project(project_id, renderer=renderer)
            _info(f"rendered={len(render_result['rendered'])}")

        # Step 8: subtitles
        _step("8/9", "Generate subtitles")
        with database.create_session() as session:
            manager = ProjectManager(session)
            scenes_index = manager._load_scenes_index(project_id)
            narrations = []
            for i, scene_id in enumerate(scenes_index):
                scene = SceneRepo.get(session, project_id, scene_id)
                narration = scene.narration_text if scene else ""
                voice_ms = int(scene.actual_voice_duration_ms) if scene and scene.actual_voice_duration_ms else 5000
                narrations.append(SceneNarration(
                    scene_id=scene_id, narration=narration or "",
                    voice_duration_ms=voice_ms, order=i + 1,
                ))
            srt_path = store.subdir(project_id, "final") / "subtitles.srt"
            sub_gen = SubtitleGenerator()
            sub_result = sub_gen.generate(project_id, narrations, srt_path)
            _info(f"subtitles={sub_result.entry_count}")

        # Step 9: compose final
        _step("9/9", "Compose final MP4")
        composer = FinalComposer()
        with database.create_session() as session:
            manager = ProjectManager(session)
            audio_path = store.subdir(project_id, "audio") / "narration.wav"
            if not audio_path.is_file():
                audio_path = None

            out = manager.compose_final(project_id, composer=composer,
                                        audio_path=str(audio_path) if audio_path else None)
            _info(f"final={out}")
            return str(out)

    try:
        final = asyncio.run(_pipeline())
        print(f"\nSUCCESS: {final}")
        return 0
    except Exception as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def _step(num: str, msg: str) -> None:
    print(f"\n{'='*60}\n[{num}] {msg}\n{'='*60}")


def _info(msg: str) -> None:
    print(f"  -> {msg}")


def _cmd_resume(args: argparse.Namespace) -> int:
    """Resume a project: show pending scenes and re-run render + compose."""
    from app.services.project_manager import ProjectManager

    _open_session()
    from app.storage import database

    with database.create_session() as session:
        manager = ProjectManager(session)
        pending = manager.get_pending_scenes(args.project)
        project = manager.get_project(args.project)

        result = {
            "project_id": args.project,
            "status": project["status"],
            "pending_scenes": pending,
            "total_pending": len(pending),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if not pending:
            print("All scenes completed — nothing to resume.")
        else:
            print(f"\n{len(pending)} scene(s) pending. Re-run with:")
            print(f"  python -m app.cli render --project {args.project}")
            print(f"  python -m app.cli compose --project {args.project}")
        return 0


def _cmd_retry_scene(args: argparse.Namespace) -> int:
    """Retry a specific scene from a given stage."""
    from app.services.project_manager import ProjectManager

    _open_session()
    from app.storage import database

    with database.create_session() as session:
        manager = ProjectManager(session)
        result = manager.retry_scene(
            args.project,
            args.scene,
            from_stage=args.from_stage,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-storyboard", description="Auto Storyboard Vox CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Check system dependencies and local services")
    p_doc.set_defaults(func=_cmd_doctor)

    p_quiz = sub.add_parser("render-quiz", help="Render an exact 30-question quiz offline")
    p_quiz.add_argument("--quiz", required=True, help="Path to quiz JSON")
    p_quiz.add_argument("--output-dir", required=True, help="Artifact output directory")
    p_quiz.add_argument("--width", type=int, default=1280)
    p_quiz.add_argument("--height", type=int, default=720)
    p_quiz.add_argument("--fps", type=int, default=30)
    p_quiz.add_argument(
        "--audio-policy",
        choices=["synthetic_sine", "silent"],
        default="synthetic_sine",
        help="Local-only audio stream policy; never invokes TTS",
    )
    p_quiz.set_defaults(func=_cmd_render_quiz)

    p_semantic = sub.add_parser(
        "render-semantic-pilot",
        help="Render the isolated provider-free semantic-motion acceptance pilot",
    )
    p_semantic.add_argument("--output-root", required=True, help="Isolated acceptance root")
    p_semantic.set_defaults(func=_cmd_render_semantic_pilot)

    p_style_bundle = sub.add_parser(
        "render-vox-style-bundle",
        help="Render four provider-free VOX visual families for one-shot approval",
    )
    p_style_bundle.add_argument("--output-root", required=True, help="Isolated acceptance root")
    p_style_bundle.set_defaults(func=_cmd_render_vox_style_bundle)

    p_create = sub.add_parser("create-project", help="Create a project from a script file")
    p_create.add_argument("--script", required=True, help="Path to the script .txt file")
    p_create.add_argument("--title", default="", help="Project title (optional)")
    p_create.add_argument("--style", default="editorial_collage", help="Style preset name")
    p_create.add_argument("--aspect-ratio", default="16:9", help="Aspect ratio (default 16:9)")
    p_create.add_argument("--fps", type=int, default=30, help="Frames per second (default 30)")
    p_create.set_defaults(func=_cmd_create_project)

    p_plan = sub.add_parser("plan", help="Run script -> storyboard pipeline for a project")
    p_plan.add_argument("--project", required=True, help="Project id")
    p_plan.add_argument("--temperature", type=float, default=0.2, help="LLM temperature (default 0.2)")
    p_plan.set_defaults(func=_cmd_plan)

    p_voice = sub.add_parser("generate-voice", help="Generate TTS per scene (OmniVoice)")
    p_voice.add_argument("--project", required=True, help="Project id")
    p_voice.set_defaults(func=_cmd_generate_voice)

    p_img = sub.add_parser("generate-images", help="Generate images per scene/role")
    p_img.add_argument("--project", required=True, help="Project id")
    p_img.add_argument(
        "--image-provider",
        choices=["auto", "flowkit", "cliproxy_image", "antigravity_image"],
        default=None,
        help="Image provider override; default comes from native runtime settings",
    )
    p_img.set_defaults(func=_cmd_generate_images)

    p_render = sub.add_parser("render", help="Render every scene to scenes/*.mp4 (P7-T02)")
    p_render.add_argument("--project", required=True, help="Project id")
    p_render.set_defaults(func=_cmd_render)
    p_render_alias = sub.add_parser("render-scenes", help="Alias for render")
    p_render_alias.add_argument("--project", required=True, help="Project id")
    p_render_alias.set_defaults(func=_cmd_render)

    p_compose = sub.add_parser(
        "compose", help="Concat scenes + audio into final/final.mp4 (P7-T03)"
    )
    p_compose.add_argument("--project", required=True, help="Project id")
    p_compose.add_argument(
        "--audio", default=None, help="Override audio track path (optional)"
    )
    p_compose.set_defaults(func=_cmd_compose)
    p_compose_alias = sub.add_parser("render-final", help="Alias for compose")
    p_compose_alias.add_argument("--project", required=True, help="Project id")
    p_compose_alias.add_argument("--audio", default=None, help="Override audio track path (optional)")
    p_compose_alias.set_defaults(func=_cmd_compose)

    p_status = sub.add_parser("status", help="Show project status and scene states")
    p_status.add_argument("--project", required=True, help="Project id")
    p_status.set_defaults(func=_cmd_status)

    p_run = sub.add_parser("run", help="Full end-to-end pipeline: script -> final.mp4")
    p_run.add_argument("--script", required=True, help="Path to the script .txt file")
    p_run.add_argument("--title", default="", help="Project title (optional)")
    p_run.add_argument("--style", default="editorial_collage", help="Style preset name")
    p_run.add_argument("--aspect-ratio", default="16:9", help="Aspect ratio (default 16:9)")
    p_run.add_argument("--fps", type=int, default=30, help="Frames per second (default 30)")
    p_run.add_argument(
        "--image-provider",
        choices=["auto", "flowkit", "cliproxy_image", "antigravity_image"],
        default="auto",
    )
    p_run.add_argument("--motion-tier", default="local")
    p_run.add_argument("--voice-profile", default="voice_vi_01")
    p_run.set_defaults(func=_cmd_run)

    p_resume = sub.add_parser("resume", help="Resume a project from where it stopped")
    p_resume.add_argument("--project", required=True, help="Project id")
    p_resume.set_defaults(func=_cmd_resume)

    p_retry = sub.add_parser("retry-scene", help="Retry a specific scene from a stage")
    p_retry.add_argument("--project", required=True, help="Project id")
    p_retry.add_argument("--scene", required=True, help="Scene id (e.g. scene_004)")
    p_retry.add_argument(
        "--from", dest="from_stage", default="image",
        choices=["image", "voice", "layers", "render"],
        help="Stage to retry from (default: image)",
    )
    p_retry.set_defaults(func=_cmd_retry_scene)

    return parser


def _pause_if_frozen() -> None:
    """When running as a frozen EXE (double-click), pause so the user can read output."""
    if getattr(sys, "frozen", False):
        print("\nPress Enter to exit...")
        with contextlib.suppress(EOFError):
            input()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()

    # No arguments → show help instead of argparse error
    if not argv:
        parser.print_help()
        _pause_if_frozen()
        return 0

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        _pause_if_frozen()
        return 1
    finally:
        # Always pause when frozen so double-click users can read output
        if getattr(sys, "frozen", False) and argv:
            _pause_if_frozen()


if __name__ == "__main__":
    raise SystemExit(main())
