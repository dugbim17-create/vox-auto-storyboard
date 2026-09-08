from __future__ import annotations

from PIL import Image

from app.schemas.semantic_scene import (
    CanonicalScene,
    build_canonical_scene,
    build_semantic_scene_spec,
)
from app.schemas.semantic_visual_stage import build_semantic_stage
from app.services.canonical_visual_planner import CanonicalVisualPlanner
from app.services.script_analysis import ScriptAnalyzer
from app.services.semantic_scene_renderer import VoxSemanticSceneRenderer


def canonical_payload() -> dict:
    return {
        "schema_version": "vox.scene/2.0",
        "project_id": "canonical-test",
        "scene_id": "S01",
        "revision": 1,
        "grammar": "object_assembly",
        "narration": "Apple mua NeXT và Jobs trở lại Apple.",
        "duration_ms": 3000,
        "fps": 30,
        "motion_fps": 12,
        "canvas": {"width": 640, "height": 360},
        "entities": [
            {
                "entity_id": "background",
                "kind": "background",
                "role": "background",
                "asset": "background.png",
                "sha256": "a" * 64,
                "x": 0,
                "y": 0,
                "z": 0,
            },
            {
                "entity_id": "jobs",
                "kind": "character",
                "role": "subject",
                "asset": "jobs.png",
                "sha256": "b" * 64,
                "x": 80,
                "y": 160,
                "z": 3,
            },
            {
                "entity_id": "next",
                "kind": "company",
                "role": "object",
                "asset": "next.png",
                "sha256": "c" * 64,
                "x": 240,
                "y": 160,
                "z": 2,
            },
            {
                "entity_id": "apple",
                "kind": "company",
                "role": "object",
                "asset": "apple.png",
                "sha256": "d" * 64,
                "x": 500,
                "y": 160,
                "z": 2,
            },
        ],
        "events": [
            {
                "event_id": "jobs_on",
                "anchor": "Apple mua NeXT",
                "start_ms": 0,
                "duration_ms": 400,
                "action": "reveal",
                "target": "jobs",
            },
            {
                "event_id": "next_on",
                "anchor": "Apple mua NeXT",
                "start_ms": 300,
                "duration_ms": 400,
                "action": "reveal",
                "target": "next",
            },
            {
                "event_id": "apple_on",
                "anchor": "Apple mua NeXT",
                "start_ms": 600,
                "duration_ms": 400,
                "action": "reveal",
                "target": "apple",
            },
            {
                "event_id": "acquire",
                "anchor": "Apple mua NeXT",
                "start_ms": 1100,
                "duration_ms": 700,
                "action": "connect",
                "source": "apple",
                "target": "next",
                "label": "MUA",
            },
            {
                "event_id": "return",
                "anchor": "Jobs trở lại Apple",
                "start_ms": 1900,
                "duration_ms": 800,
                "action": "move",
                "target": "jobs",
                "to_x": 390,
                "to_y": 160,
            },
        ],
    }


def test_canonical_scene_owns_entities_events_assets_and_motion() -> None:
    scene = build_canonical_scene(canonical_payload())
    assert isinstance(scene, CanonicalScene)
    assert scene.schema_version == "vox.scene/2.0"
    assert scene.background_entity.asset == "background.png"
    assert scene.visual_action_count == 5
    assert scene.entity_ids == ("background", "jobs", "next", "apple")
    render_plan = scene.to_render_plan()
    assert render_plan["assets"]["jobs"] == "jobs.png"
    assert render_plan["assets"]["background"] == "background.png"
    assert render_plan["z_order"]["background"] == 0
    assert render_plan["placements"]["apple"] == [500, 160]
    assert render_plan["procedural_actions"][3]["type"] == "connect"


