"""Unit tests for SceneSpec fail-closed relational grammar validation rules (Phase 2B Correction 2 Final)."""

from __future__ import annotations

from app.schemas.scene_grammar_contracts import (
    CharacterPerformanceContract,
    ChartProgressionContract,
    DocumentEvidenceContract,
    ExplanatoryHoldContract,
    MapRouteContract,
    ObjectAssemblyContract,
    ProcessFlowContract,
)
from app.schemas.scene_spec_v3 import SceneAction, SceneSpecV3
from app.services.scene_spec_validator import (
    CHARACTER_PERFORMANCE_NOT_READY,
    CHART_MISSING_DATA,
    DOCUMENT_EVIDENCE_INCOMPLETE,
    EXPLANATORY_HOLD_WITHOUT_PURPOSE,
    MAP_ROUTE_BINDING_MISMATCH,
    PROCESS_FLOW_NO_TRANSFER,
    SceneSpecValidator,
)


# ==============================================================================
# Fresh Lead Probes (Correction 2 Final)
# ==============================================================================
def test_lead_probe1_map_marker_id_target_mismatch_rejected() -> None:
    """Probe 1: map contract marker_id=EXPECTED, action target=WRONG -> rejects MAP_ROUTE_BINDING_MISMATCH."""
    validator = SceneSpecValidator()
    spec = SceneSpecV3(
        project_id="p", scene_id="s1", grammar="map_route", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=MapRouteContract(
            route_id="route_A", marker_id="marker_EXPECTED",
            declared_polyline=((0.0, 0.0), (10.0, 10.0)),
            coordinate_authority="wgs84_projected", uncertainty_policy="none",
        ),
        actions=[
            SceneAction(action_id="a1", action_type="path_draw", target_id="route_A", start_ms=0, duration_ms=1000, params={"route_id": "route_A"}),
            # target_id is WRONG instead of marker_EXPECTED!
            SceneAction(action_id="a2", action_type="traveling_marker", target_id="marker_WRONG", start_ms=500, duration_ms=2000, params={"route_id": "route_A"}),
        ],
        duration_ms=4000,
    )
    res = validator.validate(spec)
    assert not res.valid
    assert res.reason_code == MAP_ROUTE_BINDING_MISMATCH


def test_lead_probe2_process_transfer_action_lacks_token_payload_rejected() -> None:
    """Probe 2: process contract token/amount/unit, transfer action carries none -> rejects PROCESS_FLOW_NO_TRANSFER."""
    validator = SceneSpecValidator()
    spec = SceneSpecV3(
        project_id="p", scene_id="s2", grammar="process_flow", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=ProcessFlowContract(
            nodes=("bank_A", "bank_B"), edges=(("bank_A", "bank_B"),),
            token_label="Vốn điều lệ", amount=1000, unit="VND",
        ),
        actions=[
            # transfer_token has empty params, missing token_label and amount!
            SceneAction(action_id="a1", action_type="transfer_token", target_id="bank_B", source_id="bank_A", start_ms=0, duration_ms=2000, params={}),
        ],
        start_state={"bank_A": "has_capital"}, end_state={"bank_B": "received_capital"},
        duration_ms=4000,
    )
    res = validator.validate(spec)
    assert not res.valid
    assert res.reason_code == PROCESS_FLOW_NO_TRANSFER


def test_lead_probe3_character_poses_differ_but_lifecycle_unchanged_rejected() -> None:
    """Probe 3: character contract poses differ, SceneSpec lifecycle unchanged/disagrees -> rejects CHARACTER_PERFORMANCE_NOT_READY."""
    validator = SceneSpecValidator()
    spec = SceneSpecV3(
        project_id="p", scene_id="s3", grammar="character_performance", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=CharacterPerformanceContract(
            performer_id="narrator_01", capabilities=("head_turn",), acting_intent="explain",
            start_pose="speaking_idle", end_pose="pointing_board",
        ),
        actions=[
            SceneAction(action_id="a1", action_type="pose_sequence", target_id="narrator_01", start_ms=0, duration_ms=2000),
        ],
        # SceneSpec lifecycle unchanged for performer!
        start_state={"narrator_01": "neutral"}, end_state={"narrator_01": "neutral"},
        duration_ms=4000,
    )
    res = validator.validate(spec)
    assert not res.valid
    assert res.reason_code == CHARACTER_PERFORMANCE_NOT_READY


