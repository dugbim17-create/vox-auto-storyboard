"""Unit tests for SceneDirectorV3, Relational Fingerprinting, Deduplication, and Atomic Readback (Phase 2B Correction 1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.schemas.scene_grammar_contracts import MapRouteContract, ProcessFlowContract
from app.schemas.scene_spec_v3 import SceneAction, compute_scene_spec_hash
from app.schemas.story_evidence import (
    ClaimSpec,
    EntitySpec,
    SourceRef,
    StoryEvidencePack,
)
from app.services.scene_director_v3 import (
    SceneDirectorV3,
    SceneDirectorV3Error,
)
from app.services.scene_spec_validator import SceneValidationError
from app.services.script_analysis import ScriptAnalyzer


def make_test_evidence_pack(project_id: str = "prj_v3_tracer") -> StoryEvidencePack:
    source = SourceRef(publisher="ASN", title="Accident Report", url="https://asn.local")
    claim = ClaimSpec(
        claim_id="C001_MH370",
        claim_text="Chuyến bay MH370 Boeing 777-200ER",
        claim_type="confirmed",
        entities=[
            EntitySpec(
                entity_id="aircraft_mh370",
                canonical_name="Boeing 777-200ER",
                attributes={"family": "777", "engine_count": 2},
            )
        ],
        sources=[source],
        must_show=["aircraft_mh370"],
        confidence=1.0,
    )
    return StoryEvidencePack(project_id=project_id, claims=[claim])


def test_fingerprint_changes_on_any_envelope_field() -> None:
    """Changing any request envelope field MUST produce distinct fingerprints (F5)."""
    evidence_pack = make_test_evidence_pack()
    director = SceneDirectorV3()

    base_fp = director.compute_fingerprint(
        project_id="prj_v3_tracer",
        scene_id="scene_001",
        script_text="Script",
        evidence_pack=evidence_pack,
        grammar="process_flow",
        visual_thesis="Thesis",
        purpose="body",
        continuity_in={"cut": "straight"},
        continuity_out={"cut": "straight"},
        renderer_profile="vox_classic",
        fps=30,
        motion_fps=12,
        start_state={"state": "initial"},
        end_state={"state": "modified_A"},
    )

    # 1. Changed purpose
    fp_purpose = director.compute_fingerprint(
        project_id="prj_v3_tracer", scene_id="scene_001", script_text="Script", evidence_pack=evidence_pack,
        grammar="process_flow", visual_thesis="Thesis", purpose="intro",
        continuity_in={"cut": "straight"}, continuity_out={"cut": "straight"}, renderer_profile="vox_classic",
        fps=30, motion_fps=12, start_state={"state": "initial"}, end_state={"state": "modified_A"},
    )
    assert base_fp != fp_purpose

    # 2. Changed continuity_in
    fp_cont = director.compute_fingerprint(
        project_id="prj_v3_tracer", scene_id="scene_001", script_text="Script", evidence_pack=evidence_pack,
        grammar="process_flow", visual_thesis="Thesis", purpose="body",
        continuity_in={"cut": "crossfade"}, continuity_out={"cut": "straight"}, renderer_profile="vox_classic",
        fps=30, motion_fps=12, start_state={"state": "initial"}, end_state={"state": "modified_A"},
    )
    assert base_fp != fp_cont

    # 3. Changed renderer_profile
    fp_prof = director.compute_fingerprint(
        project_id="prj_v3_tracer", scene_id="scene_001", script_text="Script", evidence_pack=evidence_pack,
        grammar="process_flow", visual_thesis="Thesis", purpose="body",
        continuity_in={"cut": "straight"}, continuity_out={"cut": "straight"}, renderer_profile="vox_modern",
        fps=30, motion_fps=12, start_state={"state": "initial"}, end_state={"state": "modified_A"},
    )
    assert base_fp != fp_prof

    # 4. Changed fps / motion_fps
    fp_fps = director.compute_fingerprint(
        project_id="prj_v3_tracer", scene_id="scene_001", script_text="Script", evidence_pack=evidence_pack,
        grammar="process_flow", visual_thesis="Thesis", purpose="body",
        continuity_in={"cut": "straight"}, continuity_out={"cut": "straight"}, renderer_profile="vox_classic",
        fps=60, motion_fps=24, start_state={"state": "initial"}, end_state={"state": "modified_A"},
    )
    assert base_fp != fp_fps


def test_vertical_persistence_and_atomic_readback(tmp_path: Path) -> None:
    evidence_pack = make_test_evidence_pack(project_id="prj_vertical_tracer")
    director = SceneDirectorV3(storage_root=tmp_path)

    contract = ProcessFlowContract(
        nodes=("source_corp", "target_acc"),
        edges=(("source_corp", "target_acc"),),
        token_label="Vốn điều lệ",
    )
    spec = director.plan_scene(
        project_id="prj_vertical_tracer",
        scene_id="scene_proc_01",
        script_text="Sơ đồ dòng tiền chuyển dịch từ công ty sang tài khoản thụ hưởng.",
        evidence_pack=evidence_pack,
        grammar="process_flow",
        visual_thesis="Dòng tiền chuyển nhượng cổ phần",
        duration_ms=5000,
        grammar_contract=contract,
        actions=[
            SceneAction(
                action_id="act_transfer",
                action_type="transfer_token",
                target_id="target_acc",
                source_id="source_corp",
                start_ms=1000,
                duration_ms=3000,
                params={"token_label": "Vốn điều lệ"},
            )
        ],
        start_state={"source_corp": "has_capital"},
        end_state={"target_acc": "funds_transferred"},
    )

    manifest_path = director.persist_scene_spec(spec)
    assert manifest_path.is_file()

    readback_spec = director.load_scene_spec(project_id="prj_vertical_tracer", scene_id="scene_proc_01", revision=spec.revision)
    assert readback_spec.spec_sha256 == spec.spec_sha256
    assert readback_spec.planning_fingerprint == spec.planning_fingerprint
    assert readback_spec.grammar == "process_flow"


def test_tampered_envelope_or_fingerprint_rejected_on_load(tmp_path: Path) -> None:
    """Attacker recomputing spec_sha256 after modifying envelope/fingerprint must still reject (F5)."""
    evidence_pack = make_test_evidence_pack(project_id="prj_tamper")
    director = SceneDirectorV3(storage_root=tmp_path)

    contract = MapRouteContract(
        route_id="r1", marker_id="m1", declared_polyline=((0.0, 0.0), (10.0, 10.0)),
        coordinate_authority="wgs84_projected", uncertainty_policy="none",
    )
    spec = director.plan_scene(
        project_id="prj_tamper",
        scene_id="scene_001",
        script_text="Script",
        evidence_pack=evidence_pack,
        grammar="map_route",
        visual_thesis="Original Thesis",
        duration_ms=4000,
        grammar_contract=contract,
        actions=[
            SceneAction(action_id="a1", action_type="path_draw", target_id="r1", start_ms=0, duration_ms=1000, params={"route_id": "r1"}),
            SceneAction(action_id="a2", action_type="traveling_marker", target_id="m1", start_ms=500, duration_ms=2000, params={"route_id": "r1"}),
        ],
    )
    manifest_path = director.persist_scene_spec(spec)

    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    # Modify start_state and forged fingerprint
    data["start_state"] = {"forged": True}
    data["spec_sha256"] = compute_scene_spec_hash(data)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with pytest.raises(SceneDirectorV3Error) as exc_info:
        director.load_scene_spec(project_id="prj_tamper", scene_id="scene_001", revision=1)
    assert "SPEC_INTEGRITY_MISMATCH" in str(exc_info.value)


@pytest.mark.asyncio
async def test_production_multi_scene_failure_promotes_no_partial_outputs(tmp_path: Path) -> None:
    """If scene 2 fails in a multi-scene storyboard, no scene manifests or aggregate files are promoted."""
    fake_planner = MagicMock()
    storyboard = {
        "project_id": "prj_multi_fail",
        "summary": "Summary",
        "style_anchor": {"visual_language": "vox_classic", "palette": ["#000"], "texture": ["grain"], "typography": "sans"},
        "characters": [],
        "locations": [],
        "scenes": [
            # Scene 1: valid map_route
            {
                "scene_id": "scene_001",
                "order": 1,
                "script_span": {"start_char": 0, "end_char": 50},
                "narration_text": "Narration 1",
                "visual_summary": "Summary 1",
                "image_prompt": "Prompt 1",
                "motion_template": "map_route",
                "estimated_duration_seconds": 4.0,
                "grammar": "map_route",
                "visual_thesis": "Thesis 1",
                "grammar_contract": {
                    "route_id": "r1",
                    "marker_id": "m1",
                    "continuous_path": True,
                    "declared_polyline": [[0.0, 0.0], [10.0, 10.0]],
                    "coordinate_authority": "wgs84_projected",
                    "uncertainty_policy": "none",
                },
                "actions": [
                    {"action_id": "a1", "action_type": "path_draw", "target_id": "r1", "start_ms": 0, "duration_ms": 1000, "params": {"route_id": "r1"}},
                    {"action_id": "a2", "action_type": "traveling_marker", "target_id": "m1", "start_ms": 500, "duration_ms": 2000, "params": {"route_id": "r1"}},
                ],
            },
            # Scene 2: broken map_route (empty params)
            {
                "scene_id": "scene_002",
                "order": 2,
                "script_span": {"start_char": 51, "end_char": 100},
                "narration_text": "Narration 2",
                "visual_summary": "Summary 2",
                "image_prompt": "Prompt 2",
                "motion_template": "map_route",
                "estimated_duration_seconds": 4.0,
                "grammar": "map_route",
                "visual_thesis": "Thesis 2",
                "params": {},  # broken!
            },
        ],
    }
    evidence_pack = make_test_evidence_pack(project_id="prj_multi_fail")
    analyzer = ScriptAnalyzer(planner_provider=fake_planner)

    with pytest.raises(SceneValidationError):
        await analyzer.plan_scenes_v3(
            storyboard=storyboard,
            evidence_pack=evidence_pack,
            project_id="prj_multi_fail",
            project_root=tmp_path,
        )

    # Neither scene 1 nor aggregate manifest should exist in production tree!
    scene_1_manifest = tmp_path / "prj_multi_fail" / "scenes" / "scene_001" / "rev_001" / "scene_spec_v3.json"
    aggregate_manifest = tmp_path / "prj_multi_fail" / "manifests" / "scenes_v3.json"
    assert not scene_1_manifest.is_file()
    assert not aggregate_manifest.is_file()
