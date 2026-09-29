#!/usr/bin/env python3
"""Demo script: run the complete Vox pipeline end-to-end.

Usage:
    python demo_pipeline.py [--script <path>] [--style <preset>] [--aspect <ratio>] [--fps <n>]

This script drives the full workflow:
1. Create project from script
2. Plan (script → storyboard via LLM)
3. Generate images (per scene, per role)
4. Prepare layers (Strategy A: direct layers)
5. Motion planning (LLM + template fallback)
6. Render scenes (FFmpeg motion compiler + local renderer)
7. Generate TTS per scene (OmniVoice worker)
8. Compose final video (concat scenes + audio)

All steps use the real services (no fakes), so external dependencies must be running:
- CLIProxy at http://127.0.0.1:8317/v1 (LLM + image)
- OmniVoice worker at http://127.0.0.1:8791 (TTS)
- FFmpeg + ffprobe on PATH
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).parent))

from app.services.image_generation import ImageGenerationService
from app.services.layer_workflow import LayerWorkflow
from app.services.motion_planner import MotionPlannerService
from app.services.tts_pipeline import TTSScenePipeline
from app.providers.llm.cliproxy import CliproxyLLMProvider
from app.providers.image.antigravity import AntigravityImageProvider
from app.providers.tts.omnivoice import OmniVoiceProvider
from app.services.scene_renderer import LocalSceneRenderer
from app.services.final_composer import FinalComposer
from app.services.project_manager import ProjectManager
from app.storage import database
from app.storage.asset_store import AssetStore
from app.storage.repositories import SceneRepo, AssetRepo
from app.models import Asset


def print_step(step: str, msg: str = "") -> None:
    prefix = f"\n{'='*60}\n[STEP] {step}"
    if msg:
        prefix += f" - {msg}"
    print(prefix)
    print("=" * 60)


def print_result(label: str, data: dict) -> None:
    print(f"\n[OK] {label}:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def run_demo(
    script_path: Path,
    style: str = "editorial_collage",
    aspect_ratio: str = "16:9",
    fps: int = 30,
) -> Path:
    """Run the full pipeline and return the final MP4 path."""

    # Initialize database
    database.init_schema()

    # ----------------------------------------------------------------------- #
    # Step 1: Create project
    # ----------------------------------------------------------------------- #
    print_step("1/8", "Create project from script")
    script_text = script_path.read_text(encoding="utf-8")

    with database.create_session() as session:
        manager = ProjectManager(session)
        project, created = manager.create_project(
            script_text,
            title=script_path.stem,
            style_preset=style,
            aspect_ratio=aspect_ratio,
            fps=fps,
        )
        project_id = project["project_id"]
        print_result("Project created" if created else "Project reused", project)

    # ----------------------------------------------------------------------- #
    # Step 2: Plan (script → storyboard)
    # ----------------------------------------------------------------------- #
    print_step("2/8", "Generate storyboard via LLM")
    with database.create_session() as session:
        manager = ProjectManager(session)
        planner = CliproxyLLMProvider()
        from app.services.script_analysis import ScriptAnalyzer
        from app.services.prompts import load_presets
        presets = load_presets()
        preset = presets.get(style)
        analyzer = ScriptAnalyzer(planner, style_preset=preset)
        try:
            result = await manager.plan(project_id, analyzer, temperature=0.2)
        finally:
            await planner.aclose()
    print_result("Storyboard generated", result)

    # ----------------------------------------------------------------------- #
    # Step 3: Generate images
    # ----------------------------------------------------------------------- #
    print_step("3/8", "Generate images per scene/role")
    image_provider = AntigravityImageProvider()
    image_service = ImageGenerationService(image_provider=image_provider)

    with database.create_session() as session:
        img_result = await image_service.generate_project(project_id, session=session)
    print_result("Images generated", {
        "project_id": img_result.project_id,
        "total_scenes": img_result.total_scenes,
        "generated": img_result.generated,
        "cached": img_result.cached,
        "errors": img_result.errors,
    })

    # ----------------------------------------------------------------------- #
    # Step 4: Prepare layers (Strategy A: direct layers)
    # ----------------------------------------------------------------------- #
    print_step("4/8", "Prepare layers (normalize + align + manifest)")
    layer_wf = LayerWorkflow()

    with database.create_session() as session:
        manager = ProjectManager(session)
        scenes_index = manager._load_scenes_index(project_id)
        store = AssetStore()
        for scene_id in scenes_index:
            # Load the selected composite image for this scene
            # The image service stores selected asset in Scene.selected_image_asset_id
            scene = SceneRepo.get(session, project_id, scene_id)
            if scene and scene.selected_image_asset_id:
                asset = session.get(Asset, scene.selected_image_asset_id)
                if asset:
                    layer_wf.prepare_composite(
                        project_id, scene_id, str(asset.path), store=store
                    )

    # Also prepare layers for all scenes from individual role assets
    with database.create_session() as session:
        manager = ProjectManager(session)
        scenes_index = manager._load_scenes_index(project_id)
        store = AssetStore()
        for scene_id in scenes_index:
            # Build layer package from available role files
            layers_dir = store.subdir(project_id, "layers")
            layer_package = {}
            for role in ("background", "subject", "foreground", "texture", "composite"):
                candidate = layers_dir / f"{scene_id}_{role}.png"
                if candidate.is_file():
                    layer_package[role] = str(candidate)
            if layer_package:
                layer_wf.prepare_scene(
                    project_id, scene_id, layer_package, store=store
                )
    print_result("Layers prepared", {"scenes": scenes_index})

    # ----------------------------------------------------------------------- #
    # Step 5: Motion planning
    # ----------------------------------------------------------------------- #
    print_step("5/8", "Plan motion per scene (voice duration + template + assets)")
    motion_planner = MotionPlannerService()

    with database.create_session() as session:
        manager = ProjectManager(session)
        scenes_index = manager._load_scenes_index(project_id)
        layers_dir = store.subdir(project_id, "layers")
        store = AssetStore()

        contexts = []
        for scene_id in scenes_index:
            # Get voice duration from Scene row (TTS will populate later; use fallback for now)
            scene = SceneRepo.get(session, project_id, scene_id)
            voice_ms = int(scene.actual_voice_duration_ms) if scene and scene.actual_voice_duration_ms else 5000

            # Get available layer roles from disk
            available = frozenset(
                p.stem.replace(f"{scene_id}_", "", 1)
                for p in layers_dir.glob(f"{scene_id}_*.png")
            )

            # Get the storyboard scene's template
            storyboard = json.loads(
                (store.subdir(project_id, "manifests") / "storyboard.json").read_text(encoding="utf-8")
            )
            scene_data = next((s for s in storyboard["scenes"] if s["scene_id"] == scene_id), {})
            template = scene_data.get("motion_template", "01_subject_slide_headline_pop")

            from app.services.motion_planner import SceneMotionContext
            contexts.append(SceneMotionContext(
                scene_id=scene_id,
                voice_duration_ms=voice_ms,
                canvas_size=(1920, 1080) if aspect_ratio == "16:9" else (1080, 1920),
                available_roles=available,
                seed=42,
                template_name=template,
            ))

        plan_result = await motion_planner.plan_project(project_id, contexts)

    # Persist motion plans to disk (manifests/motion/{scene_id}.json)
    for result in plan_result.scenes:
        if result.plan:
            motion_dir = store.subdir(project_id, "manifests") / "motion"
            motion_dir.mkdir(parents=True, exist_ok=True)
            (motion_dir / f"{result.scene_id}.json").write_text(
                json.dumps(result.plan.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    print_result("Motion planned", {
        "project_id": plan_result.project_id,
        "scenes_count": len(plan_result.scenes),
        "all_have_plan": plan_result.all_scenes_have_plan,
        "errors": [r.error for r in plan_result.scenes if r.error],
    })

    # ----------------------------------------------------------------------- #
    # Step 6: Render scenes
    # ----------------------------------------------------------------------- #
    print_step("6/8", "Render scenes to MP4 (FFmpeg motion compiler)")
    renderer = LocalSceneRenderer()

    with database.create_session() as session:
        manager = ProjectManager(session)
        # Don't pass layer_workflow/motion_planner - we already did those steps
        # render_project has a bug where it calls prepare_scene with wrong signature
        render_result = await manager.render_project(
            project_id,
            renderer=renderer,
        )
    print_result("Scenes rendered", {
        "project_id": render_result["project_id"],
        "rendered_count": len(render_result["rendered"]),
        "scenes": render_result["rendered"],
    })

    # ----------------------------------------------------------------------- #
    # Step 7: Generate TTS
    # ----------------------------------------------------------------------- #
    print_step("7/8", "Generate TTS per scene (OmniVoice worker)")
    tts_provider = OmniVoiceProvider()
    tts_pipeline = TTSScenePipeline(tts_provider)

    with database.create_session() as session:
        tts_result = await tts_pipeline.run(project_id, session, project_root=AssetStore().base)
    print_result("TTS generated", {
        "project_id": tts_result.project_id,
        "total_scenes": tts_result.total_scenes,
        "generated": tts_result.generated,
        "cached": tts_result.cached,
        "errors": tts_result.errors,
    })

    # ----------------------------------------------------------------------- #
    # Step 8: Compose final video
    # ----------------------------------------------------------------------- #
    print_step("8/8", "Compose final MP4 (concat scenes + audio)")
    composer = FinalComposer()

    with database.create_session() as session:
        manager = ProjectManager(session)
        final_path = manager.compose_final(project_id, composer=composer)
    print_result("Final video composed", {"final_mp4": str(final_path)})

    return final_path


def main():
    parser = argparse.ArgumentParser(description="Run Vox pipeline demo")
    parser.add_argument("--script", default="tests/fixtures/sample_script.txt", help="Path to script file")
    parser.add_argument("--style", default="editorial_collage", help="Style preset")
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "9:16", "1:1"], help="Aspect ratio")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.is_file():
        print(f"❌ Script not found: {script_path}", file=sys.stderr)
        return 1

    print(f"\nVOX PIPELINE DEMO")
    print(f"   Script: {script_path}")
    print(f"   Style: {args.style}")
    print(f"   Aspect: {args.aspect_ratio}")
    print(f"   FPS: {args.fps}")

    try:
        final_mp4 = asyncio.run(run_demo(
            script_path=script_path,
            style=args.style,
            aspect_ratio=args.aspect_ratio,
            fps=args.fps,
        ))
        print(f"\nSUCCESS! Final video: {final_mp4}")
        return 0
    except Exception as e:
        print(f"\n❌ FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())