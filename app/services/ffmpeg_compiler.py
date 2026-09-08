"""FFmpeg motion compiler (P6-T04).

Compiles a validated ``MotionPlan`` (P6-T01) into:

1. an FFmpeg filter graph (scale/translate/rotate/opacity/reveal/overlay/
   grain/shadow/text/transition);
2. a full FFmpeg command as an **argument list** (never a shell string).

Acceptance criteria (MASTER_PLAN P6-T04):

- command uses an argument list (``subprocess.run(cmd)`` with no ``shell=True``);
- no ``shell=True`` anywhere in the module;
- correct Windows path escaping (paths may contain spaces/backslashes);
- filter graph test (each channel produces a compileable filter).

The runner is injectable so tests never invoke a real FFmpeg binary.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MotionCompilerError(Exception):
    """Raised when a MotionPlan cannot be compiled to a filter graph."""


@dataclass
class CompiledMotion:
    """A compiled FFmpeg command for one scene."""

    scene_id: str
    command: list[str]
    filter_graph: str
    fps: int
    width: int
    height: int
    duration_ms: int
    frame_count: int


@dataclass
class CompileOptions:
    """Encoding options for the compiled command."""

    fps: int = 30
    width: int = 1920
    height: int = 1080
    crf: int = 18
    preset: str = "medium"


class MotionCompiler:
    """Compile MotionPlan dicts into FFmpeg argument lists."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        runner: Callable[..., Any] | None = None,
        text_layout: Any | None = None,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self._runner = runner
        self.text_layout = text_layout

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def compile(
        self,
        plan: dict,
        *,
        assets: dict[str, str] | None = None,
        options: CompileOptions | None = None,
        output_path: str | Path = "",
    ) -> CompiledMotion:
        """Compile a MotionPlan dict into an FFmpeg command list.

        ``assets`` maps ``asset_role`` -> layer file path. Every layer in the
        plan must have a matching asset; a missing one raises
        ``MotionCompilerError`` (the planner prunes unavailable roles, so a
        plan reaching the compiler is expected to be fully supplied).
        """
        plan = self._validate_plan(plan)
        opts = options or CompileOptions(
            fps=plan["fps"],
            width=plan["canvas"]["width"],
            height=plan["canvas"]["height"],
        )
        assets = assets or {}

        graph, frames = self.build_filter_graph(plan, assets=assets, options=opts)
        out = str(output_path or f"scene_{plan['scene_id']}.mp4")
        cmd = self._build_command(graph, plan, assets, out, opts)
        return CompiledMotion(
            scene_id=plan["scene_id"],
            command=cmd,
            filter_graph=graph,
            fps=opts.fps,
            width=opts.width,
            height=opts.height,
            duration_ms=plan["duration_ms"],
            frame_count=frames,
        )

    def run(self, compiled: CompiledMotion, *, check: bool = True) -> int:
        """Run the compiled command via the injectable runner (subprocess.run)."""
        import subprocess

        runner = self._runner or subprocess.run
        proc = runner(compiled.command, capture_output=True, text=True)
        if check and getattr(proc, "returncode", 0) != 0:
            raise MotionCompilerError(
                f"ffmpeg failed for {compiled.scene_id}: {getattr(proc, 'stderr', '')}"
            )
        return getattr(proc, "returncode", 0)

    # ------------------------------------------------------------------ #
    # Filter graph
    # ------------------------------------------------------------------ #
    def build_filter_graph(
        self,
        plan: dict,
        *,
        assets: dict[str, str] | None = None,
        options: CompileOptions | None = None,
    ) -> tuple[str, int]:
        """Return (filter_graph, frame_count) for a validated plan.

        Layers are sorted by z-order; each layer is chained
        (scale -> rotate -> translate -> opacity) and overlaid in order onto
        the base. Text animations are appended as ``drawtext``.
        """
        plan = self._validate_plan(plan)
        opts = options or CompileOptions(
            fps=plan["fps"],
            width=plan["canvas"]["width"],
            height=plan["canvas"]["height"],
        )
        assets = assets or {}
        duration_ms = plan["duration_ms"]
        frame_count = int(round(duration_ms / 1000.0 * opts.fps))

        layers = sorted(plan.get("layers", []), key=lambda layer: layer.get("z", 0))
        if not layers:
            raise MotionCompilerError("plan has no layers")

        # Resolve asset paths (one input per layer).
        paths: list[str] = []
        for i, layer in enumerate(layers):
            role = layer.get("asset_role", "") or layer.get("id", "")
            path = assets.get(role)
            if not path:
                raise MotionCompilerError(
                    f"layer {i} role {role!r} has no asset; supply 'assets[{role}]'"
                )
            paths.append(_arg_path(path))

        parts: list[str] = []
        # Base = the bottom layer (z=0), scaled to the canvas. It is produced
        # by its own chain so its transform (scale/translate) still applies.
        parts.append(self._compose_base(layers[0], opts, duration_ms))  # [0:v]... -> [base]
        cur = "base"

        # Overlay the remaining layers (z>0) in order; each is transformed by
        # its own chain first ([i:v]... -> [l{i}]).
        for i in range(1, len(layers)):
            parts.append(self._layer_chain(layers[i], i, duration_ms, opts.fps))
            x_expr = _track_expression(layers[i].get("transform", {}), "x", duration_ms, 0.0)
            y_expr = _track_expression(layers[i].get("transform", {}), "y", duration_ms, 0.0)
            parts.append(
                f"[{cur}][l{i}]overlay=x=(W-w)/2+({x_expr}):y=(H-h)/2+({y_expr}):eof_action=repeat[{cur}_o]"
            )
            cur = f"{cur}_o"

        # Camera transforms the assembled visual world. Typography is applied
        # afterwards so editorial headlines remain screen-space elements.
        camera = plan.get("camera") or {}
        if camera:
            parts.extend(self._camera_chain(cur, camera, opts, duration_ms))
            cur = f"{cur}_cam"

        for index, effect in enumerate(plan.get("effects", [])):
            effect_filter = _effect_filter(effect, opts)
            if effect_filter:
                output = f"{cur}_fx{index}"
                parts.append(f"[{cur}]{effect_filter}[{output}]")
                cur = output

        # Text animations -> chain drawtext filters onto the current stream so
        # the text actually lands in the output (no orphaned filters).
        for ta in plan.get("text_animations", []):
            parts.append(f"[{cur}]{self._drawtext(ta, opts, duration_ms)}[{cur}_t]")
            cur = f"{cur}_t"

        motion_fps = int(plan.get("motion_fps", opts.fps))
        if motion_fps < opts.fps:
            output = f"{cur}_cadence"
            parts.append(
                f"[{cur}]fps=fps={motion_fps},fps=fps={opts.fps}[{output}]"
            )
            cur = output

        # Always end with a stream labeled [final] so -map "[final]" resolves.
        # Transitions are chained in front of the null terminator.
        transition = plan.get("transition_out", "none")
        parts.append(_terminate(cur, transition))
        graph = ";\n".join(parts)
        return graph, frame_count

    def _compose_base(self, layer: dict, opts: CompileOptions, duration_ms: int) -> str:
        """Compose the bottom layer (z=0) into a full-canvas ``[base]`` stream."""
        transform = layer.get("transform", {})
        scale = _track_expression(transform, "scale", duration_ms, 1.0)
        filters = [
            f"scale={opts.width}:{opts.height}:force_original_aspect_ratio=increase",
            f"crop={opts.width}:{opts.height}",
            f"scale=w=iw*({scale}):h=ih*({scale}):eval=frame",
            f"crop={opts.width}:{opts.height}:x=(iw-{opts.width})/2:y=(ih-{opts.height})/2",
        ]
        return f"[0:v]{','.join(filters)}[base]"

    def _layer_chain(self, layer: dict, idx: int, duration_ms: int, fps: int) -> str:
        """Build the filter chain for one layer, producing ``[l{idx}]``."""
        transform = layer.get("transform", {})
        filters: list[str] = []
        scale = _track_expression(transform, "scale", duration_ms, 1.0)
        filters.append(f"scale=w=iw*({scale}):h=ih*({scale}):eval=frame")
        rot = _track_expression(transform, "rotation_deg", duration_ms, 0.0)
        filters.append(f"rotate=({rot})*PI/180:ow=rotw(iw):oh=roth(ih):c=black@0")
        filters.append("format=rgba")
        filters.extend(_opacity_filters(transform, fps))
        if not filters:
            filters.append("null")
        return f"[{idx}:v]{','.join(filters)}[l{idx}]"

    def _camera_chain(
        self,
        current: str,
        camera: dict,
        opts: CompileOptions,
        duration_ms: int,
    ) -> list[str]:
        scale = _track_expression(camera, "scale", duration_ms, 1.0)
        x = _track_expression(camera, "x", duration_ms, 0.0)
        y = _track_expression(camera, "y", duration_ms, 0.0)
        scaled = f"{current}_cam_scaled"
        output = f"{current}_cam"
        x_crop = (
            f"max(0\\,min(iw-{opts.width}\\,(iw-{opts.width})/2-({x})))"
        )
        y_crop = (
            f"max(0\\,min(ih-{opts.height}\\,(ih-{opts.height})/2-({y})))"
        )
        return [
            f"[{current}]scale=w=ceil(iw*({scale})/2)*2:"
            f"h=ceil(ih*({scale})/2)*2:eval=frame[{scaled}]",
            f"[{scaled}]crop={opts.width}:{opts.height}:x={x_crop}:y={y_crop}[{output}]",
        ]

    def _drawtext(self, ta: dict, opts: CompileOptions, duration_ms: int) -> str:
        text = str(ta.get("text", "")).replace("'", "\\\\'").replace(":", "\\\\:")
        layout = None
        if self.text_layout is not None and text:
            layout = self.text_layout.layout(
                text,
                canvas_size=(opts.width, opts.height),
                placement=str(ta.get("placement", "top_left")),
                font_size=int(ta.get("font_size", 64)),
            )
            if layout.overflow:
                raise MotionCompilerError(f"text layout overflow for {text!r}")
        # fontfile value is single-quoted and the drive colon is backslash-
        # escaped so ffmpeg's option parser does not split at ':'.
        font_path = getattr(layout, "font_path", r"C:\Windows\Fonts\arial.ttf")
        font = "'" + font_path.replace("\\", "/").replace(":", r"\:") + "'"
        fontsize = int(getattr(layout, "font_size", ta.get("font_size", 64)))
        x = int(getattr(layout, "x", 0)) if layout is not None else ta.get("x", "(w-text_w)/2")
        y = int(getattr(layout, "y", 0)) if layout is not None else ta.get("y", "(h-text_h)/2")
        start_ms, end_ms = _text_window(ta, duration_ms)
        enable = (
            f":enable='between(t\\,{start_ms / 1000.0:.3f}\\,{end_ms / 1000.0:.3f})'"
        )
        # Only the drawtext filter fragment; build_filter_graph appends it to
        # the graph (the final label is derived there).
        return (
            f"drawtext=fontfile={font}:text='{text}':expansion=none:"
            f"fontcolor={ta.get('fontcolor', 'white')}:fontsize={fontsize}:x={x}:y={y}"
            f"{enable}"
        )

    def _validate_plan(self, plan: Any) -> dict:
        from app.schemas.motion_plan import MotionPlanError, build_motion_plan

        if not isinstance(plan, dict):
            raise MotionCompilerError("plan must be an object")
        try:
            validated = build_motion_plan(plan)
        except MotionPlanError as exc:
            raise MotionCompilerError(f"invalid plan: {exc}") from exc
        return validated.to_dict()

    def _build_command(
        self,
        graph: str,
        plan: dict,
        assets: dict[str, str],
        output_path: str,
        opts: CompileOptions,
    ) -> list[str]:
        """Build the FFmpeg argument list (never a shell string).

        Each layer image is read as a looping still (``-loop 1 -framerate``)
        so the assembled frames span the full scene duration instead of a
        single 1-frame still per input.
        """
        layers = sorted(plan.get("layers", []), key=lambda layer: layer.get("z", 0))
        cmd = [self.ffmpeg_bin, "-y"]
        for layer in layers:
            role = layer.get("asset_role", "") or layer.get("id", "")
            cmd += ["-loop", "1", "-framerate", str(opts.fps), "-i", _arg_path(assets.get(role, ""))]
        cmd += [
            "-filter_complex", graph,
            "-map", "[final]",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(opts.crf),
            "-preset", opts.preset,
            "-r", str(opts.fps),
            "-t", f"{plan['duration_ms'] / 1000.0:.3f}",
            _arg_path(output_path),
        ]
        return cmd


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _track_value(
    transform: dict, channel: str, t_ms: int, default: float
) -> float:
    """Linear-interpolate a channel's keyframes at time ``t_ms`` (ms).

    Keyframes are ``[[t, v], ...]`` with ``t`` in ms. A single keyframe (or a
    constant track) returns its value; a missing channel returns ``default``.
    """
    track = transform.get(channel)
    if track is None:
        return default
    keys = track if isinstance(track, list) else track.get("keyframes", [])
    if not keys:
        return default
    if len(keys) == 1:
        return keys[0][1]
    # Clamp to the track's own window.
    t0, v0 = keys[0]
    t1, v1 = keys[-1]
    if t_ms <= t0:
        return v0
    if t_ms >= t1:
        return v1
    for (ka, va), (kb, vb) in zip(keys, keys[1:], strict=False):
        if ka <= t_ms <= kb:
            frac = (t_ms - ka) / max(kb - ka, 1e-6)
            return va + frac * (vb - va)
    return v1