def test_legacy_semantic_scene_spec_upgrades_to_canonical_scene() -> None:
    legacy = build_semantic_scene_spec(
        {
            "schema_version": "vox.scene/1.0",
            "project_id": "legacy",
            "scene_id": "P01",
            "revision": 1,
            "seed": 42,
            "grammar": "object_assembly",
            "duration_ms": 2000,
            "fps": 30,
            "motion_fps": 12,
            "assets": [
                {
                    "asset_id": "background",
                    "role": "background",
                    "kind": "rgba_image",
                    "path": "background.png",
                    "sha256": "a" * 64,
                },
                {
                    "asset_id": "part",
                    "role": "object",
                    "kind": "rgba_image",
                    "path": "part.png",
                    "sha256": "b" * 64,
                },
            ],
            "beats": [
                {
                    "beat_id": "assemble",
                    "anchor": "assemble part",
                    "actions": [
                        {
                            "action_id": "part_path",
                            "type": "object_path",
                            "subject": "part",
                            "duration_ms": 900,
                            "path": [[20, 100], [300, 100]],
                        }
                    ],
                }
            ],
        }
    )
    scene = legacy.to_canonical_scene()
    assert scene.schema_version == "vox.scene/2.0"
    assert scene.events[0].action == "object_path"
    assert scene.events[0].anchor == "assemble part"


def test_legacy_semantic_visual_stage_upgrades_to_canonical_scene() -> None:
    stage = build_semantic_stage(
        {
            "stage_id": "stage-1",
            "narration": "Apple mua NeXT.",
            "duration_ms": 1500,
            "background": "background.png",
            "canvas": {"width": 640, "height": 360},
            "entities": [
                {"entity_id": "apple", "kind": "company", "asset": "apple.png", "x": 400, "y": 100},
                {"entity_id": "next", "kind": "company", "asset": "next.png", "x": 100, "y": 100},
            ],
            "events": [
                {"event_id": "apple_on", "start_ms": 0, "duration_ms": 300, "action": "reveal", "target": "apple"},
                {"event_id": "next_on", "start_ms": 200, "duration_ms": 300, "action": "reveal", "target": "next"},
                {"event_id": "buy", "start_ms": 600, "duration_ms": 500, "action": "connect", "source": "apple", "target": "next", "label": "MUA"},
            ],
        }
    )
    scene = stage.to_canonical_scene(project_id="legacy-stage")
    assert scene.scene_id == "stage-1"
    assert scene.background_entity.entity_id == "background"
    assert scene.events[-1].action == "connect"


def test_canonical_scene_exposes_one_renderer_contract_only() -> None:
    scene = build_canonical_scene(canonical_payload())
    assert "procedural_actions" in scene.to_render_plan()
    assert not hasattr(scene, "to_visual_stage_plan")


def test_canonical_renderer_accepts_scene_without_parallel_adapter(tmp_path) -> None:
    payload = canonical_payload()
    for entity in payload["entities"]:
        path = tmp_path / entity["asset"]
        Image.new("RGBA", (640, 360) if entity["role"] == "background" else (80, 80), "#eee4ce").save(path)
        entity["asset"] = str(path)
    scene = build_canonical_scene(payload)
    renderer = VoxSemanticSceneRenderer()
    output = renderer.render_scene(scene, tmp_path / "scene.mp4")
    assert output.is_file()
    assert renderer.renderer_name == "vox_semantic_ffmpeg_pillow"


def test_canonical_renderer_moves_entity_on_move_event(tmp_path) -> None:
    from app.services.semantic_scene_renderer import render_semantic_frame

    payload = canonical_payload()
    for index, entity in enumerate(payload["entities"]):
        path = tmp_path / entity["asset"]
        color = "#eee4ce" if entity["role"] == "background" else ("#cf2637" if index == 1 else "#424a52")
        Image.new("RGBA", (640, 360) if entity["role"] == "background" else (40, 40), color).save(path)
        entity["asset"] = str(path)
    scene = build_canonical_scene(payload)
    before = render_semantic_frame(scene.to_render_plan(), 1900)
    after = render_semantic_frame(scene.to_render_plan(), 2600)
    assert before != after


class FakePlanner:
    async def generate_json(self, **kwargs):
        assert kwargs["schema"]["required"] == ["scenes"]
        return {"scenes": [canonical_payload()]}


