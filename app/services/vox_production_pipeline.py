"""Shared production preparation for benchmark-style layered VOX rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.semantic_scene import CanonicalScene, build_canonical_scene
from app.services.layer_workflow import LayerWorkflow
from app.services.render_lineage import build_motion_lineage_envelope, write_lineage_manifest
from app.services.visual_event_assets import materialize_visual_event_assets
from app.services.visual_stage_lineage import (
    build_visual_stage_envelope,
    write_visual_stage_envelope,
)
from app.services.vox_asset_pack import VoxAssetPackBuilder, derive_vox_beat, semantic_purpose
from app.services.vox_event_stage import build_scene_visual_stage
from app.services.vox_scene_planner import plan_vox_scene
from app.storage.asset_store import AssetStore


@dataclass(frozen=True)
class VoxProductionResult:
    project_id: str
    scene_ids: list[str]
    asset_maps: dict[str, dict[str, str]]
    visual_change_budget: int
    median_change_interval_ms: int
    event_stages: dict[str, dict]
    event_stage_ids: list[str]
    event_count: int
    canonical_scenes: dict[str, CanonicalScene]


class VoxProductionPipeline:
    """Create semantic asset packs and lineage motion for every storyboard scene."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        canvas_size: tuple[int, int] = (1920, 1080),
        fps: int = 30,
        segmentation_backend: Any | None = None,
    ) -> None:
        self.project_root = project_root
        self.canvas_size = canvas_size
        self.fps = fps
        self.segmentation_backend = segmentation_backend

    def prepare(
        self,
        project_id: str,
        *,
        storyboard: dict,
        selected_assets: dict[str, Any],
        voice_durations_ms: dict[str, int],
        store: AssetStore | None = None,
    ) -> VoxProductionResult:
        store = store or AssetStore(self.project_root)
        scenes = sorted(
            [item for item in storyboard.get("scenes", []) if isinstance(item, dict)],
            key=lambda item: int(item.get("order") or 0),
        )
        if not scenes:
            raise RuntimeError("VOX production requires storyboard scenes")
        style_snapshot = storyboard.get("style_snapshot")
        if not isinstance(style_snapshot, dict):
            style_snapshot = {}
        asset_maps: dict[str, dict[str, str]] = {}
        event_stages: dict[str, dict] = {}
        canonical_scenes: dict[str, CanonicalScene] = {}
        event_count = 0
        motion_dir = store.subdir(project_id, "manifests") / "motion"
        motion_dir.mkdir(parents=True, exist_ok=True)
        changes = 0
        for index, scene in enumerate(scenes, start=1):
            scene_id = str(scene.get("scene_id") or "")
            if not scene_id:
                raise RuntimeError("VOX storyboard scene missing scene_id")
            selected = selected_assets.get(scene_id)
            if selected is None or not Path(str(selected.path)).is_file():
                raise RuntimeError(f"VOX selected asset missing: {scene_id}")
            duration_ms = int(voice_durations_ms.get(scene_id) or 0)
            if duration_ms <= 0:
                raise RuntimeError(f"VOX voice duration missing: {scene_id}")
            purpose = semantic_purpose(scene, order=index, total=len(scenes))
            beat = derive_vox_beat(
                scene_id=scene_id,
                narration=str(scene.get("narration_text") or ""),
                purpose=purpose,
                order=index,
            )
            separated = LayerWorkflow(
                canvas_width=self.canvas_size[0],
                canvas_height=self.canvas_size[1],
                aspect_ratio=str(storyboard.get("aspect_ratio") or "16:9"),
                project_root=store.base,
                segmentation_backend=self.segmentation_backend,
            ).prepare_composite(
                project_id,
                scene_id,
                str(selected.path),
                store=store,
                require_subject=True,
            )
            if not separated.ok:
                raise RuntimeError(f"{scene_id}: {separated.error}")
            by_role = {layer.role: layer.path for layer in separated.layers}
            if "subject" not in by_role or "background" not in by_role:
                raise RuntimeError(f"{scene_id}: separated subject/background missing")
            pack = VoxAssetPackBuilder(
                canvas_size=self.canvas_size,
                project_root=store.base,
            ).build(
                project_id,
                beat,
                background_path=by_role["background"],
                subject_path=by_role["subject"],
                store=store,
            )
            if not pack.ok:
                raise RuntimeError(f"{scene_id}: {pack.error}")
            asset_maps[scene_id] = dict(pack.assets)
            stage = build_scene_visual_stage(
                scene={
                    **scene,
                    "canvas": {
                        "width": self.canvas_size[0],
                        "height": self.canvas_size[1],
                    },
                },
                duration_ms=duration_ms + 340,
                background=pack.assets["background"],
                asset_roles=frozenset(pack.assets),
            )
            event_asset_dir = store.subdir(project_id, "event_assets") / scene_id
            event_assets = materialize_visual_event_assets(
                stage,
                role_assets=pack.assets,
                output_dir=event_asset_dir,
            )
            event_asset_manifest = event_assets.pop("_manifest")
            stage_payload = stage.to_dict()
            for event_payload in stage_payload["events"]:
                event_payload["asset"] = event_assets[event_payload["event_id"]]
            stage = build_scene_visual_stage(
                scene={
                    **scene,
                    "visual_events": stage_payload["events"],
                    "canvas": stage_payload["canvas"],
                },
                duration_ms=duration_ms + 340,
                background=pack.assets["background"],
                asset_roles=frozenset(pack.assets),
            )
            stage_envelope = build_visual_stage_envelope(
                stage,
                style_snapshot=style_snapshot,
            )
            stage_envelope["event_assets_manifest"] = event_asset_manifest
            write_visual_stage_envelope(
                store.subdir(project_id, "manifests") / "visual_events" / f"{scene_id}.json",
                stage_envelope,
            )
            event_stages[scene_id] = stage_envelope
            event_count += stage.event_count
            authored_canonical = scene.get("canonical_visual_scene")
            if isinstance(authored_canonical, dict):
                canonical_scenes[scene_id] = _materialize_canonical_scene(
                    authored_canonical,
                    project_id=project_id,
                    scene_id=scene_id,
                    duration_ms=duration_ms + 340,
                    pack_assets=pack.assets,
                )
            else:
                canonical_scenes[scene_id] = _canonical_from_visual_stage(
                    project_id=project_id,
                    scene=scene,
                    stage_payload=stage_payload,
                    fps=self.fps,
                    motion_fps=12,
                )
            planned = plan_vox_scene(
                scene_id=scene_id,
                narration=beat.narration,
                purpose=beat.visual_function,
                duration_ms=duration_ms + 340,
                canvas_size=self.canvas_size,
                available_roles=frozenset(pack.assets),
                authored_text=beat.keyword,
                seed=42 + index,
            )
            write_lineage_manifest(
                motion_dir / f"{scene_id}.json",
                build_motion_lineage_envelope(
                    planned.plan,
                    style_snapshot=style_snapshot,
                ),
            )
            changes += max(3, len(planned.plan.get("layers", [])))
        total_duration = sum(int(voice_durations_ms[item["scene_id"]]) + 340 for item in scenes)
        interval = max(1, round(total_duration / max(changes, 1)))
        return VoxProductionResult(
            project_id=project_id,
            scene_ids=[str(item["scene_id"]) for item in scenes],
            asset_maps=asset_maps,
            visual_change_budget=changes,
            median_change_interval_ms=interval,
            event_stages=event_stages,
            event_stage_ids=[str(item["scene_id"]) for item in scenes],
            event_count=event_count,
            canonical_scenes=canonical_scenes,
        )


