"""FastAPI web application with embedded HTML dashboard.

Serves a single-page UI at ``/`` that lets the user:
- View system status (doctor)
- Create projects from a script
- Run the full pipeline
- Check project status
- Browse project files

All heavy work is dispatched to background tasks; the UI polls for progress.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.ui.vox_studio_shell import render_shell
from app.version import APP_VERSION

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Auto Storyboard Vox", version=APP_VERSION)

# In-memory job tracker  {job_id: {status, step, detail, result}}
_jobs: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    from app import config
    return Path(config.REPO_ROOT)


def _projects_dir() -> Path:
    from app.settings import get_settings
    return Path(get_settings().project_root)


def _project_store(project_id: str):
    from app.storage.asset_store import AssetStore

    return AssetStore(_projects_dir()), project_id


def _project_session():
    from app.storage import database

    database.init_schema()
    return database.create_session()


def _json_file(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def _safe_project_path(project_id: str, relative: str) -> Path:
    root = (_projects_dir() / project_id).resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(400, "invalid artifact path")
    if not candidate.is_file():
        raise HTTPException(404, "artifact not found")
    return candidate


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/providers/health")
async def providers_health() -> dict[str, Any]:
    from app.tooling.doctor import run_all

    return run_all()


@app.get("/api/doctor")
async def api_doctor():
    """Run doctor check and return JSON report."""
    from app.tooling.doctor import run_all

    return JSONResponse(run_all())


@app.get("/api/projects")
async def api_projects():
    """List existing projects."""
    projects_dir = _projects_dir()
    projects = []
    if projects_dir.is_dir():
        for p in sorted(projects_dir.iterdir()):
            if p.is_dir():
                manifest = p / "manifests" / "storyboard.json"
                final = p / "final" / "final.mp4"
                projects.append({
                    "project_id": p.name,
                    "has_storyboard": manifest.is_file(),
                    "has_final": final.is_file(),
                })
    return {"projects": projects}


@app.get("/api/vox/catalogs")
async def vox_catalogs() -> dict[str, Any]:
    return {
        "styles": [
            {"id": "editorial_collage", "label": "Vox Classic (Editorial)", "description": "Editorial collage"},
            {"id": "johnny_harris_geopolitics", "label": "Johnny Harris (Maps & Geopolitics)", "description": "Terrain maps & geopolitical borders"},
            {"id": "magnates_media_billionaires", "label": "Magnates Media (Billionaires & Business)", "description": "Cinematic dark noir financial exposé"},
            {"id": "true_crime_dossier", "label": "True Crime (Police Dossier)", "description": "Tactical forensic investigation corkboard"},
            {"id": "archival_vintage_history", "label": "Archival Vintage (History & Biographies)", "description": "Aged museum parchment & historical dossiers"},
            {"id": "cyberpunk_tech_breakdown", "label": "Cyberpunk Tech (AI & Silicon Valley)", "description": "Futuristic neon blueprint HUD breakdown"},
            {"id": "tactical_investigation", "label": "Tactical Radar (Military & Aviation)", "description": "Tactical investigation board with 360 radar"},
            {"id": "documentary", "label": "Vox Documentary", "description": "Documentary contrast"},
            {"id": "minimal_motion", "label": "Vox Modern", "description": "Minimal motion"},
        ],
        "aspect_ratios": ["9:16", "16:9", "1:1"],
        "fps": [24, 25, 30, 60],
        "render": {"formats": ["mp4"], "video_codec": "h264", "audio_codec": "aac"},
    }


@app.get("/api/vox/projects")
async def vox_projects() -> dict[str, Any]:
    projects_dir = _projects_dir()
    rows: list[dict[str, Any]] = []
    if projects_dir.is_dir():
        for path in sorted(projects_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_dir() or path.name.startswith("."):
                continue
            manifest = _json_file(path / "manifests" / "storyboard.json", {})
            final = path / "final" / "final.mp4"
            scenes = manifest.get("scenes", []) if isinstance(manifest, dict) else []
            rows.append({
                "project_id": path.name,
                "title": manifest.get("title") or (scenes[0].get("narration_text", "") if scenes else path.name)[:80],
                "status": "COMPLETED" if final.is_file() else "IN_PROGRESS" if manifest else "NEW",
                "scene_count": len(scenes),
                "has_final": final.is_file(),
                "final_mp4": str(final) if final.is_file() else None,
                "updated_at": path.stat().st_mtime,
            })
    return {"projects": rows}


@app.post("/api/vox/projects")
async def vox_create_project(request: Request) -> dict[str, Any]:
    body = await request.json()
    script = str(body.get("script") or "").strip()
    if not script:
        raise HTTPException(400, "script text is required")
    from app.services.project_manager import ProjectManager

    with _project_session() as session:
        manager = ProjectManager(session)
        project, _created = manager.create_project(
            script,
            title=str(body.get("title") or ""),
            style_preset=str(body.get("style") or "editorial_collage"),
            aspect_ratio=str(body.get("aspect_ratio") or "16:9"),
            fps=int(body.get("fps") or 30),
        )
    return project


@app.get("/api/vox/projects/{project_id}")
async def vox_project(project_id: str) -> dict[str, Any]:
    from app.services.project_manager import ProjectManager, ProjectManagerError

    try:
        with _project_session() as session:
            project = ProjectManager(session).get_project(project_id)
    except ProjectManagerError as exc:
        raise HTTPException(404, str(exc)) from exc
    return project


@app.get("/api/vox/projects/{project_id}/script")
async def vox_script(project_id: str) -> dict[str, Any]:
    root = (_projects_dir() / project_id).resolve()
    script_path = root / "input" / "script.txt"
    if not root.is_dir() or not script_path.is_file():
        with _project_session() as session:
            from app.storage.repositories import ProjectRepo

            project = ProjectRepo.get(session, project_id)
            if project is None:
                raise HTTPException(404, "project not found")
            return {"project_id": project_id, "script": project.script_text or ""}
    manifest = _json_file(root / "manifests" / "storyboard.json", {})
    return {"project_id": project_id, "script": script_path.read_text(encoding="utf-8") if script_path.is_file() else manifest.get("script_text", "")}


@app.put("/api/vox/projects/{project_id}/script")
async def vox_save_script(project_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    script = str(body.get("script") or "").strip()
    if not script:
        raise HTTPException(400, "script text is required")
    from app.services.project_manager import ProjectManager, sha256_text
    from app.storage.repositories import ProjectRepo

    with _project_session() as session:
        manager = ProjectManager(session)
        try:
            project = manager.get_project(project_id)
        except Exception as exc:
            raise HTTPException(404, "project not found") from exc
        path = manager.store.write_project_file(project_id, "input/script.txt", script.encode("utf-8"))
        row = ProjectRepo.get(session, project_id)
        row.script_text = script
        row.script_hash = sha256_text(script)
        row.title = str(body.get("title") or project.get("title") or script.splitlines()[0][:120])
        session.commit()
    return {"project_id": project_id, "saved": True, "path": str(path)}


@app.get("/api/vox/projects/{project_id}/scenes")
async def vox_scenes(project_id: str) -> dict[str, Any]:
    from app.storage.repositories import SceneRepo

    with _project_session() as session:
        scenes = SceneRepo.list(session, project_id)
        if not scenes:
            manifest = _json_file(_projects_dir() / project_id / "manifests" / "storyboard.json", {})
            return {"project_id": project_id, "scenes": manifest.get("scenes", []) if isinstance(manifest, dict) else []}
        return {"project_id": project_id, "scenes": [{
            "scene_id": s.scene_id, "order": s.order, "narration_text": s.narration_text,
            "purpose": s.purpose, "image_prompt": s.image_prompt,
            "estimated_duration_seconds": s.estimated_duration_seconds,
            "actual_voice_duration_ms": s.actual_voice_duration_ms, "status": s.status,
            "selected_image_asset_id": s.selected_image_asset_id,
        } for s in scenes]}


@app.post("/api/vox/projects/{project_id}/plan")
async def vox_plan(project_id: str) -> dict[str, Any]:
    return await _start_vox_job(project_id, "plan")


@app.post("/api/vox/projects/{project_id}/scenes/{scene_id}/prompt")
async def vox_save_prompt(project_id: str, scene_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")
    from app.storage.repositories import SceneRepo

    with _project_session() as session:
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None:
            raise HTTPException(404, "scene not found")
        scene.image_prompt = prompt
        session.commit()
    return {"project_id": project_id, "scene_id": scene_id, "saved": True, "prompt": prompt}


@app.post("/api/vox/projects/{project_id}/scenes/{scene_id}/images/generate")
async def vox_generate_image(project_id: str, scene_id: str) -> dict[str, Any]:
    return await _start_vox_job(project_id, "image", scene_id=scene_id)


@app.get("/api/vox/projects/{project_id}/images")
async def vox_images(project_id: str) -> dict[str, Any]:
    from app.storage.repositories import AssetRepo

    with _project_session() as session:
        assets = AssetRepo.list(session, project_id)
        return {"project_id": project_id, "images": [{
            "asset_id": asset.asset_id, "scene_id": asset.scene_id, "role": asset.role,
            "path": asset.path, "selected": asset.selected, "width": asset.width,
            "height": asset.height, "version": asset.version,
        } for asset in assets]}


@app.post("/api/vox/projects/{project_id}/voice")
async def vox_generate_voice(project_id: str) -> dict[str, Any]:
    return await _start_vox_job(project_id, "voice")


@app.post("/api/vox/projects/{project_id}/captions")
async def vox_generate_captions(project_id: str) -> dict[str, Any]:
    return await _start_vox_job(project_id, "caption")


@app.get("/api/vox/projects/{project_id}/captions")
async def vox_captions(project_id: str) -> dict[str, Any]:
    path = _projects_dir() / project_id / "final" / "subtitles.srt"
    return {"project_id": project_id, "exists": path.is_file(), "path": str(path) if path.is_file() else None}


@app.post("/api/vox/projects/{project_id}/render")
async def vox_render(project_id: str) -> dict[str, Any]:
    return await _start_vox_job(project_id, "render")


@app.get("/api/vox/voices")
async def vox_voices() -> dict[str, Any]:
    from app.providers.tts.omnivoice import OmniVoiceProvider

    provider = OmniVoiceProvider(timeout_seconds=3)
    try:
        health = await provider.health()
        if health.status != "ok":
            return {"status": health.status, "voices": [], "detail": health.detail}
        return {"status": "ok", "voices": health.detail.get("voices", []) if isinstance(health.detail, dict) else []}
    finally:
        await provider.aclose()


@app.get("/api/vox/projects/{project_id}/voices")
async def vox_project_voices(project_id: str) -> dict[str, Any]:
    del project_id
    return await vox_voices()


@app.get("/api/vox/projects/{project_id}/style")
async def vox_style(project_id: str) -> dict[str, Any]:
    manifest = _json_file(_projects_dir() / project_id / "manifests" / "storyboard.json", {})
    return {"project_id": project_id, "style": manifest.get("style_anchor", {}), "preset": manifest.get("style_preset", "editorial_collage")}


@app.put("/api/vox/projects/{project_id}/style")
async def vox_save_style(project_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    root = _projects_dir() / project_id
    if not root.is_dir():
        raise HTTPException(404, "project not found")
    manifest_path = root / "manifests" / "storyboard.json"
    manifest = _json_file(manifest_path, {"project_id": project_id})
    manifest["style_preset"] = str(body.get("preset") or manifest.get("style_preset") or "editorial_collage")
    manifest["style_anchor"] = body.get("style") or manifest.get("style_anchor", {})
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"project_id": project_id, "saved": True, "preset": manifest["style_preset"]}


@app.get("/api/vox/projects/{project_id}/artifacts")
async def vox_artifacts(project_id: str) -> dict[str, Any]:
    root = (_projects_dir() / project_id).resolve()
    if not root.is_dir():
        raise HTTPException(404, "project not found")
    artifacts = []
    for kind in ("audio", "final", "scenes", "images"):
        folder = root / kind
        if folder.is_dir():
            artifacts.extend({"kind": kind, "name": p.name, "bytes": p.stat().st_size, "url": f"/api/vox/media/{project_id}/{kind}/{p.name}"} for p in folder.iterdir() if p.is_file())
    return {"project_id": project_id, "artifacts": artifacts}


@app.get("/api/vox/media/{project_id}/{artifact_kind}/{name}")
async def vox_media(project_id: str, artifact_kind: str, name: str):
    from fastapi.responses import FileResponse

    path = _safe_project_path(project_id, f"{artifact_kind}/{name}")
    return FileResponse(path)


async def _start_vox_job(
    project_id: str,
    action: str,
    *,
    scene_id: str | None = None,
) -> dict[str, Any]:
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "status": "running",
        "step": action,
        "action": action,
        "progress": 0,
        "detail": "Starting...",
        "events": [],
        "project_id": project_id,
        "scene_id": scene_id,
        "cancel_requested": False,
        "result": None,
    }
    asyncio.create_task(_run_vox_action(job_id, project_id, action, scene_id=scene_id))
    return {"job_id": job_id, "project_id": project_id, "action": action}


async def _run_vox_action(
    job_id: str,
    project_id: str,
    action: str,
    *,
    scene_id: str | None = None,
) -> None:
    job = _jobs[job_id]
    try:
        if action == "plan":
            job["detail"] = "Generating storyboard via CLIProxy..."
            with _project_session() as session:
                from app.providers.llm.cliproxy import CliproxyLLMProvider
                from app.services.project_manager import ProjectManager
                from app.services.prompts import load_presets
                from app.services.script_analysis import ScriptAnalyzer
                from app.storage.repositories import ProjectRepo

                project = ProjectRepo.get(session, project_id)
                if project is None:
                    raise HTTPException(404, "project not found")
                provider = CliproxyLLMProvider()
                try:
                    result = await ProjectManager(session).plan(
                        project_id,
                        ScriptAnalyzer(provider, style_preset=load_presets().get(project.style_preset)),
                    )
                finally:
                    await provider.aclose()
            job["result"] = result
        elif action == "image":
            if not scene_id:
                raise ValueError("scene_id is required for image generation")
            job["detail"] = "Image generation wiring is ready; provider execution is next vertical slice."
            job["status"] = "failed"
            job["detail"] = "Image generation endpoint requires a live provider-backed scene worker."
            return
        elif action in {"voice", "caption", "render"}:
            job["detail"] = f"{action} action requires its provider/artifact prerequisites."
            job["status"] = "failed"
            return
        else:
            raise ValueError(f"unsupported Vox job action: {action}")
        job["progress"] = 100
        job["status"] = "completed"
        job["detail"] = "Completed"
    except Exception as exc:  # noqa: BLE001
        job["status"] = "failed"
        job["detail"] = str(exc)


@app.post("/api/run")
async def api_run(request: Request):
    """Start full pipeline in background. Returns a job_id to poll."""
    body = await request.json()
    script_text = body.get("script", "").strip()
    if not script_text:
        raise HTTPException(400, "script text is required")

    job_id = str(uuid.uuid4())[:8]
    project_id = str(body.get("project_id") or f"web_{job_id}")
    body["project_id"] = project_id
    _jobs[job_id] = {
        "status": "running",
        "step": "starting",
        "detail": "",
        "result": None,
        "project_id": project_id,
        "cancel_requested": False,
    }

    asyncio.create_task(_run_pipeline(job_id, script_text, body))
    return {"job_id": job_id, "project_id": project_id}


@app.get("/api/job/{job_id}")
async def api_job(job_id: str):
    """Poll job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.post("/projects/{project_id}/cancel")