def _track_expression(transform: dict, channel: str, duration_ms: int, default: float) -> str:
    """Compile keyframes into an FFmpeg expression evaluated in seconds."""
    track = transform.get(channel)
    keys = track if isinstance(track, list) else (track or {}).get("keyframes", [])
    if not keys:
        return f"{default:.6f}"
    if len(keys) == 1:
        return f"{float(keys[0][1]):.6f}"
    segments: list[tuple[float, float, float, float, float]] = []
    for (t0, v0), (t1, v1) in zip(keys, keys[1:], strict=False):
        start = float(t0) / 1000.0
        end = float(t1) / 1000.0
        slope = (float(v1) - float(v0)) / max(end - start, 1e-9)
        segments.append((start, end, float(v0), float(v1), slope))

    expression = f"{segments[-1][3]:.6f}"
    for start, end, v0, _v1, slope in reversed(segments):
        segment_value = f"{v0:.6f}+({slope:.6f})*(t-{start:.6f})"
        expression = f"if(lt(t,{end:.6f}),{segment_value},{expression})"
    first_t, first_v = keys[0]
    expression = f"if(lt(t,{float(first_t) / 1000.0:.6f}),{float(first_v):.6f},{expression})"
    # Commas separate filter options. Escape expression commas so FFmpeg keeps
    # nested if() arguments inside the current option value.
    return expression.replace(",", r"\,")


