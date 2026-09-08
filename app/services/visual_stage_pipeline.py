"""Production seam from VisualStage contract to the event renderer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.visual_events import VisualStage, build_visual_stage
from app.services.ffmpeg_compiler import CompileOptions
from app.services.visual_event_renderer import VisualEventCompiler


@dataclass(frozen=True)
class PreparedVisualStage:
    stage_id: str
    duration_ms: int
    event_ids: tuple[str, ...]
    command: list[str]
    filter_graph: str
    manifest_path: str

    @property
    def event_count(self) -> int:
        return len(self.event_ids)


class VisualStagePipeline:
    """Validate, persist, and compile one accumulated narration stage."""

    def __init__(self, *, compiler: VisualEventCompiler | None = None) -> None:
        self.compiler = compiler or VisualEventCompiler()

    def prepare_stage(
        self,
        stage: VisualStage | dict[str, Any],
        *,
        assets: dict[str, str],
        output_path: str | Path,
        manifest_path: str | Path,
        options: CompileOptions | None = None,
    ) -> PreparedVisualStage:
        validated = build_visual_stage(stage) if isinstance(stage, dict) else stage
        manifest = Path(manifest_path)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(validated.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        command = self.compiler.compile(
            validated,
            assets=assets,
            output_path=output_path,
            options=options,
        )
        graph, _ = self.compiler.build_filter_graph(
            validated,
            assets=assets,
            options=options
            or CompileOptions(
                width=validated.canvas_width,
                height=validated.canvas_height,
            ),
        )
        return PreparedVisualStage(
            stage_id=validated.stage_id,
            duration_ms=validated.duration_ms,
            event_ids=tuple(event.event_id for event in validated.events),
            command=command,
            filter_graph=graph,
            manifest_path=str(manifest),
        )
