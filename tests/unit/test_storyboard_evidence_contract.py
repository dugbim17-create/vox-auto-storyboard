"""Unit tests for Storyboard Evidence Join, Validation, and Truthful Pipeline Boundaries (Phase 1 & 1B)."""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.story_evidence import (
    ClaimSpec,
    EntitySpec,
    SourceRef,
    StoryEvidenceError,
    StoryEvidencePack,
)
from app.schemas.storyboard import validate_storyboard
from app.services.claim_asset_validator import (
    ENTITY_ATTRIBUTE_MISMATCH,
    ClaimAssetValidator,
)
from app.services.script_analysis import join_storyboard_evidence


def make_scene(order: int) -> dict[str, Any]:
    return {
        "scene_id": f"scene_{order:03d}",
        "order": order,
        "script_span": {
            "start_char": (order - 1) * 100,
            "end_char": order * 100,
        },
        "narration_text": f"Narration for scene {order}.",
        "purpose": "hook" if order == 1 else "body",
        "estimated_duration_seconds": 5.0,
        "visual_summary": f"Visual summary of scene {order}.",
        "image_prompt": f"Detailed image prompt for scene {order}.",
        "motion_template": "subject_enter_headline_pop",
        "transition_out": "paper_wipe",
    }


def make_valid_storyboard(scene_count: int = 4, project_id: str = "prj_test_evidence") -> dict[str, Any]:
    return {
        "project_id": project_id,
        "summary": "Documentary investigation series.",
        "target_duration_seconds": 25,
        "style_anchor": {
            "visual_language": "archival documentary",
            "palette": ["off-white", "black", "amber"],
            "texture": ["paper grain", "halftone"],
            "typography": "bold editorial sans",
            "continuity_rules": ["keep amber tint"],
        },
        "characters": [
            {
                "character_id": "char_001",
                "name": "Investigator",
                "description": "Lead investigative journalist.",
            }
        ],
        "locations": [
            {
                "location_id": "loc_001",
                "name": "Archive Room",
                "description": "Historical document archive.",
            }
        ],
        "scenes": [make_scene(i) for i in range(1, scene_count + 1)],
    }


# ==============================================================================
# Tracer 6: Storyboard / Evidence Join Contract
# ==============================================================================
def test_tracer6_storyboard_evidence_join_persists_fields() -> None:
    raw_storyboard = make_valid_storyboard(scene_count=4)
    original_summary = raw_storyboard["summary"]
    original_scenes_count = len(raw_storyboard["scenes"])

    source = SourceRef(publisher="Aviation Safety Network", title="Accident Report", url="https://asn.local")
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
        must_not_invent=["four_engine_aircraft"],
        confidence=1.0,
    )
    evidence_pack = StoryEvidencePack(
        project_id="prj_test_evidence",
        claims=[claim],
    )

    scene_bindings = {
        "scene_001": {
            "evidence_ids": ["C001_MH370"],
            "must_show": ["aircraft_mh370"],
            "must_not_invent": ["four_engine_aircraft"],
            "claim_risk": "high",
            "asset_policy": "source_verified",
        }
    }

    joined = join_storyboard_evidence(
        storyboard=raw_storyboard,
        evidence_pack=evidence_pack,
        scene_bindings=scene_bindings,
    )

    # 1. Verify schema compliance of joined storyboard
    validate_storyboard(joined)

    # 2. Verify evidence persistence on scene_001
    scene1 = next(s for s in joined["scenes"] if s["scene_id"] == "scene_001")
    assert scene1["evidence_ids"] == ["C001_MH370"]
    assert scene1["must_show"] == ["aircraft_mh370"]
    assert scene1["must_not_invent"] == ["four_engine_aircraft"]
    assert scene1["claim_risk"] == "high"
    assert scene1["asset_policy"] == "source_verified"

    # 3. Verify unrelated fields are strictly preserved
    assert joined["summary"] == original_summary
    assert len(joined["scenes"]) == original_scenes_count
    assert joined["style_anchor"] == raw_storyboard["style_anchor"]
    assert joined["characters"] == raw_storyboard["characters"]
    assert joined["locations"] == raw_storyboard["locations"]