class VoxLayeredSceneRenderer:
    """Thin renderer adapter that supplies semantic asset maps to FFmpeg."""

    renderer_name = "ffmpeg_vox_layered"
    renderer_version = "1"

    def __init__(self, base_renderer: Any, asset_maps: dict[str, dict[str, str]]) -> None:
        self.base_renderer = base_renderer
        self.asset_maps = asset_maps

    def render_scene(
        self,
        project_id: str,
        scene_id: str,
        plan: dict,
        *,
        assets: dict[str, str] | None = None,
        project_root: str | Path | None = None,
    ):
        del assets
        return self.base_renderer.render_scene(
            project_id,
            scene_id,
            plan,
            assets=self.asset_maps[scene_id],
            project_root=project_root,
        )


def _canonical_from_visual_stage(
    *,
    project_id: str,
    scene: dict[str, Any],
    stage_payload: dict[str, Any],
    fps: int,
    motion_fps: int,
) -> CanonicalScene:
    entities = [
        {
            "entity_id": "background",
            "kind": "background",
            "role": "background",
            "asset": stage_payload["background"],
            "sha256": "",
            "x": 0,
            "y": 0,
            "z": 0,
        }
    ]
    events: list[dict[str, Any]] = []
    for index, event in enumerate(stage_payload["events"]):
        entity_id = f"event_asset_{index + 1:02d}"
        entities.append(
            {
                "entity_id": entity_id,
                "kind": "semantic_asset",
                "role": "object",
                "asset": event["asset"],
                "sha256": "",
                "x": 0,
                "y": 0,
                "z": int(event.get("z") or 10),
                "metadata": {"placement": event.get("placement") or "center"},
            }
        )
        events.append(
            {
                "event_id": event["event_id"],
                "anchor": event.get("trigger") or stage_payload["narration"],
                "start_ms": event["start_ms"],
                "duration_ms": event["duration_ms"],
                "action": "reveal",
                "target": entity_id,
                "enter": event.get("enter") or "popup",
                "placement": event.get("placement") or "center",
            }
        )
    return build_canonical_scene(
        {
            "schema_version": "vox.scene/2.0",
            "project_id": project_id,
            "scene_id": stage_payload["stage_id"],
            "revision": 1,
            "grammar": "explanatory_hold",
            "narration": stage_payload["narration"],
            "duration_ms": stage_payload["duration_ms"],
            "fps": fps,
            "motion_fps": motion_fps,
            "canvas": stage_payload["canvas"],
            "entities": entities,
            "events": events,
        }
    )


