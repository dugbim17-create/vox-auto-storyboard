"""Deterministic FFmpeg compiler for accumulated VisualStage events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.visual_events import VisualEvent, VisualStage, build_visual_stage
from app.services.ffmpeg_compiler import CompileOptions


class VisualEventRenderError(ValueError):
    """Raised when a stage event cannot be compiled."""


PLACEMENTS = {
    "center_top": "x=(W-w)/2:y=120",
    "center": "x=(W-w)/2:y=(H-h)/2",
    "left": "x=120:y=(H-h)/2",
    "left_center": "x=180:y=(H-h)/2",
    "left_bottom": "x=140:y=H-h-120",
    "right": "x=W-w-140:y=(H-h)/2",
    "right_bottom": "x=W-w-140:y=H-h-140",
    "top_left": "x=120:y=120",
    "top_right": "x=W-w-120:y=120",
}


class VisualEventCompiler:
    """Compile a persistent stage into one FFmpeg filter graph.

    Event inputs are transparent stills or authored text cards. Events remain
    visible after their entrance unless ``persistent`` is false or an explicit
    exit is requested. This is the core distinction from scene-per-sentence
    rendering.
    """

    def __init__(self, *, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin

    def compile(
        self,
        stage: VisualStage | dict[str, Any],
        *,
        assets: dict[str, str],
        output_path: str | Path,
        options: CompileOptions | None = None,
    ) -> list[str]:
        validated = build_visual_stage(stage) if isinstance(stage, dict) else stage
        opts = options or CompileOptions(
            fps=30,
            width=validated.canvas_width,
            height=validated.canvas_height,
        )
        graph, input_assets = self.build_filter_graph(validated, assets=assets, options=opts)
        command: list[str] = [
            self.ffmpeg_bin,
            "-y",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-filter_complex_threads",
            "1",
            "-loop",
            "1",
            "-framerate",
            str(opts.fps),
            "-i",
            validated.background,
        ]
        for asset in input_assets:
            command.extend(["-loop", "1", "-framerate", str(opts.fps), "-i", asset])
        command.extend(
            [
                "-filter_complex",
                graph,
                "-map",
                "[final]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                str(opts.crf),
                "-preset",
                opts.preset,
                "-r",
                str(opts.fps),
                "-t",
                f"{validated.duration_ms / 1000:.3f}",
                str(output_path),
            ]
        )
        return command

    def build_filter_graph(
        self,
        stage: VisualStage,
        *,
        assets: dict[str, str],
        options: CompileOptions,
    ) -> tuple[str, list[str]]:
        inputs: list[str] = []
        parts = [
            f"[0:v]scale={options.width}:{options.height}:force_original_aspect_ratio=increase,crop={options.width}:{options.height},format=rgba[stage0]"
        ]
        current = "stage0"
        for index, event in enumerate(stage.events, start=1):
            asset = assets.get(event.asset, event.asset)
            if not asset:
                raise VisualEventRenderError(f"missing asset for event {event.event_id}: {event.asset}")
            inputs.append(str(asset))
            label = f"ev{index}"
            start = event.start_ms / 1000.0
            duration = event.duration_ms / 1000.0
            entrance = self._entrance(event, options.fps)
            parts.append(
                f"[{index}:v]format=rgba,{entrance},setpts=PTS-STARTPTS[{label}]"
            )
            placement = PLACEMENTS.get(event.placement)
            if placement is None:
                raise VisualEventRenderError(f"unknown placement {event.placement!r}")
            out = f"stage{index}"
            parts.append(
                f"[{current}][{label}]overlay={placement}:enable='between(t,{start:.3f},{start + duration:.3f})'"
                f":eof_action=repeat[{out}]"
            )
            current = out
            if event.exit != "none" and not event.persistent:
                # The first production slice intentionally supports fade-out;
                # other exits remain explicit schema options for later adapters.
                parts.append(f"[{current}]fade=t=out:st={start + duration:.3f}:d=0.15:alpha=1[stage{index}x]")
                current = f"stage{index}x"
        parts.append(f"[{current}]format=yuv420p[final]")
        return ";\n".join(parts), inputs

    @staticmethod
    def _entrance(event: VisualEvent, fps: int) -> str:
        del fps
        if event.enter in {"fade", "popup", "glow"}:
            return f"fade=t=in:st=0:d={min(0.28, event.duration_ms / 1000):.3f}:alpha=1"
        if event.enter == "stamp":
            return "fade=t=in:st=0:d=0.12:alpha=1,scale=iw*1.08:ih*1.08,scale=iw/1.08:ih/1.08"
        if event.enter == "counter":
            return "fade=t=in:st=0:d=0.18:alpha=1,scale=iw*1.02:ih*1.02"
        if event.enter in {"swipe_left", "swipe_right", "swipe_up", "page_flip", "line_draw", "shake"}:
            return "fade=t=in:st=0:d=0.22:alpha=1"
        return "null"


def compile_visual_stage(
    stage: VisualStage | dict[str, Any],
    *,
    assets: dict[str, str],
    output_path: str | Path,
    options: CompileOptions | None = None,
) -> list[str]:
    return VisualEventCompiler().compile(stage, assets=assets, output_path=output_path, options=options)


__all__ = ["VisualEventCompiler", "VisualEventRenderError", "compile_visual_stage"]


# Keep ``Path`` imported in the public module so callers can pass Windows paths
# without normalising them through a shell.
_ = Path