def test_lead_probe4_document_action_lacks_focus_binding_rejected() -> None:
    """Probe 4: document action lacks focus/page identity binding -> rejects DOCUMENT_EVIDENCE_INCOMPLETE."""
    validator = SceneSpecValidator()
    # 1. Missing page and focus
    spec1 = SceneSpecV3(
        project_id="p", scene_id="s4_1", grammar="document_evidence", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_01"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_01", page_or_section="page_5",
            focus_region={"x": 10, "y": 20, "w": 50, "h": 50}, citation="Law 12",
            display_policy="overlay",
        ),
        actions=[
            # Action has empty params (missing page and focus!)
            SceneAction(action_id="a1", action_type="document_focus", target_id="doc_01", start_ms=0, duration_ms=1000, params={}),
        ],
        duration_ms=4000,
    )
    res1 = validator.validate(spec1)
    assert not res1.valid
    assert res1.reason_code == DOCUMENT_EVIDENCE_INCOMPLETE

    # 2. Missing page only
    spec2 = SceneSpecV3(
        project_id="p", scene_id="s4_2", grammar="document_evidence", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_01"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_01", page_or_section="page_5",
            focus_region={"x": 10, "y": 20, "w": 50, "h": 50}, citation="Law 12",
            display_policy="overlay",
        ),
        actions=[
            # Has focus_region but missing page_or_section!
            SceneAction(action_id="a1", action_type="document_focus", target_id="doc_01", start_ms=0, duration_ms=1000, params={"focus_region": {"x": 10, "y": 20, "w": 50, "h": 50}}),
        ],
        duration_ms=4000,
    )
    res2 = validator.validate(spec2)
    assert not res2.valid
    assert res2.reason_code == DOCUMENT_EVIDENCE_INCOMPLETE

    # 3. Missing focus only
    spec3 = SceneSpecV3(
        project_id="p", scene_id="s4_3", grammar="document_evidence", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_01"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_01", page_or_section="page_5",
            focus_region={"x": 10, "y": 20, "w": 50, "h": 50}, citation="Law 12",
            display_policy="overlay",
        ),
        actions=[
            # Has page_or_section but missing focus_region!
            SceneAction(action_id="a1", action_type="document_focus", target_id="doc_01", start_ms=0, duration_ms=1000, params={"page_or_section": "page_5"}),
        ],
        duration_ms=4000,
    )
    res3 = validator.validate(spec3)
    assert not res3.valid
    assert res3.reason_code == DOCUMENT_EVIDENCE_INCOMPLETE

    # 4. Wrong page
    spec4 = SceneSpecV3(
        project_id="p", scene_id="s4_4", grammar="document_evidence", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_01"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_01", page_or_section="page_5",
            focus_region={"x": 10, "y": 20, "w": 50, "h": 50}, citation="Law 12",
            display_policy="overlay",
        ),
        actions=[
            # Contradictory page_or_section!
            SceneAction(action_id="a1", action_type="document_focus", target_id="doc_01", start_ms=0, duration_ms=1000, params={"page_or_section": "page_99", "focus_region": {"x": 10, "y": 20, "w": 50, "h": 50}}),
        ],
        duration_ms=4000,
    )
    res4 = validator.validate(spec4)
    assert not res4.valid
    assert res4.reason_code == DOCUMENT_EVIDENCE_INCOMPLETE

    # 5. Wrong focus
    spec5 = SceneSpecV3(
        project_id="p", scene_id="s4_5", grammar="document_evidence", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_01"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_01", page_or_section="page_5",
            focus_region={"x": 10, "y": 20, "w": 50, "h": 50}, citation="Law 12",
            display_policy="overlay",
        ),
        actions=[
            # Contradictory focus_region!
            SceneAction(action_id="a1", action_type="document_focus", target_id="doc_01", start_ms=0, duration_ms=1000, params={"page_or_section": "page_5", "focus_region": {"x": 99, "y": 99, "w": 1, "h": 1}}),
        ],
        duration_ms=4000,
    )
    res5 = validator.validate(spec5)
    assert not res5.valid
    assert res5.reason_code == DOCUMENT_EVIDENCE_INCOMPLETE

    # 6. Exact document + page + focus -> passes
    spec6 = SceneSpecV3(
        project_id="p", scene_id="s4_6", grammar="document_evidence", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_01"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_01", page_or_section="page_5",
            focus_region={"x": 10, "y": 20, "w": 50, "h": 50}, citation="Law 12",
            display_policy="overlay",
        ),
        actions=[
            # Exact match!
            SceneAction(action_id="a1", action_type="document_focus", target_id="doc_01", start_ms=0, duration_ms=1000, params={"page_or_section": "page_5", "focus_region": {"x": 10, "y": 20, "w": 50, "h": 50}}),
        ],
        duration_ms=4000,
    )
    assert validator.validate(spec6).valid