def _opacity_filters(transform: dict, fps: int) -> list[str]:
    """Compile opacity keyframes into real alpha-changing FFmpeg filters.

    Binary 0↔1 transitions use FFmpeg's optimized alpha-aware ``fade``. Tracks
    with intermediate values use ``geq`` evaluated by frame number so the
    output follows every keyframe instead of freezing at frame zero.
    """
    track = transform.get("opacity")
    keys = track if isinstance(track, list) else (track or {}).get("keyframes", [])
    if not keys:
        return []
    if len(keys) == 1:
        value = float(keys[0][1])
        return [] if value >= 1.0 else [f"colorchannelmixer=aa={value:.6f}"]

    values = {float(value) for _time, value in keys}
    if values.issubset({0.0, 1.0}):
        filters: list[str] = []
        for (start_ms, start_value), (end_ms, end_value) in zip(keys, keys[1:], strict=False):
            start_value = float(start_value)
            end_value = float(end_value)
            if start_value == end_value:
                continue
            direction = "in" if start_value < end_value else "out"
            start = float(start_ms) / 1000.0
            duration = max((float(end_ms) - float(start_ms)) / 1000.0, 0.001)
            filters.append(
                f"fade=t={direction}:st={start:.3f}:d={duration:.3f}:alpha=1"
            )
        return filters

    expression = _track_frame_expression(keys, fps)
    return [
        "geq="
        "r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
        f"a='alpha(X,Y)*({expression})'"
    ]