async def cancel_project(project_id: str) -> dict[str, str]:
    for job in _jobs.values():
        if job.get("project_id") == project_id and job.get("status") == "running":
            job["cancel_requested"] = True
            job["detail"] = "Cancellation requested; the current stage may finish before stopping."
            return {"project_id": project_id, "status": "cancelling"}
    raise HTTPException(404, "running project job not found")


async def _run_pipeline(job_id: str, script_text: str, opts: dict):
    """Run the pipeline steps, updating _jobs[job_id] along the way."""
    job = _jobs[job_id]
    try:
        # Write script to temp file
        tmp = _projects_dir() / f".tmp_script_{job_id}.txt"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(script_text, encoding="utf-8")

        # We re-use the CLI internals
        from app.cli import main as cli_main

        job["step"] = "pipeline"
        job["detail"] = "Running full pipeline..."

        # Run in executor to not block event loop
        loop = asyncio.get_event_loop()
        rc = await loop.run_in_executor(
            None,
            cli_main,
            ["run", "--script", str(tmp),
             "--style", opts.get("style", "editorial_collage"),
             "--aspect-ratio", opts.get("aspect_ratio", "16:9")],
        )

        tmp.unlink(missing_ok=True)

        if job.get("cancel_requested"):
            job["status"] = "cancelled"
            job["detail"] = "Pipeline cancelled after the current stage finished."
        elif rc == 0:
            job["status"] = "completed"
            job["detail"] = "Pipeline finished successfully"
            project_id = opts.get("project_id")
            if project_id:
                job["result"] = {
                    "project_id": project_id,
                    "final_mp4": str(_projects_dir() / project_id / "final" / "final.mp4"),
                }
        else:
            job["status"] = "failed"
            job["detail"] = f"Pipeline exited with code {rc}"

    except Exception as e:
        job["status"] = "failed"
        job["detail"] = str(e)