def test_lead_probe5_chart_source_not_in_evidence_or_wrong_series_rejected() -> None:
    """Probe 5: chart source not in evidence and action targets wrong series -> rejects CHART_MISSING_DATA."""
    validator = SceneSpecValidator()
    spec = SceneSpecV3(
        project_id="p", scene_id="s5", grammar="chart_progression", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["EVID_FINANCE_01"],  # SBV is NOT in evidence_ids!
        grammar_contract=ChartProgressionContract(
            domain="years", series_id="gdp_growth", series=(10.0, 20.0),
            units="VND", source="UNBOUND_SOURCE", progression_intent="grow",
        ),
        actions=[
            # Action targets wrong series!
            SceneAction(action_id="a1", action_type="chart_series", target_id="wrong_series", start_ms=0, duration_ms=1000),
        ],
        duration_ms=4000,
    )
    res = validator.validate(spec)
    assert not res.valid
    assert res.reason_code == CHART_MISSING_DATA


def test_lead_probe6_hold_prior_state_change_with_no_real_action_or_state_rejected() -> None:
    """Probe 6: hold prior_state_change with no real action/state -> rejects EXPLANATORY_HOLD_WITHOUT_PURPOSE."""
    validator = SceneSpecValidator()
    spec = SceneSpecV3(
        project_id="p", scene_id="s6", grammar="explanatory_hold", visual_thesis="Thesis",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=ExplanatoryHoldContract(
            declared_purpose="reading", prior_state_change="nonexistent_action_id",
            anchor="summary_point",
        ),
        narration_anchors=[{"anchor": "summary_point", "at_ms": 1000}],
        actions=[],
        start_state={}, end_state={},
        duration_ms=4000,
    )
    res = validator.validate(spec)
    assert not res.valid
    assert res.reason_code == EXPLANATORY_HOLD_WITHOUT_PURPOSE