def _track_frame_expression(keys: list, fps: int) -> str:
    """Piecewise-linear keyframe expression using FFmpeg's frame variable N."""
    segments: list[tuple[float, float, float, float, float]] = []
    for (t0, v0), (t1, v1) in zip(keys, keys[1:], strict=False):
        start = float(t0) / 1000.0 * fps
        end = float(t1) / 1000.0 * fps
        slope = (float(v1) - float(v0)) / max(end - start, 1e-9)
        segments.append((start, end, float(v0), float(v1), slope))
    expression = f"{segments[-1][3]:.6f}"
    for start, end, v0, _v1, slope in reversed(segments):
        value = f"{v0:.6f}+({slope:.9f})*(N-{start:.6f})"
        expression = f"if(lt(N,{end:.6f}),{value},{expression})"
    first_frame = float(keys[0][0]) / 1000.0 * fps
    expression = f"if(lt(N,{first_frame:.6f}),{float(keys[0][1]):.6f},{expression})"
    return expression.replace(",", r"\,")


def _text_window(text_animation: dict, duration_ms: int) -> tuple[int, int]:
    """Resolve an explicit semantic window, or the legacy timing track start."""
    start = text_animation.get("start_ms")
    end = text_animation.get("end_ms")
    timing = text_animation.get("timing") or {}
    timing_keys = timing if isinstance(timing, list) else timing.get("keyframes", [])
    if start is None and timing_keys:
        start = timing_keys[0][0]
    start_ms = int(start or 0)
    end_ms = int(duration_ms if end is None else end)
    if start_ms < 0 or end_ms <= start_ms or end_ms > duration_ms:
        raise MotionCompilerError(
            f"invalid text event window: start_ms={start_ms}, end_ms={end_ms}, "
            f"scene_duration_ms={duration_ms}"
        )
    return start_ms, end_ms