def _materialize_canonical_scene(
    payload: dict[str, Any],
    *,
    project_id: str,
    scene_id: str,
    duration_ms: int,
    pack_assets: dict[str, str],
) -> CanonicalScene:
    materialized = {
        **payload,
        "project_id": project_id,
        "scene_id": scene_id,
        "duration_ms": duration_ms,
        "entities": [dict(entity) for entity in payload.get("entities") or []],
        "events": [dict(event) for event in payload.get("events") or []],
    }
    for entity in materialized["entities"]:
        if entity.get("role") == "background":
            entity["entity_id"] = "background"
            break
    for entity in materialized["entities"]:
        logical = str(entity.get("asset") or "")
        if logical.startswith("role://"):
            role = logical.removeprefix("role://")
            if role not in pack_assets:
                raise RuntimeError(f"canonical asset role missing: {scene_id}/{role}")
            entity["asset"] = pack_assets[role]
        elif entity.get("role") == "background":
            entity["asset"] = pack_assets["background"]
        elif logical.startswith("asset://"):
            kind = str(entity.get("kind") or "").casefold()
            role = str(entity.get("role") or "").casefold()
            if kind in {"texture", "grain"} or role == "texture":
                entity["asset"] = pack_assets["texture"]
            elif kind in {"foreground", "arrow", "line", "chart", "document"} or role == "foreground":
                entity["asset"] = pack_assets["foreground"]
            else:
                entity["asset"] = pack_assets["subject"]
    for event in materialized["events"]:
        start = int(event.get("start_ms") or 0)
        event["duration_ms"] = min(
            int(event.get("duration_ms") or 1),
            duration_ms - start,
        )
    return build_canonical_scene(materialized)
