from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import time
from copy import deepcopy
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import quiz_ai_generator as ai
from app.services.quiz_ai_generator import generate_quiz_json_with_ai
from app.services.quiz_asset_resolver import resolve_quiz_assets
from app.services.quiz_channel_profiles import PROFILES, get_profile
from app.services.quiz_engine_v2 import QuizRenderOptions, QuizVideoEngineV2
from app.services.quiz_episode_structure import apply_round_allocation, build_episode_structure
from app.services.quiz_style_packs import resolve_style_snapshot
from app.services.quiz_voice_registry import PiperVoiceError, resolve_voice_assets, voice_spec_for_locale
from app.providers.image.cliproxy_image import CliproxyImageProvider

ROOT = Path(__file__).resolve().parents[1]
RUN = sorted((ROOT / "output" / "quiz-live-acceptance").glob("*-country-mode"))[-1]
MATRIX_SOURCE = RUN / "matrix-final.json"
OUT_ROOT = RUN / "matrix-cells"
MODEL_ROOT = ROOT / "assets" / "models" / "piper"
PIPER_EXE = Path(r"D:/ALL AI/Hermes-argent-runtime/hermes-agent/venv/Scripts/piper.exe")

# The canary already owns this exact cell and its artifacts must not be regenerated.
CANARY_KEY = ("de-football", "photo_reveal")
MODES = ("multiple_choice", "photo_reveal", "4cards", "visual_riddle", "mixed")
PROFILE_IDS = (
    "de-football",
    "de-wissen",
    "fr-culture",
    "it-calcio",
    "locale-en-US",
    "locale-en-GB",
    "locale-vi-VN",
    "locale-ko-KR",
    "locale-ja-JP",
    "locale-es-ES",
    "locale-es-MX",
)
STYLE_BY_PROFILE = {
    "de-football": "sport-scoreboard",
    "de-wissen": "clear-knowledge",
    "fr-culture": "editorial-culture",
    "it-calcio": "sport-scoreboard",
}

provider_counts = {"llm": 0, "image": 0}
raw_responses: list[str] = []

_original_llm = ai._call_cliproxy_llm


def counted_llm(*args: Any, **kwargs: Any) -> str:
    provider_counts["llm"] += 1
    raw = _original_llm(*args, **kwargs)
    raw_responses.append(raw)
    return raw


ai._call_cliproxy_llm = counted_llm
_original_image = CliproxyImageProvider.generate


async def counted_image(self: CliproxyImageProvider, *args: Any, **kwargs: Any) -> Any:
    provider_counts["image"] += 1
    return await _original_image(self, *args, **kwargs)


CliproxyImageProvider.generate = counted_image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ffprobe(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path.name}: {proc.stderr[-600:]}")
    payload = json.loads(proc.stdout)
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video or not audio:
        raise RuntimeError(f"MP4 must contain video+audio streams: {path}")
    duration = float((payload.get("format") or {}).get("duration") or 0)
    if duration <= 0:
        raise RuntimeError(f"MP4 duration invalid: {path}")
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": str(video.get("r_frame_rate") or ""),
        "duration_seconds": duration,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "audio_sample_rate": audio.get("sample_rate"),
    }


def mode_prompt(profile_id: str, locale: str, mode: str, count: int) -> str:
    profile = get_profile(profile_id)
    pillars = ", ".join(str(x) for x in profile.get("pillars") or [])
    if mode == "multiple_choice":
        schema = "one ordinary multiple-choice question with exactly four choices A/B/C/D and correct_id"
    elif mode == "photo_reveal":
        schema = "one multiple-choice question with exactly four choices A/B/C/D, correct_id, and reveal_image_prompt"
    elif mode == "4cards":
        schema = "one 4cards question with exactly four cards, each card id/label/image_prompt, and correct_option"
    elif mode == "visual_riddle":
        schema = "one visual_riddle with scene_prompt, options 1/2/3/4, correct_option, and an explanation"
    else:
        schema = (
            "exactly two questions in order: q1 must be multiple_choice with four choices A/B/C/D; "
            "q2 must be photo_reveal with four choices A/B/C/D and reveal_image_prompt"
        )
    return (
        f"Create {count} native {locale} quiz question(s) for profile {profile_id} ({profile.get('name')}). "
        f"Topic pillars: {pillars}. Use the audience/persona and form of address from the profile. "
        f"The required schema is: {schema}. "
        "Return only JSON. Question at most 90 characters, each choice/label at most 40 characters, explanation at most 90 characters. Keep question, voice_q, voice_a, answer/explanation and labels in the target locale. "
        "Use fair, non-defamatory wording. For factual claims include source_url or fact_sources with an official or stable URL; "
        "do not invent a source. Include numbers, diacritics and a relevant place/name where natural. "
        "Do not use local file paths. For visual prompts, describe original graphics only; no logos, copyrighted photos, or film stills."
    )