def _effect_filter(effect: dict, opts: CompileOptions) -> str:
    """Compile supported post-composition editorial effects."""
    effect_type = str(effect.get("type") or "")
    amount = max(0.0, float(effect.get("amount", 0.0)))
    if effect_type in {"film_grain", "paper_grain"}:
        strength = max(1, min(100, int(round(amount * 100))))
        seed = int(effect.get("seed", 42))
        return f"noise=alls={strength}:allf=t+u:all_seed={seed}"
    if effect_type == "jitter":
        raw_pixels = min(opts.width, opts.height) * amount if amount <= 0.1 else amount
        pixels = max(1, min(12, int(round(raw_pixels))))
        crop_width = opts.width - 2 * pixels
        crop_height = opts.height - 2 * pixels
        return (
            f"crop={crop_width}:{crop_height}:"
            f"x={pixels}+{pixels}*sin(n*0.700):"
            f"y={pixels}+{pixels}*cos(n*0.900),"
            f"scale={opts.width}:{opts.height}"
        )
    return ""


def _arg_path(path: str) -> str:
    """A path safe for an FFmpeg argument list.

    FFmpeg argument lists receive raw paths; backslashes and spaces are
    preserved as-is (no shell quoting needed). Windows drive letters are fine.
    """
    return path


def _terminate(cur: str, transition: str) -> str:
    """Return the final chain from ``cur`` to the ``[final]`` output label.

    Transitions (crossfade/dip_to_color) are chained as filters before the
    null terminator, so the graph keeps a single stream named ``[final]``.
    """
    if transition in ("none", "hard_cut"):
        return f"[{cur}]null[final]"
    if transition == "crossfade":
        return f"[{cur}]fade=t=in:st=0:d=0.3[final]"
    if transition == "dip_to_color":
        return f"[{cur}]fade=t=in:st=0:d=0.2:color=black[final]"
    return f"[{cur}]null[final]"  # other transitions handled by P6-T05


# Module-level compile helper.
def compile_plan(
    plan: dict,
    *,
    assets: dict[str, str] | None = None,
    ffmpeg_bin: str = "ffmpeg",
    output_path: str = "",
) -> CompiledMotion:
    """Convenience: compile a plan without instantiating the compiler."""
    return MotionCompiler(ffmpeg_bin=ffmpeg_bin).compile(
        plan, assets=assets, output_path=output_path
    )
