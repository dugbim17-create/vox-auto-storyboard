"""Local scene renderer (P6-T05).

Renders a silent scene MP4 from a validated ``MotionPlan`` + its layer assets,
using the FFmpeg motion compiler (P6-T04). Per scene:

1. assemble ``assets`` (asset_role -> layer PNG path) from the project store;
2. compile the plan to an FFmpeg argument list;
3. run FFmpeg to produce ``scenes/{scene_id}.mp4``;
4. probe the output and verify FPS / resolution / duration / pix_fmt.

Acceptance criteria (MASTER_PLAN P6-T05):

- correct FPS;
- correct resolution;
- correct duration (within ±1 frame);
- yuv420p;
- 12-template render smoke test.

The compiler and probe are injectable so unit tests never need a real FFmpeg
binary (an integration test uses the real one when available).
"""

from __future__ import annotations

import logging
import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.ffmpeg_compiler import CompiledMotion, MotionCompiler

logger = logging.getLogger(__name__)


class SceneRenderError(Exception):
    """Raised when a scene cannot be rendered or fails verification."""


@dataclass
class RenderProbe:
    """Facts verified about a rendered MP4."""

    fps: float
    width: int
    height: int
    duration_ms: int
    pix_fmt: str

    def verify(self, *, expected_fps: int, expected_w: int, expected_h: int,
               expected_duration_ms: int, tolerance_frames: int = 1) -> None:
        """Assert the probe matches expectations; raise ``SceneRenderError``."""
        if abs(self.fps - expected_fps) > 0.01:
            raise SceneRenderError(
                f"fps {self.fps:.2f} != expected {expected_fps}"
            )
        if self.width != expected_w or self.height != expected_h:
            raise SceneRenderError(
                f"resolution {self.width}x{self.height} != expected {expected_w}x{expected_h}"
            )
        tolerance_ms = math.ceil(1000.0 / expected_fps * tolerance_frames) + 2
        if abs(self.duration_ms - expected_duration_ms) > tolerance_ms:
            raise SceneRenderError(
                f"duration {self.duration_ms}ms != expected {expected_duration_ms}ms "
                f"(±{tolerance_ms}ms)"
            )
        if self.pix_fmt != "yuv420p":
            raise SceneRenderError(f"pix_fmt {self.pix_fmt!r} != 'yuv420p'")


class LocalSceneRenderer:
    """Render silent scene MP4s via MotionCompiler + ffprobe verification."""

    renderer_name = "ffmpeg"
    renderer_version = "system"

    def __init__(
        self,
        *,
        compiler: MotionCompiler | None = None,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        project_root: str | Path | None = None,
        runner: Callable[..., Any] | None = None,
        text_layout: Any | None = None,
    ) -> None:
        self.compiler = compiler or MotionCompiler(ffmpeg_bin=ffmpeg_bin, text_layout=text_layout)
        self.ffprobe_bin = ffprobe_bin
        self.project_root = project_root
        self._runner = runner

    # ------------------------------------------------------------------ #
    # Entrypoint
    # ------------------------------------------------------------------ #
    def render_scene(
        self,
        project_id: str,
        scene_id: str,
        plan: dict,
        *,
        assets: dict[str, str] | None = None,
        project_root: str | Path | None = None,
    ) -> tuple[Path, RenderProbe]:
        """Render one silent scene to ``scenes/{scene_id}.mp4`` and verify it.

        ``assets`` maps asset_role -> layer path. When omitted, layers are
        read from ``layers/{scene_id}_{role}.png`` under the project root.
        """
        from app.storage.asset_store import AssetStore

        root = project_root or self.project_root
        store = AssetStore(root)
        scenes_dir = store.subdir(project_id, "scenes")
        out_path = scenes_dir / f"{scene_id}.mp4"

        asset_map = assets or self._default_assets(project_id, scene_id, plan, store)
        from app.services.ken_burns_validator import validate_or_raise

        try:
            validate_or_raise(plan)
        except Exception as exc:  # noqa: BLE001
            raise SceneRenderError(str(exc)) from exc
        compiled = self.compiler.compile(
            plan, assets=asset_map, output_path=str(out_path)
        )
        self._run_ffmpeg(compiled)
        probe = self._probe(out_path, plan)
        return out_path, probe

    # ------------------------------------------------------------------ #
    # Asset + execution helpers
    # ------------------------------------------------------------------ #
    def _default_assets(
        self, project_id: str, scene_id: str, plan: dict, store: Any
    ) -> dict[str, str]:
        """Map asset_role -> ``layers/{scene_id}_{role}.png`` when no overrides."""
        asset_map: dict[str, str] = {}
        layers_dir = store.subdir(project_id, "layers")
        for layer in plan.get("layers", []):
            role = layer.get("asset_role", "") or layer.get("id", "")
            candidate = layers_dir / f"{scene_id}_{role}.png"
            if candidate.is_file():
                asset_map[role] = str(candidate)
            else:
                logger.warning("scene %s: layer role %r missing asset %s", scene_id, role, candidate)
        return asset_map

    def _run_ffmpeg(self, compiled: CompiledMotion) -> None:
        runner = self._runner or subprocess.run
        proc = runner(compiled.command, capture_output=True, text=True)
        if getattr(proc, "returncode", 0) != 0:
            raise SceneRenderError(
                f"ffmpeg failed for {compiled.scene_id}: {getattr(proc, 'stderr', '')}"
            )

    def _probe(self, path: Path, plan: dict) -> RenderProbe:
        """Probe the output MP4 and verify against the plan's expectations."""
        try:
            probe_data = self._run_probe(path)
        except (OSError, subprocess.SubprocessError) as exc:
            raise SceneRenderError(f"ffprobe failed for {path}: {exc}") from exc

        probe = RenderProbe(**probe_data)
        canvas = plan.get("canvas", {})
        probe.verify(
            expected_fps=plan.get("fps", 30),
            expected_w=canvas.get("width", 1920),
            expected_h=canvas.get("height", 1080),
            expected_duration_ms=plan.get("duration_ms", 0),
        )
        return probe

    def _run_probe(self, path: Path) -> dict:
        """Run ffprobe and return fps/width/height/duration_ms/pix_fmt."""
        proc = subprocess.run(
            [
                self.ffprobe_bin, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate,width,height,pix_fmt",
                "-show_entries", "format=duration",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise SceneRenderError(f"ffprobe rc={proc.returncode}: {proc.stderr}")
        import json

        data = json.loads(proc.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format", {})
        fps = _parse_fps(stream.get("r_frame_rate", ""))
        duration_ms = int(float(fmt.get("duration", 0)) * 1000)
        return {
            "fps": fps,
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "duration_ms": duration_ms,
            "pix_fmt": stream.get("pix_fmt", ""),
        }


def _parse_fps(r_frame_rate: str) -> float:
    """Parse '30000/1001' or '30/1' into a float fps."""
    if "/" in r_frame_rate:
        num, den = r_frame_rate.split("/")
        try:
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(r_frame_rate)
    except ValueError:
        return 0.0