class MalformedThenValidPlanner:
    def __init__(self):
        self.calls = 0

    async def generate_json(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("model returned malformed JSON")
        return {"scenes": [canonical_payload()]}


class RepairingPlanner:
    def __init__(self):
        self.calls = 0

    async def generate_json(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            broken = canonical_payload()
            broken["entities"][1]["entity_id"] = "background"
            return {"scenes": [broken]}
        assert "validation error" in kwargs["user_prompt"]
        return {"scenes": [canonical_payload()]}


def test_ai_visual_planner_validates_model_output_as_canonical_scene() -> None:
    planner = CanonicalVisualPlanner(FakePlanner())
    scenes = __import__("asyncio").run(
        planner.plan(
            project_id="canonical-test",
            storyboard={"scenes": [{"scene_id": "S01", "narration_text": canonical_payload()["narration"]}]},
            voice_durations_ms={"S01": 3000},
        )
    )
    assert list(scenes) == ["S01"]
    assert scenes["S01"].visual_action_count == 5
    assert scenes["S01"].background_entity.role == "background"


def test_ai_visual_planner_retries_one_malformed_provider_response() -> None:
    import asyncio

    provider = MalformedThenValidPlanner()
    scenes = asyncio.run(
        CanonicalVisualPlanner(provider).plan(
            project_id="canonical-test",
            storyboard={"scenes": [{"scene_id": "S01", "narration_text": canonical_payload()["narration"]}]},
            voice_durations_ms={"S01": 3000},
        )
    )
    assert provider.calls == 2
    assert scenes["S01"].scene_id == "S01"


def test_materialized_canonical_scene_maps_all_logical_assets_to_pack_roles() -> None:
    from app.services.vox_production_pipeline import _materialize_canonical_scene

    payload = canonical_payload()
    payload["entities"][1]["asset"] = "asset://fonts/heading_bold"
    payload["entities"][1]["role"] = "object"
    scene = _materialize_canonical_scene(
        payload,
        project_id="canonical-test",
        scene_id="S01",
        duration_ms=3000,
        pack_assets={
            "background": "background.png",
            "subject": "subject.png",
            "foreground": "foreground.png",
            "texture": "texture.png",
        },
    )
    assert scene.entities[1].asset == "subject.png"


def test_materialized_canonical_scene_preserves_background_identity() -> None:
    from app.services.vox_production_pipeline import _materialize_canonical_scene

    payload = canonical_payload()
    payload["entities"][0]["entity_id"] = "bg_alias"
    payload["entities"][0]["asset"] = "asset://backgrounds/dark_gradient"
    scene = _materialize_canonical_scene(
        payload,
        project_id="canonical-test",
        scene_id="S01",
        duration_ms=3000,
        pack_assets={
            "background": "background.png",
            "subject": "subject.png",
            "foreground": "foreground.png",
            "texture": "texture.png",
        },
    )
    plan = scene.to_render_plan()
    assert plan["assets"]["background"] == "background.png"
    assert "bg_alias" not in plan["assets"]


def test_ai_visual_planner_repairs_one_invalid_live_contract() -> None:
    import asyncio

    provider = RepairingPlanner()
    scenes = asyncio.run(
        CanonicalVisualPlanner(provider).plan(
            project_id="canonical-test",
            storyboard={"scenes": [{"scene_id": "S01", "narration_text": canonical_payload()["narration"]}]},
            voice_durations_ms={"S01": 3000},
        )
    )
    assert provider.calls == 2
    assert scenes["S01"].entity_ids[1] == "jobs"


def test_ai_visual_planner_normalizes_common_model_aliases_without_extra_call() -> None:
    import asyncio

    payload = canonical_payload()
    payload["grammar"] = "standard"
    payload["fps"] = 60
    payload["motion_fps"] = 60
    payload["entities"] = [
        {
            "id": item["entity_id"],
            "type": item["kind"],
            "asset": item["asset"],
            "transform": {"position": [item["x"], item["y"], 0]},
        }
        for item in payload["entities"]
    ]
    payload["events"] = [
        {"at_ms": 0, "duration_ms": 400, "type": "fade_in", "entity_id": "jobs"},
        {
            "at_ms": 800,
            "duration_ms": 600,
            "type": "transform",
            "entity_id": "jobs",
            "target_transform": {"position": [390, 160, 0]},
        },
    ]

    class AliasPlanner:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, **kwargs):
            self.calls += 1
            return {"scenes": [payload]}

    provider = AliasPlanner()
    scenes = asyncio.run(
        CanonicalVisualPlanner(provider).plan(
            project_id="canonical-test",
            storyboard={"scenes": [{"scene_id": "S01", "narration_text": payload["narration"]}]},
            voice_durations_ms={"S01": 3000},
        )
    )
    assert provider.calls == 1
    assert scenes["S01"].fps == 30
    assert scenes["S01"].events[0].action == "reveal"
    assert scenes["S01"].events[1].action == "move"


def test_ai_visual_planner_normalizes_object_grammar() -> None:
    import asyncio

    payload = canonical_payload()
    payload["grammar"] = {"type": "object_assembly"}

    class ObjectGrammarPlanner:
        async def generate_json(self, **kwargs):
            return {"scenes": [payload]}

    scenes = asyncio.run(
        CanonicalVisualPlanner(ObjectGrammarPlanner()).plan(
            project_id="canonical-test",
            storyboard={"scenes": [{"scene_id": "S01", "narration_text": payload["narration"]}]},
            voice_durations_ms={"S01": 3000},
        )
    )
    assert scenes["S01"].grammar == "object_assembly"


def test_production_pipeline_prefers_authored_canonical_visual_scene(tmp_path) -> None:
    from types import SimpleNamespace

    from PIL import ImageDraw

    from app.services.vox_production_pipeline import VoxProductionPipeline
    from app.storage.asset_store import AssetStore

    class FakeSegmentation:
        def produce_mask(self, image: Image.Image) -> Image.Image:
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).rectangle((30, 20, 150, 160), fill=255)
            return mask

    root = tmp_path / "projects"
    store = AssetStore(root)
    store.init_project("canonical-production")
    source = tmp_path / "source.png"
    Image.new("RGB", (320, 180), "#eee4ce").save(source)
    payload = canonical_payload()
    payload["project_id"] = "canonical-production"
    payload["duration_ms"] = 2340
    payload["canvas"] = {"width": 320, "height": 180}
    for entity in payload["entities"]:
        if entity["role"] != "background":
            entity["asset"] = "role://subject"
    for event in payload["events"]:
        event["start_ms"] = min(event["start_ms"], 1900)
        event["duration_ms"] = min(event["duration_ms"], 2340 - event["start_ms"])
    storyboard = {
        "project_id": "canonical-production",
        "scenes": [
            {
                "scene_id": "S01",
                "order": 1,
                "purpose": "opening",
                "narration_text": payload["narration"],
                "canonical_visual_scene": payload,
            }
        ],
    }
    result = VoxProductionPipeline(
        project_root=store.base,
        canvas_size=(320, 180),
        segmentation_backend=FakeSegmentation(),
    ).prepare(
        "canonical-production",
        storyboard=storyboard,
        selected_assets={"S01": SimpleNamespace(path=str(source))},
        voice_durations_ms={"S01": 2000},
        store=store,
    )
    assert result.canonical_scenes["S01"].events[-1].action == "move"
    assert result.canonical_scenes["S01"].entities[1].asset.startswith(str(store.base))


def test_script_analyzer_persists_canonical_visual_plan_for_production(tmp_path) -> None:
    import asyncio

    from app.storage.asset_store import AssetStore

    storyboard = {
        "project_id": "canonical-test",
        "scenes": [{"scene_id": "S01", "narration_text": canonical_payload()["narration"]}],
    }
    analyzer = ScriptAnalyzer(FakePlanner())
    planned = asyncio.run(
        analyzer.plan_canonical_visuals(
            storyboard,
            project_id="canonical-test",
            voice_durations_ms={"S01": 3000},
            project_root=tmp_path,
        )
    )
    path = AssetStore(tmp_path).subdir("canonical-test", "manifests") / "canonical_scenes.json"
    assert path.is_file()
    persisted = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert persisted["kind"] == "canonical_scenes"
    assert persisted["scenes"][0]["schema_version"] == "vox.scene/2.0"
    assert planned["scenes"][0]["canonical_visual_scene"]["events"][3]["action"] == "connect"