# ==============================================================================
# Correction 1 & Phase 1B: Storyboard Join Validation Rules
# ==============================================================================
def test_f4_storyboard_project_id_mismatch_rejected() -> None:
    raw_storyboard = make_valid_storyboard(project_id="prj_STORYBOARD")
    source = SourceRef(publisher="ASN", title="Report", url="https://asn.local")
    claim = ClaimSpec(
        claim_id="C001",
        claim_text="Claim",
        claim_type="confirmed",
        entities=[EntitySpec(entity_id="e1", canonical_name="Ent")],
        sources=[source],
    )
    evidence_pack = StoryEvidencePack(project_id="prj_PACK", claims=[claim])

    with pytest.raises(StoryEvidenceError) as exc_info:
        join_storyboard_evidence(storyboard=raw_storyboard, evidence_pack=evidence_pack)
    assert "PROJECT_ID_MISMATCH" in str(exc_info.value)


def test_f4_storyboard_unknown_evidence_id_rejected() -> None:
    raw_storyboard = make_valid_storyboard(project_id="prj_test")
    source = SourceRef(publisher="ASN", title="Report", url="https://asn.local")
    claim = ClaimSpec(
        claim_id="C001",
        claim_text="Claim",
        claim_type="confirmed",
        entities=[EntitySpec(entity_id="e1", canonical_name="Ent")],
        sources=[source],
    )
    evidence_pack = StoryEvidencePack(project_id="prj_test", claims=[claim])

    bad_bindings = {
        "scene_001": {
            "evidence_ids": ["C999_UNKNOWN"],
        }
    }
    with pytest.raises(StoryEvidenceError) as exc_info:
        join_storyboard_evidence(
            storyboard=raw_storyboard,
            evidence_pack=evidence_pack,
            scene_bindings=bad_bindings,
        )
    assert "UNKNOWN_EVIDENCE_ID" in str(exc_info.value)


def test_f4_storyboard_undeclared_must_show_rejected() -> None:
    raw_storyboard = make_valid_storyboard(project_id="prj_test")
    source = SourceRef(publisher="ASN", title="Report", url="https://asn.local")
    claim = ClaimSpec(
        claim_id="C001",
        claim_text="Claim",
        claim_type="confirmed",
        entities=[EntitySpec(entity_id="e_real", canonical_name="Real Ent")],
        sources=[source],
        must_show=["e_real"],
    )
    evidence_pack = StoryEvidencePack(project_id="prj_test", claims=[claim])

    bad_bindings = {
        "scene_001": {
            "evidence_ids": ["C001"],
            "must_show": ["e_unregistered"],
        }
    }
    with pytest.raises(StoryEvidenceError) as exc_info:
        join_storyboard_evidence(
            storyboard=raw_storyboard,
            evidence_pack=evidence_pack,
            scene_bindings=bad_bindings,
        )
    assert "UNDECLARED_MUST_SHOW" in str(exc_info.value)


def test_f4_join_storyboard_rejects_arbitrary_to_dict_objects() -> None:
    """join_storyboard_evidence rejects arbitrary non-StoryEvidencePack objects."""
    raw_storyboard = make_valid_storyboard(project_id="prj_test")

    class FakeArbitraryObj:
        def to_dict(self) -> dict[str, Any]:
            return {"fake": True}

    with pytest.raises(StoryEvidenceError) as exc_info:
        join_storyboard_evidence(
            storyboard=raw_storyboard,
            evidence_pack=FakeArbitraryObj(),
        )
    assert "INVALID_EVIDENCE_PACK" in str(exc_info.value)


# ==============================================================================
# Tracer 7 & Truthful Pipeline Boundaries
# ==============================================================================
def test_tracer7_truthful_service_seam_blocks_invalid_candidate() -> None:
    """Prove that invalid candidate metadata fails closed through the validator API."""
    source = SourceRef(publisher="ASN", title="Report", url="https://asn.local")
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
    bad_b747_candidate = {
        "asset_id": "asset_b747_bad",
        "identified_metadata": {
            "canonical_name": "Boeing 747-400",
            "family": "747",
            "engine_count": 4,
        },
    }

    validator = ClaimAssetValidator()
    validation_res = validator.validate_candidate(claim=claim, candidate=bad_b747_candidate)
    assert not validation_res.valid
    assert validation_res.reason_code == ENTITY_ATTRIBUTE_MISMATCH
