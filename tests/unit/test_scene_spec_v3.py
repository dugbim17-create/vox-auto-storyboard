"""Unit tests for SceneSpec v3 Schema, Invariants, and Relational Grammar Normalization (Phase 2B Correction 1)."""

from __future__ import annotations

import json

import pytest

from app.schemas.scene_grammar_contracts import (
    CharacterPerformanceContract,
    ChartProgressionContract,
    DocumentEvidenceContract,
    ExplanatoryHoldContract,
    GrammarContractError,
    MapRouteContract,
    ProcessFlowContract,
)
from app.schemas.scene_spec_v3 import (
    SceneSpecV3,
    SceneSpecV3Error,
)


def make_valid_spec_dict() -> dict:
    return {
        "project_id": "prj_001",
        "scene_id": "scene_001",
        "revision": 1,
        "schema_version": "scene_spec/3.0",
        "script_snapshot_sha256": "a" * 64,
        "evidence_pack_sha256": "b" * 64,
        "purpose": "body",
        "grammar": "map_route",
        "visual_thesis": "Visual thesis",
        "duration_ms": 4000,
        "grammar_contract": {
            "route_id": "route_001",
            "marker_id": "marker_1",
            "declared_polyline": [[10.0, 20.0], [30.0, 40.0]],
            "continuous_path": True,
            "coordinate_authority": "wgs84_projected",
            "uncertainty_policy": "none",
        },
        "actions": [
            {"action_id": "act_01", "action_type": "path_draw", "target_id": "route_001", "start_ms": 0, "duration_ms": 1000, "params": {"route_id": "route_001"}},
            {"action_id": "act_02", "action_type": "traveling_marker", "target_id": "marker_1", "start_ms": 500, "duration_ms": 2000, "params": {"route_id": "route_001"}},
        ],
    }


def test_schema_invariants_valid() -> None:
    data = make_valid_spec_dict()
    spec = SceneSpecV3.from_dict(data)
    assert spec.schema_version == "scene_spec/3.0"
    assert spec.revision == 1
    assert isinstance(spec.grammar_contract, MapRouteContract)
    assert spec.grammar_contract.route_id == "route_001"
    assert len(spec.actions) == 2


# ==============================================================================
# F1: Prohibiting Authority Invention Probes
# ==============================================================================
def test_f1_probe_process_flow_flags_only_invention_rejected() -> None:
    """ProcessFlowContract.from_dict(flags only) must NOT invent source_node/target_node or edge."""
    with pytest.raises(GrammarContractError) as exc_info:
        ProcessFlowContract.from_dict({"has_token_transfer": True, "has_direction": True})
    assert "PROCESS_FLOW_NO_TRANSFER" in str(exc_info.value)


def test_f1_probe_character_ready_boolean_invention_rejected() -> None:
    """CharacterPerformanceContract.from_dict(ready=True) must NOT invent puppet_ready capability or acting_intent."""
    with pytest.raises(GrammarContractError) as exc_info:
        CharacterPerformanceContract.from_dict({"ready": True, "puppet_id": "narrator"})
    assert "CHARACTER_PERFORMANCE_NOT_READY" in str(exc_info.value)


def test_f1_probe_document_missing_page_or_section_invention_rejected() -> None:
    """DocumentEvidenceContract.from_dict without page_or_section must NOT invent page_1."""
    with pytest.raises(GrammarContractError) as exc_info:
        DocumentEvidenceContract.from_dict({
            "document_id": "doc_01",
            "focus_region": {"x": 0, "y": 0, "w": 10, "h": 10},
            "citation": "Law 01",
            "display_policy": "overlay",
        })
    assert "DOCUMENT_EVIDENCE_INCOMPLETE" in str(exc_info.value)


def test_f1_probe_chart_missing_domain_invention_rejected() -> None:
    """ChartProgressionContract.from_dict without domain must NOT invent time_domain."""
    with pytest.raises(GrammarContractError) as exc_info:
        ChartProgressionContract.from_dict({
            "series": [10.0, 20.0],
            "units": "VND",
            "source": "Gov",
            "progression_intent": "grow",
        })
    assert "CHART_MISSING_DATA" in str(exc_info.value)