# ==============================================================================
# Complete Valid Specimens for All 7 Grammar Families
# ==============================================================================
def test_valid_specimens_for_all_seven_grammars() -> None:
    validator = SceneSpecValidator()

    # 1. Map Route
    spec_map = SceneSpecV3(
        project_id="p", scene_id="s_map", grammar="map_route", visual_thesis="Lộ trình bay",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=MapRouteContract(
            route_id="route_A", marker_id="plane_marker", declared_polyline=((0.0, 0.0), (100.0, 100.0)),
            coordinate_authority="wgs84_projected", uncertainty_policy="none",
        ),
        actions=[
            SceneAction(action_id="a1", action_type="path_draw", target_id="route_A", start_ms=0, duration_ms=1000, params={"route_id": "route_A"}),
            SceneAction(action_id="a2", action_type="traveling_marker", target_id="plane_marker", start_ms=500, duration_ms=2000, params={"route_id": "route_A"}),
        ],
        duration_ms=4000,
    )
    assert validator.validate(spec_map).valid

    # 2. Process Flow
    spec_proc = SceneSpecV3(
        project_id="p", scene_id="s_proc", grammar="process_flow", visual_thesis="Dòng tiền",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=ProcessFlowContract(
            nodes=("bank_A", "bank_B"), edges=(("bank_A", "bank_B"),),
            token_label="Vốn điều lệ", amount=5000, unit="VND",
        ),
        actions=[
            SceneAction(
                action_id="a1", action_type="transfer_token", target_id="bank_B", source_id="bank_A",
                start_ms=0, duration_ms=2000,
                params={"token_label": "Vốn điều lệ", "amount": 5000, "unit": "VND"},
            ),
        ],
        start_state={"bank_A": "has_capital"}, end_state={"bank_B": "capital_received"},
        duration_ms=4000,
    )
    assert validator.validate(spec_proc).valid

    # 3. Object Assembly
    spec_obj = SceneSpecV3(
        project_id="p", scene_id="s_obj", grammar="object_assembly", visual_thesis="Lắp ráp",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=ObjectAssemblyContract(parts=("chassis", "wheel"), assembly_intent="assemble", start_configuration="raw", end_configuration="done"),
        actions=[
            SceneAction(action_id="a1", action_type="transform", target_id="wheel", start_ms=0, duration_ms=2000),
        ],
        start_state={"wheel": "detached"}, end_state={"wheel": "assembled"},
        duration_ms=4000,
    )
    assert validator.validate(spec_obj).valid

    # 4. Character Performance
    spec_char = SceneSpecV3(
        project_id="p", scene_id="s_char", grammar="character_performance", visual_thesis="Thuyết minh",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=CharacterPerformanceContract(
            performer_id="narrator_01", capabilities=("head_turn", "point"),
            acting_intent="explain_evidence", start_pose="idle", end_pose="pointing",
        ),
        actions=[
            SceneAction(action_id="a1", action_type="pose_sequence", target_id="narrator_01", start_ms=0, duration_ms=2000),
        ],
        start_state={"narrator_01": "idle"}, end_state={"narrator_01": "pointing"},
        duration_ms=4000,
    )
    assert validator.validate(spec_char).valid

    # 5. Document Evidence
    spec_doc = SceneSpecV3(
        project_id="p", scene_id="s_doc", grammar="document_evidence", visual_thesis="Tài liệu",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["doc_verdict"],
        grammar_contract=DocumentEvidenceContract(
            document_id="doc_verdict", page_or_section="page_1",
            focus_region={"x": 10, "y": 20, "w": 100, "h": 50}, citation="Decree 12", display_policy="overlay",
        ),
        actions=[
            SceneAction(
                action_id="a1", action_type="document_focus", target_id="doc_verdict", start_ms=0, duration_ms=2000,
                params={"page_or_section": "page_1", "focus_region": {"x": 10, "y": 20, "w": 100, "h": 50}},
            ),
        ],
        duration_ms=4000,
    )
    assert validator.validate(spec_doc).valid

    # 6. Chart Progression
    spec_chart = SceneSpecV3(
        project_id="p", scene_id="s_chart", grammar="chart_progression", visual_thesis="Biểu đồ",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        evidence_ids=["SBV_REPORT"],
        grammar_contract=ChartProgressionContract(
            domain="years", series_id="main_series", series=(10.5, 20.2, 35.8),
            units="VND", source="SBV_REPORT", progression_intent="growth",
        ),
        actions=[
            SceneAction(action_id="a1", action_type="chart_series", target_id="main_series", start_ms=0, duration_ms=2000),
        ],
        duration_ms=4000,
    )
    assert validator.validate(spec_chart).valid

    # 7. Explanatory Hold
    spec_hold = SceneSpecV3(
        project_id="p", scene_id="s_hold", grammar="explanatory_hold", visual_thesis="Bảng ghim",
        script_snapshot_sha256="1" * 64, evidence_pack_sha256="2" * 64,
        grammar_contract=ExplanatoryHoldContract(
            declared_purpose="read_summary", prior_state_change="board", anchor="tóm lại",
        ),
        hold_policy={"declared_purpose": "read_summary", "max_duration_ms": 4000},
        narration_anchors=[{"anchor": "tóm lại", "at_ms": 1000}],
        start_state={"board": "empty"}, end_state={"board": "pinned"},
        duration_ms=4000,
    )
    assert validator.validate(spec_hold).valid