def cell_manifest_path(cell_dir: Path) -> Path:
    return cell_dir / "cell-manifest.json"


def valid_completed_cell(cell_dir: Path) -> bool:
    manifest = cell_manifest_path(cell_dir)
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return False
    if data.get("status") != "TECH_PASS":
        return False
    from app.services.quiz_v2_contract import detect_question_mode
    document_path = cell_dir / "resolved-document.json"
    if not document_path.exists():
        return False
    document = json.loads(document_path.read_text(encoding="utf-8"))
    actual = [detect_question_mode(q) for q in document.get("questions", [])]
    expected = ["multiple_choice", "photo_reveal"] if data.get("mode") == "mixed" else [data.get("mode")]
    if actual != expected:
        return False
    outputs = data.get("render_results") or []
    return len(outputs) == 2 and all(Path(item["path"]).is_file() and sha256(Path(item["path"])) == item.get("sha256") for item in outputs)


def generate_cell_questions(profile_id: str, mode: str, out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profile = get_profile(profile_id)
    locale = str(profile["locale"])
    count = 2 if mode == "mixed" else 1
    structure = build_episode_structure("mixed" if mode == "mixed" else "single", episode_count=count,
                                        format_key="photo_reveal" if mode == "mixed" else mode)
    prompt = mode_prompt(profile_id, locale, mode, count)
    context = {
        "series": profile.get("name"),
        "topic": ", ".join(str(x) for x in profile.get("pillars") or []),
        "difficulty_curve": "mixed",
        "target_minutes": 1,
        "question_index": 1,
        "question_total": count,
        "round_structure": structure,
    }
    ledger_path = out / "attempt-ledger.json"
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    else:
        previous = cell_manifest_path(out)
        old = json.loads(previous.read_text(encoding="utf-8")) if previous.exists() else {}
        ledger = {"used": int(old.get("provider_requests", {}).get("llm", 0))}
    errors: list[str] = []
    for attempt in range(int(ledger["used"]) + 1, 3):
        ledger["used"] = attempt
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        request_prompt = prompt if attempt == 1 else (
            prompt
            + " Previous output failed validation: "
            + (errors[-1] if errors else "prior attempt failed; see cell evidence")
            + ". Repair the JSON and return the exact requested mode/round allocation; this is the only repair request."
        )
        try:
            questions = generate_quiz_json_with_ai(
                request_prompt,
                count=count,
                format_type=mode,
                language=locale,
                channel_profile=profile_id,
                episode_context=context,
            )
            questions = apply_round_allocation(questions, structure)
            (out / "raw-ai-responses").mkdir(parents=True, exist_ok=True)
            for index, raw in enumerate(raw_responses[-attempt:], start=1):
                (out / "raw-ai-responses" / f"response-{index}.txt").write_text(raw, encoding="utf-8")
            return questions, {
                "status": "GENERATED",
                "attempts": attempt,
                "requested_count": count,
                "format": mode,
                "locale": locale,
                "structure": structure,
                "validation_errors": errors,
            }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors) or "REQUEST_BUDGET_EXHAUSTED: retained across restarts")