def test_f1_probe_hold_missing_prior_state_change_invention_rejected() -> None:
    """ExplanatoryHoldContract.from_dict without prior_state_change must NOT invent state_transition."""
    with pytest.raises(GrammarContractError) as exc_info:
        ExplanatoryHoldContract.from_dict({
            "declared_purpose": "reading",
            "anchor": "summary",
        })
    assert "EXPLANATORY_HOLD_WITHOUT_PURPOSE" in str(exc_info.value)


# ==============================================================================
# F2 & F4 Invariants
# ==============================================================================
def test_schema_invariants_invalid_version_rejected() -> None:
    data = make_valid_spec_dict()
    data["schema_version"] = "scene_spec/2.0"
    with pytest.raises(SceneSpecV3Error) as exc_info:
        SceneSpecV3.from_dict(data)
    assert "INVALID_SCHEMA_VERSION" in str(exc_info.value)


def test_schema_invariants_invalid_revision_rejected() -> None:
    data = make_valid_spec_dict()
    data["revision"] = 0
    with pytest.raises(SceneSpecV3Error) as exc_info:
        SceneSpecV3.from_dict(data)
    assert "INVALID_REVISION" in str(exc_info.value)


def test_schema_invariants_invalid_fingerprint_rejected() -> None:
    data = make_valid_spec_dict()
    data["planning_fingerprint"] = "not_a_64_hex_string"
    with pytest.raises(SceneSpecV3Error) as exc_info:
        SceneSpecV3.from_dict(data)
    assert "INVALID_FINGERPRINT" in str(exc_info.value)


def test_schema_invariants_decreasing_action_starts_rejected() -> None:
    data = make_valid_spec_dict()
    data["actions"] = [
        {"action_id": "act_01", "action_type": "path_draw", "target_id": "route_001", "start_ms": 1000, "duration_ms": 1000, "params": {"route_id": "route_001"}},
        {"action_id": "act_02", "action_type": "traveling_marker", "target_id": "marker_1", "start_ms": 500, "duration_ms": 2000, "params": {"route_id": "route_001"}},
    ]
    with pytest.raises(SceneSpecV3Error) as exc_info:
        SceneSpecV3.from_dict(data)
    assert "INVALID_ACTION_TIMING" in str(exc_info.value)


def test_schema_invariants_duplicate_evidence_ids_rejected() -> None:
    data = make_valid_spec_dict()
    data["evidence_ids"] = ["EVID_01", "EVID_01"]
    with pytest.raises(SceneSpecV3Error) as exc_info:
        SceneSpecV3.from_dict(data)
    assert "DUPLICATE_COLLECTION_ITEM" in str(exc_info.value)


def test_f2_wrong_contract_type_for_grammar_rejected() -> None:
    """Providing a ProcessFlowContract to a map_route grammar must reject."""
    with pytest.raises(SceneSpecV3Error) as exc_info:
        SceneSpecV3(
            project_id="p",
            scene_id="s",
            grammar="map_route",
            visual_thesis="Thesis",
            script_snapshot_sha256="1" * 64,
            evidence_pack_sha256="2" * 64,
            grammar_contract=ProcessFlowContract(nodes=("A", "B"), edges=(("A", "B"),), token_label="Token"),  # Wrong contract!
            duration_ms=4000,
        )
    assert "INVALID_GRAMMAR_CONTRACT" in str(exc_info.value)


def test_json_roundtrip_contract_parity() -> None:
    data = make_valid_spec_dict()
    spec = SceneSpecV3.from_dict(data)
    serialized = json.dumps(spec.to_dict())
    deserialized_data = json.loads(serialized)
    spec2 = SceneSpecV3.from_dict(deserialized_data)
    assert spec.spec_sha256 == spec2.spec_sha256
    assert isinstance(spec2.grammar_contract, MapRouteContract)
    assert spec2.grammar_contract.route_id == "route_001"
