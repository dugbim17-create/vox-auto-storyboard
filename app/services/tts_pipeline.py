"""TTS scene pipeline (P3-T05).

Generates a Vietnamese WAV per scene through the OmniVoice worker adapter,
normalizes loudness with ffmpeg, and persists the result to the Scene row.

Flow per scene:

1. normalize narration (P3-T04) for TTS;
2. compute cache key = sha256(normalized narration);
3. if ``audio/{scene_id}_{key8}.wav`` exists -> reuse (rerun dùng cache);
4. else synthesize via the OmniVoice adapter, normalize loudness, persist;
5. update ``Scene.actual_voice_duration_ms`` + record WAV path.

Re-planning a scene with changed narration produces a different cache key, so
only that scene is regenerated (thay narration chỉ regenerate scene đó).
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from app.providers.base import TTSRequest, TTSWordTiming
from app.schemas.editorial_timeline import VoiceTimeline, WordTiming
from app.services.scene_audio_mux import SceneAudioMuxer
from app.services.vi_normalize import normalize_vi
from app.storage.asset_store import AssetStore
from app.storage.repositories import SceneRepo

logger = logging.getLogger(__name__)


@dataclass
class SceneTTSResult:
    scene_id: str
    wav_path: str
    duration_ms: int
    cached: bool
    normalized: bool = False
    error: str = ""
    word_timings: tuple[TTSWordTiming, ...] = ()

    def voice_timeline(self, *, fps: int) -> VoiceTimeline:
        """Return the canonical measured timeline; never invent word boundaries."""
        return VoiceTimeline.build(
            scene_id=self.scene_id,
            duration_ms=self.duration_ms,
            fps=fps,
            words=tuple(
                WordTiming(text=item.text, start_ms=item.start_ms, end_ms=item.end_ms)
                for item in self.word_timings
            ),
        )


@dataclass
class TTSPipelineResult:
    project_id: str
    total_scenes: int
    generated: int = 0
    cached: int = 0
    errors: list[str] = field(default_factory=list)
    scene_results: list[SceneTTSResult] = field(default_factory=list)
    elapsed_ms: int = 0

    @property
    def audio_paths(self) -> list[str]:
        """Successful WAV paths in storyboard/scene order."""
        return [item.wav_path for item in self.scene_results if item.wav_path]


class TTSPipelineError(Exception):
    """Raised when TTS generation fails for a scene."""


class TTSScenePipeline:
    """Per-scene TTS generation with caching + loudness normalization."""

    def __init__(
        self,
        tts_provider: Any,
        *,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        loudness_target: float = -16.0,
        voice_profile_id: str = "voice_vi_01",
        reference_audio_path: str = "",
        reference_audio_hash: str = "",
        language: str = "vi",
        seed: int = 42,
        speed: float = 1.0,
        provider_params: dict[str, Any] | None = None,
        word_aligner: Any | None = None,
    ) -> None:
        self.tts = tts_provider
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.loudness_target = loudness_target
        self.voice_profile_id = voice_profile_id
        self.reference_audio_path = reference_audio_path
        self.reference_audio_hash = reference_audio_hash or _hash_optional_file(reference_audio_path)
        self.language = language
        self.seed = seed
        self.speed = speed
        self.provider_params = dict(provider_params or {})
        self.word_aligner = word_aligner

    # ------------------------------------------------------------------ #
    # Entrypoints
    # ------------------------------------------------------------------ #
    async def run(self, project_id: str, session: Any, *, project_root: str | Path | None = None) -> TTSPipelineResult:
        """Generate TTS for all scenes that don't have a cached WAV."""
        start = time.monotonic()
        store = AssetStore(project_root)
        scenes = SceneRepo.list(session, project_id)
        result = TTSPipelineResult(project_id=project_id, total_scenes=len(scenes))

        for scene in scenes:
            try:
                scene_result = await self.generate_scene(
                    project_id, scene.scene_id, session, store=store
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{scene.scene_id}: {exc}")
                continue
            if scene_result.cached:
                result.cached += 1
            else:
                result.generated += 1
            result.scene_results.append(scene_result)

        result.elapsed_ms = int((time.monotonic() - start) * 1000)
        return result

    async def generate_scene(
        self,
        project_id: str,
        scene_id: str,
        session: Any,
        *,
        store: AssetStore | None = None,
    ) -> SceneTTSResult:
        """Generate (or fetch cached) TTS for one scene."""
        store = store or AssetStore()
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None:
            raise TTSPipelineError(f"scene not found: {project_id}/{scene_id}")

        normalized = normalize_vi(scene.narration_text or "")
        if not normalized.strip():
            raise TTSPipelineError(f"scene {scene_id} has empty narration")

        cache_key = sha256_tts_request(
            text_normalized=normalized,
            voice_profile_id=self.voice_profile_id,
            language=self.language,
            reference_audio_hash=self.reference_audio_hash,
            seed=self.seed,
            speed=self.speed,
            provider_params=self.provider_params,
        )[:12]
        audio_dir = store.subdir(project_id, "audio")
        wav_path = audio_dir / f"{scene_id}_{cache_key}.wav"

        # Cache hit
        if wav_path.is_file() and wav_path.stat().st_size > 44:
            duration = probe_wav(wav_path, self.ffprobe_bin)
            if duration > 0:
                word_timings = _read_word_timings(wav_path, scene_id, duration)
                if not word_timings and self.word_aligner is not None:
                    word_timings = tuple(
                        self.word_aligner.align(wav_path, normalized, duration)
                    )
                    _write_word_timings(wav_path, scene_id, duration, word_timings)
                self._update_scene(session, scene, wav_path, duration)
                return SceneTTSResult(
                    scene_id=scene_id,
                    wav_path=str(wav_path),
                    duration_ms=duration,
                    cached=True,
                    word_timings=word_timings,
                )

        # Generate
        request = TTSRequest(
            segment_id=scene_id,
            text=normalized,
            language=self.language,
            voice_profile_id=self.voice_profile_id,
            reference_audio_path=self.reference_audio_path,
            seed=self.seed,
            speed=self.speed,
            provider_params=self.provider_params,
            output_path=str(wav_path),
        )
        tts_result = await self.tts.synthesize(request)
        duration = tts_result.duration_ms or probe_wav(Path(tts_result.wav_path), self.ffprobe_bin)

        # Loudness normalization (optional if ffmpeg unavailable)
        normalized = False
        try:
            normalized = loudness_normalize(
                Path(tts_result.wav_path), self.ffmpeg_bin, target=self.loudness_target
            )
            if normalized:
                duration = probe_wav(Path(tts_result.wav_path), self.ffprobe_bin)
        except TTSPipelineError:
            logger.warning("loudness normalize skipped for %s", scene_id)

        self._update_scene(session, scene, Path(tts_result.wav_path), duration)
        word_timings = tuple(tts_result.word_timings)
        if not word_timings and self.word_aligner is not None:
            word_timings = tuple(
                self.word_aligner.align(Path(tts_result.wav_path), request.text, duration)
            )
        if word_timings:
            _write_word_timings(Path(tts_result.wav_path), scene_id, duration, word_timings)
        return SceneTTSResult(
            scene_id=scene_id,
            wav_path=str(tts_result.wav_path),
            duration_ms=duration,
            cached=False,
            normalized=normalized,
            word_timings=word_timings,
        )

    def _update_scene(
        self, session: Any, scene: Any, wav_path: Path, duration_ms: int
    ) -> None:
        scene.actual_voice_duration_ms = float(duration_ms)
        scene.updated_at = _now()
        session.commit()

    def materialize_audio(
        self,
        result: TTSPipelineResult,
        output_path: str | Path,
        *,
        runner: Any | None = None,
    ) -> Path:
        """Concatenate every successful scene WAV into one ordered narration track."""
        if result.errors:
            raise TTSPipelineError(
                f"cannot materialize incomplete narration: {len(result.errors)} scene error(s)"
            )
        if len(result.audio_paths) != result.total_scenes:
            raise TTSPipelineError(
                f"audio cardinality mismatch: {len(result.audio_paths)} paths for "
                f"{result.total_scenes} scenes"
            )
        muxer = SceneAudioMuxer(
            ffmpeg_bin=self.ffmpeg_bin,
            ffprobe_bin=self.ffprobe_bin,
            runner=runner,
        )
        return muxer.concat_audio(result.audio_paths, output_path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_tts_request(
    *,
    text_normalized: str,
    voice_profile_id: str,
    language: str,
    reference_audio_hash: str,
    seed: int,
    speed: float,
    provider_params: dict[str, Any],
) -> str:
    """Hash all inputs that can change the generated voice artifact."""
    payload = {
        "text_normalized": text_normalized,
        "voice_profile_id": voice_profile_id,
        "language": language,
        "reference_audio_hash": reference_audio_hash,
        "seed": seed,
        "speed": speed,
        "provider_params": provider_params,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(encoded)


def _hash_optional_file(path: str) -> str:
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        return ""
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _word_timings_path(wav_path: Path) -> Path:
    return wav_path.with_suffix(".words.json")


def _validate_word_timings(
    scene_id: str,
    duration_ms: int,
    timings: tuple[TTSWordTiming, ...],
) -> None:
    VoiceTimeline.build(
        scene_id=scene_id,
        duration_ms=duration_ms,
        fps=1000,
        words=tuple(
            WordTiming(text=item.text, start_ms=item.start_ms, end_ms=item.end_ms)
            for item in timings
        ),
    )


def _write_word_timings(
    wav_path: Path,
    scene_id: str,
    duration_ms: int,
    timings: tuple[TTSWordTiming, ...],
) -> None:
    _validate_word_timings(scene_id, duration_ms, timings)
    path = _word_timings_path(wav_path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            [
                {"text": item.text, "start_ms": item.start_ms, "end_ms": item.end_ms}
                for item in timings
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)


def _read_word_timings(
    wav_path: Path,
    scene_id: str,
    duration_ms: int,
) -> tuple[TTSWordTiming, ...]:
    path = _word_timings_path(wav_path)
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        timings = tuple(
            TTSWordTiming(
                text=str(item["text"]),
                start_ms=int(item["start_ms"]),
                end_ms=int(item["end_ms"]),
            )
            for item in payload
        )
        _validate_word_timings(scene_id, duration_ms, timings)
        return timings
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise TTSPipelineError(f"invalid word timing cache for {scene_id}: {exc}") from exc


def probe_wav(path: Path, ffprobe_bin: str) -> int:
    """Return WAV duration in ms via ffprobe. 0 on failure."""
    if not path.is_file():
        return 0
    try:
        proc = subprocess.run(
            [ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return 0
        return int(float(proc.stdout.strip()) * 1000)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def loudness_normalize(path: Path, ffmpeg_bin: str, *, target: float = -16.0) -> bool:
    """Apply single-pass loudnorm via ffmpeg. Rewrites the file in place."""
    tmp = path.with_suffix(".loud.wav")
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-y", "-i", str(path),
             "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11", "-ar", "24000", str(tmp)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not tmp.is_file():
            return False
        tmp.replace(path)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _now():
    from datetime import datetime

    return datetime.now(UTC)