def render_cell(
    questions: list[dict[str, Any]],
    *,
    profile_id: str,
    mode: str,
    style: dict[str, Any],
    voice: dict[str, Any],
    out: Path,
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    render_results: list[dict[str, Any]] = []
    for aspect in ("16:9", "9:16"):
        name = f"render-{aspect.replace(':', '_')}.mp4"
        target = out / name
        identity = hashlib.sha256(json.dumps({"document": document, "aspect": aspect,
            "model": sha256(Path(voice["model_path"])), "config": sha256(Path(voice["config_path"]))}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        identity_path = out / (name + ".identity.json")
        if target.is_file() and identity_path.exists() and json.loads(identity_path.read_text()).get("identity") == identity and json.loads(identity_path.read_text()).get("sha256") == sha256(target):
            probe = ffprobe(target)
            render_results.append({
                "aspect": aspect,
                "path": str(target.resolve()),
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
                "probe": probe,
                "reused_existing": True,
            })
            continue
        if target.exists():
            target.rename(out / (name + f".unverified-{time.time_ns()}.mp4"))
        options = QuizRenderOptions(
            aspect_ratio=aspect,
            fps=30,
            language=str(document["language"]),
            channel_profile=profile_id,
            visual_style=deepcopy(style),
            output_path=target,
            tts_engine="piper",
            piper_voice=str(voice["voice_id"]),
            piper_model_dir=Path(voice["model_path"]).parent,
            piper_config_path=Path(voice["config_path"]),
            piper_exe=PIPER_EXE,
            piper_speed=float(get_profile(profile_id).get("speed", 1.0)),
            archetype="riddle_mystra" if mode in {"4cards", "visual_riddle"} else "classic",
        )
        engine = QuizVideoEngineV2(options)
        rendered = engine.render_quiz_video(questions, title=document["title"])
        if rendered != target and rendered.is_file():
            rendered.replace(target)
        probe = ffprobe(target)
        expected = (1920, 1080) if aspect == "16:9" else (1080, 1920)
        if (probe["width"], probe["height"]) != expected:
            raise RuntimeError(f"aspect mismatch for {target}: {probe}")
        identity_path.write_text(json.dumps({"identity": identity, "sha256": sha256(target)}), encoding="utf-8")
        render_results.append({
            "aspect": aspect,
            "path": str(target.resolve()),
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
            "probe": probe,
            "tts_calls": getattr(engine, "tts_calls", 0),
            "tts_cache_hits": getattr(engine, "tts_cache_hits", 0),
            "reused_existing": False,
        })
    return render_results


def run_cell(profile_id: str, mode: str) -> dict[str, Any]:
    key = (profile_id, mode)
    profile = get_profile(profile_id)
    locale = str(profile["locale"])
    cell_id = f"{profile_id}__{mode}"
    out = OUT_ROOT / cell_id
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if key == CANARY_KEY:
        canary = RUN / "canary" / "de-football-photo-reveal" / "canary-manifest.json"
        data = json.loads(canary.read_text(encoding="utf-8"))
        return {
            "cell_id": cell_id,
            "profile_id": profile_id,
            "locale": locale,
            "mode": mode,
            "status": "TECH_PASS",
            "reused_canary": True,
            "source_manifest": str(canary.resolve()),
            "render_results": data["render_results"],
            "provider_requests": data["provider_counts"],
            "elapsed_seconds": time.perf_counter() - started,
        }
    if profile_id == "locale-ja-JP":
        return {
            "cell_id": cell_id,
            "profile_id": profile_id,
            "locale": locale,
            "mode": mode,
            "status": "BLOCKED_VOICE",
            "reason": "No ja_JP entry in current Piper voices catalog; no cross-locale fallback",
            "provider_requests": {"llm": 0, "image": 0},
            "elapsed_seconds": time.perf_counter() - started,
        }
    if valid_completed_cell(out):
        return json.loads(cell_manifest_path(out).read_text(encoding="utf-8")) | {"reused_cell": True}
    existing_manifest = cell_manifest_path(out)
    existing_ledger = out / "attempt-ledger.json"
    if existing_manifest.exists() and existing_ledger.exists():
        prior = json.loads(existing_manifest.read_text(encoding="utf-8"))
        ledger = json.loads(existing_ledger.read_text(encoding="utf-8"))
        if prior.get("status") in {"FAILED_CELL", "BLOCKED_CELL"} and int(ledger.get("used", 0)) >= 2:
            blocked = {
                "cell_id": cell_id,
                "profile_id": profile_id,
                "locale": locale,
                "mode": mode,
                "status": "BLOCKED_CELL",
                "blocked_reason": "REQUEST_BUDGET_EXHAUSTED_OR_VALIDATION_BLOCKED",
                "prior_error": prior.get("error") or prior.get("blocked_reason"),
                "attempts_used": int(ledger.get("used", 0)),
                "provider_requests": {"llm": 0, "image": 0},
                "elapsed_seconds": time.perf_counter() - started,
            }
            existing_manifest.write_text(json.dumps(blocked, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return blocked
    before_counts = dict(provider_counts)
    try:
        voice = resolve_voice_assets(MODEL_ROOT, locale=locale, voice_id=None, strict=True)
    except (PiperVoiceError, OSError) as exc:
        return {
            "cell_id": cell_id,
            "profile_id": profile_id,
            "locale": locale,
            "mode": mode,
            "status": "BLOCKED_VOICE",
            "reason": str(exc),
            "provider_requests": {"llm": 0, "image": 0},
            "elapsed_seconds": time.perf_counter() - started,
        }
    style_id = STYLE_BY_PROFILE.get(profile_id, "clear-knowledge")
    style = resolve_style_snapshot(style_id, locale=locale, motion="medium")
    try:
        resolved_path = out / "resolved-document.json"
        validated_path = out / "validated-document.json"
        cached_path = resolved_path if resolved_path.exists() else validated_path
        if cached_path.exists():
            cached = json.loads(cached_path.read_text(encoding="utf-8"))
            if cached.get("channel_profile") != profile_id:
                raise ValueError("cached document profile mismatch")
            expected_modes = ["multiple_choice", "photo_reveal"] if mode == "mixed" else [mode]
            from app.services.quiz_v2_contract import detect_question_mode
            cached_modes = [detect_question_mode(q) for q in cached.get("questions", [])]
            if cached_modes != expected_modes:
                # Preserve the stale evidence, but use the one remaining bounded
                # repair request instead of treating a mismatched cache as a valid cell.
                questions, generation = generate_cell_questions(profile_id, mode, out)
            else:
                questions = cached["questions"]
                structure = build_episode_structure("mixed" if mode == "mixed" else "single", episode_count=len(questions), format_key="photo_reveal" if mode == "mixed" else mode)
                questions = apply_round_allocation(questions, structure)
                generation = {"structure": structure, "reused_document": str(cached_path)}
        else:
            questions, generation = generate_cell_questions(profile_id, mode, out)
        document = {
            "schema_version": "quiz_v2_dynamic",
            "engine_v2": True,
            "title": f"{profile['name']} · {mode}",
            "language": locale,
            "channel_profile": profile_id,
            "visual_style": style,
            "round_structure": generation["structure"],
            "questions": questions,
            "settings": {"piper_voice": voice["voice_id"], "piper_locale": locale, "piper_speed": profile.get("speed", 1.0)},
            "approval": {"status": "draft"},
        }
        if not validated_path.exists():
            validated_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        resolved = questions if resolved_path.exists() else asyncio.run(resolve_quiz_assets(questions, out / "assets", image_model="gpt-image-2", allow_generation=True))
        document["questions"] = resolved
        (out / "resolved-document.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        render_results = render_cell(resolved, profile_id=profile_id, mode=mode, style=style, voice=voice, out=out, document=document)
        result = {
            "cell_id": cell_id,
            "profile_id": profile_id,
            "locale": locale,
            "mode": mode,
            "status": "TECH_PASS",
            "style_id": style_id,
            "voice_id": voice["voice_id"],
            "voice_model": str(voice["model_path"]),
            "voice_config": str(voice["config_path"]),
            "question_count": len(resolved),
            "generation": generation,
            "render_results": render_results,
            "provider_requests": {"llm": provider_counts["llm"] - before_counts["llm"], "image": provider_counts["image"] - before_counts["image"]},
            "elapsed_seconds": time.perf_counter() - started,
            "document": str((out / "resolved-document.json").resolve()),
        }
    except Exception as exc:  # noqa: BLE001
        result = {
            "cell_id": cell_id,
            "profile_id": profile_id,
            "locale": locale,
            "mode": mode,
            "status": "FAILED_CELL",
            "error": f"{type(exc).__name__}: {exc}",
            "provider_requests": {"llm": provider_counts["llm"] - before_counts["llm"], "image": provider_counts["image"] - before_counts["image"]},
            "elapsed_seconds": time.perf_counter() - started,
        }
    cell_manifest_path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for profile_id in PROFILE_IDS:
        for mode in MODES:
            result = run_cell(profile_id, mode)
            results.append(result)
            print(json.dumps({k: result.get(k) for k in ("cell_id", "status", "provider_requests", "error")}, ensure_ascii=False), flush=True)
    summary = {
        "run": str(RUN.resolve()),
        "results": results,
        "provider_totals_this_process": dict(provider_counts),
        "provider_calls_canary": 2,
        "completed": sum(r.get("status") == "TECH_PASS" for r in results),
        "blocked_voice": sum(r.get("status") == "BLOCKED_VOICE" for r in results),
        "failed_cells": sum(r.get("status") == "FAILED_CELL" for r in results),
        "blocked_cells": sum(r.get("status") == "BLOCKED_CELL" for r in results),
        "reused_canary": sum(bool(r.get("reused_canary")) for r in results),
        "build_started": False,
        "commit_created": False,
    }
    (RUN / "matrix-run-final.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("provider_totals_this_process", "completed", "blocked_voice", "failed_cells", "reused_canary")}, ensure_ascii=False))
    return 0 if summary["failed_cells"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