# ---------------------------------------------------------------------------
# HTML Dashboard (embedded - no external templates needed)
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = render_shell()

_LEGACY_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vox Studio v0.3.0</title>
<style>
  :root {
    --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a;
    --text: #e4e4e7; --muted: #8b8d98; --accent: #6366f1;
    --accent-hover: #818cf8; --success: #22c55e; --error: #ef4444;
    --warning: #f59e0b;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh;
  }
  .container { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
  .subtle { color: var(--muted); font-size: 0.8rem; line-height: 1.45; }
  .error-box { margin-top: 0.7rem; padding: 0.65rem 0.75rem; border: 1px solid rgba(239,68,68,0.45); border-radius: 8px; color: #fecaca; background: rgba(239,68,68,0.08); }
  .success-box { margin-top: 0.7rem; padding: 0.65rem 0.75rem; border: 1px solid rgba(34,197,94,0.45); border-radius: 8px; color: #bbf7d0; background: rgba(34,197,94,0.08); }
  .progress-track { height: 8px; margin-top: 0.8rem; border-radius: 999px; background: var(--border); overflow: hidden; }
  .progress-bar { height: 100%; width: 0%; background: var(--accent); transition: width 0.25s ease; }
  .stepper { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.35rem; margin-top: 1rem; }
  .step { padding: 0.45rem 0.2rem; border-top: 3px solid var(--border); color: var(--muted); font-size: 0.7rem; text-align: center; }
  .step.active { border-color: var(--accent); color: var(--text); }
  .step.done { border-color: var(--success); color: var(--success); }
  .step.failed { border-color: var(--error); color: var(--error); }
  .project-list li { gap: 0.7rem; }
  .project-list li > span:first-child { min-width: 0; overflow-wrap: anywhere; }
  .project-meta { display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; justify-content: flex-end; }
  button:focus-visible, select:focus-visible, textarea:focus-visible { outline: 3px solid #a5b4fc; outline-offset: 2px; }
  @media (max-width: 640px) {
    .container { padding: 1rem; }
    header { padding-top: 1rem; margin-bottom: 1rem; }
    .select-row { display: grid; grid-template-columns: 1fr; }
    .select-row > div, select, #run-btn { width: 100%; }
    .stepper { grid-template-columns: repeat(3, 1fr); }
    .step { font-size: 0.65rem; }
    .project-list li { align-items: flex-start; flex-direction: column; }
    .project-meta { justify-content: flex-start; }
  }
  header {
    text-align: center; padding: 2rem 0 1rem;
    border-bottom: 1px solid var(--border); margin-bottom: 2rem;
  }
  header h1 { font-size: 1.8rem; font-weight: 700; letter-spacing: -0.02em; }
  header h1 span { color: var(--accent); }
  header p { color: var(--muted); margin-top: 0.3rem; font-size: 0.9rem; }

  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; margin-bottom: 2rem; }
  @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }

  .card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.4rem; transition: border-color 0.2s;
  }
  .card:hover { border-color: var(--accent); }
  .card h2 { font-size: 1rem; font-weight: 600; margin-bottom: 0.8rem; display: flex; align-items: center; gap: 0.5rem; }
  .card h2 .icon { font-size: 1.2rem; }

  .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.85rem; }
  .status-item { display: flex; justify-content: space-between; padding: 0.3rem 0; }
  .status-item .label { color: var(--muted); }
  .badge {
    padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;
  }
  .badge-ok { background: rgba(34,197,94,0.15); color: var(--success); }
  .badge-err { background: rgba(239,68,68,0.15); color: var(--error); }
  .badge-warn { background: rgba(245,158,11,0.15); color: var(--warning); }
  .badge-run { background: rgba(99,102,241,0.15); color: var(--accent); }

  .full-width { grid-column: 1 / -1; }

  textarea {
    width: 100%; min-height: 150px; background: var(--bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 8px; padding: 0.8rem;
    font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.85rem;
    resize: vertical; outline: none; transition: border-color 0.2s;
  }
  textarea:focus { border-color: var(--accent); }

  .btn-row { display: flex; gap: 0.8rem; margin-top: 1rem; flex-wrap: wrap; }
  button, .btn {
    padding: 0.6rem 1.4rem; border: none; border-radius: 8px;
    font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
    text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem;
  }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent-hover); transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .btn-secondary { background: var(--border); color: var(--text); }
  .btn-secondary:hover { background: #3a3d4a; }

  .select-row { display: flex; gap: 0.8rem; margin-top: 0.8rem; flex-wrap: wrap; align-items: center; }
  select {
    padding: 0.5rem 0.8rem; background: var(--bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 8px; font-size: 0.85rem;
    outline: none;
  }
  select:focus { border-color: var(--accent); }
  label { color: var(--muted); font-size: 0.8rem; }

  .log-box {
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 0.8rem; margin-top: 1rem; font-family: monospace; font-size: 0.8rem;
    max-height: 200px; overflow-y: auto; white-space: pre-wrap; color: var(--muted);
  }

  .project-list { list-style: none; }
  .project-list li {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.6rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem;
  }
  .project-list li:last-child { border-bottom: none; }
  .project-name { font-weight: 600; font-family: monospace; }

  .spinner {
    display: inline-block; width: 14px; height: 14px;
    border: 2px solid var(--border); border-top-color: var(--accent);
    border-radius: 50%; animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  footer {
    text-align: center; padding: 2rem 0 1rem; color: var(--muted);
    font-size: 0.75rem; border-top: 1px solid var(--border); margin-top: 2rem;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🎬 Auto <span>Storyboard</span> Vox</h1>
    <p>Script → Storyboard → Voice → Images → Motion → Video</p>
  </header>

  <div class="grid">
    <!-- System Status -->
    <div class="card">
      <h2><span class="icon">⚙️</span> System Status</h2>
      <div id="doctor-status" role="status" aria-live="polite"><span class="badge badge-warn">Checking...</span></div>
      <div id="doctor-grid" class="status-grid" style="margin-top:0.8rem"></div>
      <div class="btn-row">
        <button class="btn btn-secondary" type="button" onclick="runDoctor()">🔄 Refresh system status</button>
      </div>
    </div>

    <!-- Projects -->
    <div class="card">
      <h2><span class="icon">📁</span> Projects</h2>
      <ul id="project-list" class="project-list" aria-live="polite">
        <li><span class="badge badge-warn">Loading projects...</span></li>
      </ul>
      <div class="btn-row">
        <button class="btn btn-secondary" type="button" onclick="loadProjects()">🔄 Refresh projects</button>
      </div>
    </div>

    <!-- Create & Run -->
    <div class="card full-width">
      <h2><span class="icon">🚀</span> Create Video</h2>
      <label for="script-input">Script <span class="subtle">(required)</span></label>
      <textarea id="script-input" aria-describedby="script-help" placeholder="Paste your script here...&#10;&#10;Each paragraph becomes a scene. The AI will generate storyboard, voice, images, motion, and compose the final video."></textarea>
      <div id="script-help" class="subtle">Each paragraph becomes a scene. The pipeline may take several minutes.</div>
      <div class="select-row">
        <div>
          <label for="style-select">Style</label><br>
          <select id="style-select" aria-label="Video style">
            <option value="editorial_collage" selected>Editorial Collage (Vox Classic)</option>
            <option value="johnny_harris_geopolitics">Johnny Harris (Maps & Geopolitics)</option>
            <option value="magnates_media_billionaires">Magnates Media (Billionaires & Business)</option>
            <option value="true_crime_dossier">True Crime (Police Dossier)</option>
            <option value="archival_vintage_history">Archival Vintage (History & Biographies)</option>
            <option value="cyberpunk_tech_breakdown">Cyberpunk Tech (AI & Silicon Valley)</option>
            <option value="tactical_investigation">Tactical Radar (Military & Aviation)</option>
            <option value="documentary">Documentary</option>
            <option value="minimal_motion">Minimal Motion</option>
          </select>
        </div>
        <div>
          <label for="ratio-select">Aspect Ratio</label><br>
          <select id="ratio-select" aria-label="Video aspect ratio">
            <option value="16:9" selected>16:9 (Landscape)</option>
            <option value="9:16">9:16 (Portrait)</option>
          </select>
        </div>
      </div>
      <div class="btn-row">
        <button id="run-btn" class="btn btn-primary" type="button" onclick="startPipeline()">▶ Run Pipeline</button>
        <button id="cancel-btn" class="btn btn-secondary" type="button" onclick="cancelPipeline()" disabled>⏹ Cancel</button>
      </div>
      <div id="job-status" style="display:none" role="status" aria-live="polite">
        <div class="log-box" id="job-log"></div>
        <div class="progress-track" aria-hidden="true"><div id="progress-bar" class="progress-bar"></div></div>
        <div id="pipeline-stepper" class="stepper" aria-label="Pipeline progress">
          <div class="step" data-step="script">Script</div><div class="step" data-step="storyboard">Storyboard</div><div class="step" data-step="voice">Voice</div><div class="step" data-step="images">Images</div><div class="step" data-step="motion">Motion</div><div class="step" data-step="video">Video</div>
        </div>
      </div>
    </div>
  </div>

  <footer>
    Auto Storyboard Vox v0.1.0 — Local Windows MVP
  </footer>
</div>

<script>
const API = '';

async function runDoctor() {
  document.getElementById('doctor-status').innerHTML = '<span class="badge badge-run"><span class="spinner"></span> checking...</span>';
  try {
    const r = await fetch(API + '/api/doctor');
    const d = await r.json();
    const checks = d.checks || [];
    const failed = checks.filter(c => c.status === 'error' || c.status === 'missing').length;
    const ok = d.core_ok && failed === 0;
    document.getElementById('doctor-status').innerHTML = ok
      ? '<span class="badge badge-ok">✓ All systems ready</span>'
      : `<span class="badge badge-warn">⚠ Degraded — ${failed} issue${failed === 1 ? '' : 's'}</span>`;
    const grid = document.getElementById('doctor-grid');
    grid.innerHTML = checks.map(c => {
      const cls = c.status === 'ok' ? 'badge-ok' : c.status === 'error' ? 'badge-err' : 'badge-warn';
      return `<div class="status-item"><span class="label">${escapeHtml(c.name)}</span><span class="badge ${cls}">${escapeHtml(c.status)}</span></div>`;
    }).join('');
  } catch(e) {
    document.getElementById('doctor-status').innerHTML = '<div class="error-box">Could not load system status. Check the backend, then try again.</div>';
  }
}

async function loadProjects() {
  try {
    const r = await fetch(API + '/api/projects');
    const d = await r.json();
    const list = document.getElementById('project-list');
    if (!d.projects.length) {
      list.innerHTML = '<li style="color:var(--muted)">No projects yet</li>';
      return;
    }
    list.innerHTML = (d.projects || []).map(p => {
      const badge = p.has_final ? '<span class="badge badge-ok">✓ final.mp4</span>'
                   : p.has_storyboard ? '<span class="badge badge-warn">● In progress</span>'
                   : '<span class="badge badge-run">＋ New</span>';
      return `<li><span class="project-name">${escapeHtml(p.project_id)}</span><span class="project-meta">${badge}</span></li>`;
    }).join('');
  } catch(e) {
    document.getElementById('project-list').innerHTML = '<li><div class="error-box">Could not load projects. Try Refresh projects.</div></li>';
  }
}

function escapeHtml(value) {
  const node = document.createElement('span');
  node.textContent = String(value ?? '');
  return node.innerHTML;
}

let _pollTimer = null;
let _currentJobId = null;
let _currentProjectId = null;
const STEP_ORDER = ['starting', 'storyboard', 'voice', 'images', 'motion', 'video', 'pipeline'];
function setRunState(running) {
  const btn = document.getElementById('run-btn');
  const cancel = document.getElementById('cancel-btn');
  btn.disabled = running;
  cancel.disabled = !running;
  btn.textContent = running ? '⏳ Running...' : '▶ Run Pipeline';
}
function updateStepper(step, status) {
  const index = STEP_ORDER.indexOf(String(step || 'starting').toLowerCase());
  document.querySelectorAll('#pipeline-stepper .step').forEach((el, i) => {
    el.className = 'step';
    if (status === 'failed' && i === Math.min(Math.max(index, 0), 5)) el.classList.add('failed');
    else if (i < Math.min(Math.max(index, 0), 6)) el.classList.add('done');
    else if (i === Math.min(Math.max(index, 0), 5)) el.classList.add('active');
  });
  const progress = status === 'completed' ? 100 : status === 'failed' || status === 'cancelled' ? 100 : Math.max(5, Math.round(Math.min(Math.max(index, 0), 6) / 6 * 100));
  document.getElementById('progress-bar').style.width = progress + '%';
}
async function cancelPipeline() {
  if (!_currentProjectId) return;
  const button = document.getElementById('cancel-btn');
  button.disabled = true;
  button.textContent = '⏳ Cancelling...';
  try {
    const r = await fetch(API + `/projects/${encodeURIComponent(_currentProjectId)}/cancel`, {method: 'POST'});
    const d = await r.json();
    document.getElementById('job-log').textContent += `\\n${d.status === 'cancelled' ? '⏹ Cancel requested.' : (d.detail || 'Cancel failed.')}`;
  } catch (e) {
    document.getElementById('job-log').textContent += `\\nCould not cancel: ${e.message}`;
    button.disabled = false;
  }
}
async function startPipeline() {
  const script = document.getElementById('script-input').value.trim();
  if (!script) { document.getElementById('script-input').focus(); document.getElementById('job-log').textContent = 'Please paste a script first.'; document.getElementById('job-status').style.display = 'block'; return; }
  setRunState(true);
  const jobDiv = document.getElementById('job-status');
  const jobLog = document.getElementById('job-log');
  jobDiv.style.display = 'block';
  jobLog.textContent = 'Starting pipeline...\\n';

  try {
    const r = await fetch(API + '/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        script: script,
        style: document.getElementById('style-select').value,
        aspect_ratio: document.getElementById('ratio-select').value,
        project_id: 'web_' + Date.now(),
      })
    });
    const d = await r.json();
    const jobId = d.job_id;
    _currentJobId = jobId; _currentProjectId = d.project_id || null;
    jobLog.textContent += `Job ID: ${jobId}\\n`;

    _pollTimer = setInterval(async () => {
      try {
        const pr = await fetch(API + `/api/job/${jobId}`);
        const pj = await pr.json();
        jobLog.textContent = `Job: ${jobId}\\nStatus: ${pj.status}\\nStep: ${pj.step}\\n${pj.detail || ''}\\n`;
        updateStepper(pj.step, pj.status);
        if (pj.status !== 'running') {
          clearInterval(_pollTimer);
          setRunState(false);
          document.getElementById('cancel-btn').textContent = '⏹ Cancel';
          if (pj.status === 'completed') {
            jobLog.textContent += '\\n✅ Done! Check the Projects panel.';
            loadProjects();
          } else if (pj.status === 'cancelled') {
            jobLog.textContent += '\\n⏹ Cancelled.';
          } else {
            jobLog.textContent += '\\n❌ Failed. Check the details above.';
          }
        }
      } catch(e) { /* poll error, keep trying */ }
    }, 2000);
  } catch(e) {
    jobLog.textContent += `\\nError: ${e.message}`;
    setRunState(false);
  }
}

// Init
runDoctor();
loadProjects();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _DASHBOARD_HTML
