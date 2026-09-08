"""Adversarial Acceptance Suite for Vox Semantic V3.

Phase 1 status:
- Cases 1-3: GREEN (PASS) via production ClaimAssetValidator & StoryEvidencePack API
Phase 2 status:
- Cases 5-7: GREEN (PASS) via production SceneSpecValidator & SceneSpec v3 structural grammar contracts
  (Note: pixel rendered-motion validation is separately tested in Phase 4)
Phase 3/6/7 status:
- Case 4: strict XFAIL reserved for Phase 3/7 (Asset Quality & Vision Critic)
- Case 8: strict XFAIL reserved for Phase 6 (Three Visual Families Separation)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas.scene_grammar_contracts import (
    MapRouteContract,
    ObjectAssemblyContract,
    ProcessFlowContract,
)
from app.schemas.scene_spec_v3 import SceneAction, SceneSpecV3
from app.schemas.story_evidence import ClaimSpec
from app.services.claim_asset_validator import (
    ENTITY_ATTRIBUTE_MISMATCH,
    FORBIDDEN_PLACEHOLDER,
    INSTITUTION_JURISDICTION_MISMATCH,
    LOCALE_MISMATCH,
    ClaimAssetValidator,
    ClaimValidationError,
)
from app.services.claim_asset_validator import (
    VALIDATION_OK as CLAIM_VALIDATION_OK,
)
from app.services.scene_spec_validator import (
    MAP_DISCONTINUOUS_ROUTE,
    OBJECT_ASSEMBLY_NO_TRANSFORMATION,
    PROCESS_FLOW_NO_TRANSFER,
    REVEAL_ONLY_ACTION_REJECTED,
    SceneSpecValidator,
    SceneValidationError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "vox_v3"


def load_fixture(rel_path: str) -> dict[str, Any]:
    path = FIXTURES_DIR / rel_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing required fixture: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# 1. MH370: Wrong Aircraft Entity Mismatch (Phase 1: GREEN via ClaimAssetValidator)
# ==============================================================================
def test_mh370_wrong_aircraft_entity_mismatch_rejected() -> None:
    claim = ClaimSpec.from_dict(load_fixture("claims/claim_mh370.json"))
    candidate_asset = load_fixture("assets/asset_mh370_b747_mismatch.json")

    validator = ClaimAssetValidator()

    # 1. Production API rejects candidate with mismatched airframe / engine count
    result = validator.validate_candidate(claim=claim, candidate=candidate_asset)
    assert not result.valid
    assert result.reason_code == ENTITY_ATTRIBUTE_MISMATCH
    assert "777" in result.message and "747" in result.message

    with pytest.raises(ClaimValidationError) as exc_info:
        validator.assert_valid_candidate(claim=claim, candidate=candidate_asset)
    assert exc_info.value.reason_code == ENTITY_ATTRIBUTE_MISMATCH

    # 2. Production API accepts valid exact Boeing 777-200ER candidate with all required attributes
    valid_candidate = {
        "asset_id": "asset_b777_exact",
        "identified_metadata": {
            "canonical_name": "Boeing 777-200ER",
            "family": "777",
            "variant": "200ER",
            "engine_count": 2,
            "operator": "Malaysia Airlines",
            "registration": "9M-MRO",
            "manufacturer": "Boeing",
        },
    }
    valid_res = validator.validate_candidate(claim=claim, candidate=valid_candidate)
    assert valid_res.valid
    assert valid_res.reason_code == CLAIM_VALIDATION_OK


# ==============================================================================
# 2. SCB: Wrong Institution / Foreign Bank (Phase 1: GREEN via ClaimAssetValidator)
# ==============================================================================
def test_scb_wrong_institution_rejected() -> None:
    claim = ClaimSpec.from_dict(load_fixture("claims/claim_scb_vn.json"))
    candidate_asset = load_fixture("assets/asset_scb_thailand_mismatch.json")

    validator = ClaimAssetValidator()

    # 1. Production API rejects Siam Commercial Bank (TH) for Saigon Commercial Bank (VN)
    result = validator.validate_candidate(claim=claim, candidate=candidate_asset)
    assert not result.valid
    assert result.reason_code == INSTITUTION_JURISDICTION_MISMATCH
    assert "Siam Commercial Bank" in result.message

    with pytest.raises(ClaimValidationError) as exc_info:
        validator.assert_valid_candidate(claim=claim, candidate=candidate_asset)
    assert exc_info.value.reason_code == INSTITUTION_JURISDICTION_MISMATCH

    # 2. Production API accepts valid Saigon Commercial Bank candidate with required attributes
    valid_candidate = {
        "asset_id": "asset_scb_vn_exact",
        "identified_metadata": {
            "canonical_name": "Saigon Commercial Bank",
            "vietnamese_name": "Ngân hàng Thương mại Cổ phần Sài Gòn",
            "jurisdiction": "VN",
            "country": "Vietnam",
            "ticker_alias": "SCB",
            "headquarters": "TP. Hồ Chí Minh, Việt Nam",
        },
    }
    valid_res = validator.validate_candidate(claim=claim, candidate=valid_candidate)
    assert valid_res.valid
    assert valid_res.reason_code == CLAIM_VALIDATION_OK


# ==============================================================================
# 3. True Crime: Foreign US Placeholder in VN Case (Phase 1: GREEN via ClaimAssetValidator)
# ==============================================================================
def test_true_crime_foreign_placeholder_rejected() -> None:
    claim = ClaimSpec.from_dict(load_fixture("claims/claim_true_crime_vn.json"))
    candidate_asset = load_fixture("assets/asset_true_crime_us_placeholder.json")

    validator = ClaimAssetValidator()

    # 1. Production API rejects forbidden foreign US placeholder in Vietnamese case
    result = validator.validate_candidate(claim=claim, candidate=candidate_asset)
    assert not result.valid
    assert result.reason_code in (FORBIDDEN_PLACEHOLDER, LOCALE_MISMATCH)

    with pytest.raises(ClaimValidationError) as exc_info:
        validator.assert_valid_candidate(claim=claim, candidate=candidate_asset)
    assert exc_info.value.reason_code in (FORBIDDEN_PLACEHOLDER, LOCALE_MISMATCH)

    # 2. Production API accepts valid Vietnamese casefile asset
    valid_candidate = {
        "asset_id": "asset_tc_vn_exact",
        "intended_entity_id": "doc_casefile_vn",
        "identified_metadata": {
            "canonical_name": "Hồ sơ vụ án hình sự Việt Nam",
            "country": "Vietnam",
            "locale": "vi-VN",
            "detected_placeholders": [],
        },
    }
    valid_res = validator.validate_candidate(claim=claim, candidate=valid_candidate)
    assert valid_res.valid
    assert valid_res.reason_code == CLAIM_VALIDATION_OK


# ==============================================================================
# 4. Provider Logo / AI Gibberish (Reserved for Phase 3 / 7)
# ==============================================================================
@pytest.mark.xfail(
    strict=True,
    reason="MISSING_CONTRACT: Pre-publication asset quality gate must reject donor watermarks and hallucinated AI text.",
)
def test_provider_logo_or_gibberish_rejected() -> None:
    candidate_asset = load_fixture("assets/asset_provider_logo_gibberish.json")
    meta = candidate_asset["identified_metadata"]

    has_watermark = meta.get("detected_donor_watermark", False)
    gibberish_list = meta.get("detected_ai_gibberish", [])

    is_clean_asset = (not has_watermark) and (len(gibberish_list) == 0)

    assert is_clean_asset, (
        f"RED (Asset Quality Rejection): Detected donor watermark={has_watermark}, "
        f"gibberish text={gibberish_list}."
    )


# ==============================================================================
# 5. Reveal-Only 80%+ Dead Hold (Phase 2: GREEN via SceneSpecValidator structural check)
# ==============================================================================
def test_reveal_only_dead_hold_grammar_rejected() -> None:
    scene_fixture = load_fixture("scenes/scene_reveal_only_dead_hold.json")

    actions = [
        SceneAction(
            action_id="evt_01_reveal",
            action_type="reveal",
            target_id="tactical_vehicle",
            start_ms=0,
            duration_ms=1500,
        )
    ]
    bad_spec = SceneSpecV3(
        project_id="prj_acc_05",
        scene_id=scene_fixture["scene_id"],
        grammar="object_assembly",
        visual_thesis=scene_fixture["visual_thesis"],
        script_snapshot_sha256="1" * 64,
        evidence_pack_sha256="2" * 64,
        grammar_contract=ObjectAssemblyContract(
            parts=("tactical_vehicle",),
            assembly_intent="reposition",
            start_configuration="checkpoint_1",
            end_configuration="checkpoint_2",
        ),
        start_state={"tactical_vehicle": "checkpoint_1"},
        end_state={"tactical_vehicle": "checkpoint_2"},
        duration_ms=10000,
        actions=actions,
    )

    validator = SceneSpecValidator()

    # 1. Structural validation rejects reveal-only action scene
    res = validator.validate(bad_spec)
    assert not res.valid
    assert res.reason_code in (REVEAL_ONLY_ACTION_REJECTED, OBJECT_ASSEMBLY_NO_TRANSFORMATION)

    with pytest.raises(SceneValidationError) as exc_info:
        validator.assert_valid(bad_spec)
    assert exc_info.value.reason_code in (REVEAL_ONLY_ACTION_REJECTED, OBJECT_ASSEMBLY_NO_TRANSFORMATION)

    # 2. Valid purposeful hold or continuous procedural action passes
    valid_spec = SceneSpecV3(
        project_id="prj_acc_05",
        scene_id="SCN_01_VALID_ACTION",
        grammar="object_assembly",
        visual_thesis="Xe đặc nhiệm di chuyển qua các điểm chốt",
        script_snapshot_sha256="1" * 64,
        evidence_pack_sha256="2" * 64,
        grammar_contract=ObjectAssemblyContract(
            parts=("tactical_vehicle",),
            assembly_intent="reposition",
            start_configuration="checkpoint_1",
            end_configuration="checkpoint_2",
        ),
        start_state={"tactical_vehicle": "checkpoint_1"},
        end_state={"tactical_vehicle": "checkpoint_2"},
        duration_ms=5000,
        actions=[
            SceneAction(
                action_id="act_move",
                action_type="move",
                target_id="tactical_vehicle",
                start_ms=500,
                duration_ms=3500,
                params={"to_x": 1200, "to_y": 600},
            )
        ],
    )
    assert validator.validate(valid_spec).valid


# ==============================================================================
# 6. Map Reposition Without Route Continuity (Phase 2: GREEN via SceneSpecValidator)
# ==============================================================================
def test_map_reposition_without_route_continuity_rejected() -> None:
    scene_fixture = load_fixture("scenes/scene_map_reposition_without_route_continuity.json")

    bad_map_spec = SceneSpecV3(
        project_id="prj_acc_06",
        scene_id=scene_fixture["scene_id"],
        grammar="map_route",
        visual_thesis=scene_fixture["visual_thesis"],
        script_snapshot_sha256="1" * 64,
        evidence_pack_sha256="2" * 64,
        grammar_contract=MapRouteContract(
            route_id="r1",
            marker_id="plane_marker",
            declared_polyline=((0.0, 0.0), (10.0, 10.0)),
            coordinate_authority="wgs84_projected",
            uncertainty_policy="none",
        ),
        duration_ms=6000,
        params={"route_spec": scene_fixture["route_spec"]},
        actions=[
            SceneAction(
                action_id="evt_02_teleport",
                action_type="hold",
                target_id="plane_marker",
                start_ms=2000,
                duration_ms=4000,
                params={"motion_type": "instant_teleport_without_path"},
            )
        ],
    )

    validator = SceneSpecValidator()

    # 1. Structural validation rejects disconnected teleportation
    res = validator.validate(bad_map_spec)
    assert not res.valid
    assert res.reason_code == MAP_DISCONTINUOUS_ROUTE

    with pytest.raises(SceneValidationError) as exc_info:
        validator.assert_valid(bad_map_spec)
    assert exc_info.value.reason_code == MAP_DISCONTINUOUS_ROUTE

    # 2. Valid continuous map route passes
    valid_map_spec = SceneSpecV3(
        project_id="prj_acc_06",
        scene_id="SCN_02_VALID_MAP",
        grammar="map_route",
        visual_thesis="Máy bay di chuyển dọc theo lộ trình hải phận quốc tế",
        script_snapshot_sha256="1" * 64,
        evidence_pack_sha256="2" * 64,
        duration_ms=6000,
        grammar_contract=MapRouteContract(
            route_id="r_sea",
            marker_id="plane_marker",
            declared_polyline=((100.0, 200.0), (400.0, 500.0), (800.0, 700.0)),
            coordinate_authority="wgs84_projected",
            uncertainty_policy="none",
        ),
        actions=[
            SceneAction(
                action_id="act_draw",
                action_type="path_draw",
                target_id="r_sea",
                start_ms=0,
                duration_ms=2000,
                params={"route_id": "r_sea"},
            ),
            SceneAction(
                action_id="act_track",
                action_type="traveling_marker",
                target_id="plane_marker",
                start_ms=500,
                duration_ms=4500,
                params={"route_id": "r_sea"},
            ),
        ],
    )
    assert validator.validate(valid_map_spec).valid


# ==============================================================================
# 7. Financial Connectors Without Transfer (Phase 2: GREEN via SceneSpecValidator)
# ==============================================================================
def test_financial_connectors_without_transfer_rejected() -> None:
    scene_fixture = load_fixture("scenes/scene_financial_connectors_without_transfer.json")

    bad_fin_spec = SceneSpecV3(
        project_id="prj_acc_07",
        scene_id=scene_fixture["scene_id"],
        grammar="process_flow",
        visual_thesis=scene_fixture["visual_thesis"],
        script_snapshot_sha256="1" * 64,
        evidence_pack_sha256="2" * 64,
        grammar_contract=ProcessFlowContract(
            nodes=("node_scb", "node_vtp"),
            edges=(("node_scb", "node_vtp"),),
            token_label="Vốn điều lệ",
        ),
        start_state={"node_scb": "has_capital"},
        end_state={"node_vtp": "funds_received"},
        duration_ms=8000,
        params={"process_spec": scene_fixture["process_spec"]},
        actions=[
            SceneAction(
                action_id="evt_01_static_line",
                action_type="reveal",
                target_id="static_line",
                start_ms=1000,
                duration_ms=1000,
            )
        ],
    )

    validator = SceneSpecValidator()

    # 1. Structural validation rejects undirected lines without token transfer
    res = validator.validate(bad_fin_spec)
    assert not res.valid
    assert res.reason_code == PROCESS_FLOW_NO_TRANSFER

    with pytest.raises(SceneValidationError) as exc_info:
        validator.assert_valid(bad_fin_spec)
    assert exc_info.value.reason_code == PROCESS_FLOW_NO_TRANSFER

    # 2. Valid directed transfer passes
    valid_fin_spec = SceneSpecV3(
        project_id="prj_acc_07",
        scene_id="SCN_03_VALID_PROCESS",
        grammar="process_flow",
        visual_thesis="Dòng tiền giải ngân chuyển dịch từ SCB sang VTP",
        script_snapshot_sha256="1" * 64,
        evidence_pack_sha256="2" * 64,
        duration_ms=8000,
        grammar_contract=ProcessFlowContract(
            nodes=("node_scb", "node_vtp"),
            edges=(("node_scb", "node_vtp"),),
            token_label="Vốn giải ngân",
            amount=5000000000000,
            unit="VND",
        ),
        start_state={"node_scb": "has_capital"},
        end_state={"node_vtp": "funds_received"},
        actions=[
            SceneAction(
                action_id="act_transfer",
                action_type="transfer_token",
                target_id="node_vtp",
                source_id="node_scb",
                start_ms=1000,
                duration_ms=4000,
                params={"token_label": "Vốn giải ngân", "amount": 5000000000000, "unit": "VND"},
            )
        ],
    )
    assert validator.validate(valid_fin_spec).valid


# ==============================================================================
# 8. Style Labels Share One Skeleton (Reserved for Phase 6)
# ==============================================================================
@pytest.mark.xfail(
    strict=True,
    reason="MISSING_CONTRACT: Visual language validator must reject styles sharing identical layout skeleton (similarity=1.00 >= 0.30 threshold).",
)
def test_style_labels_share_one_skeleton_rejected() -> None:
    fixture = load_fixture("scenes/scene_styles_shared_skeleton.json")
    similarity = fixture["skeleton_similarity_score"]
    separation_pass = fixture["blind_separation_pass"]

    is_distinct_visual_language = (similarity < 0.30) and separation_pass

    assert is_distinct_visual_language, (
        f"RED (Style Separation Rejection): Declared styles share identical layout skeleton "
        f"with similarity score {similarity:.2f} (max allowed 0.30)."
    )
