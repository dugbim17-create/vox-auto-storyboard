"""Unit tests for StoryEvidencePack and ClaimSpec schemas (Phase 1 & Phase 1B Strict Normalization)."""

from __future__ import annotations

import json

import pytest

from app.schemas.story_evidence import (
    ClaimSpec,
    EntitySpec,
    SourceRef,
    StoryEvidenceError,
    StoryEvidencePack,
)


def test_valid_confirmed_claim_schema() -> None:
    entity = EntitySpec(
        entity_id="aircraft_mh370",
        canonical_name="Boeing 777-200ER",
        entity_type="aircraft",
        aliases=["9M-MRO", "MH370"],
        attributes={"family": "777", "variant": "200ER", "engine_count": 2},
    )
    source = SourceRef(
        publisher="Aviation Safety Network",
        url="https://aviation-safety.net/database/record.php?id=20140308-0",
        title="ASN Aircraft accident Boeing 777-200ER 9M-MRO",
    )
    claim = ClaimSpec(
        claim_id="C001",
        claim_text="Chuyến bay MH370 sử dụng máy bay Boeing 777-200ER.",
        claim_type="confirmed",
        entities=[entity],
        sources=[source],
        must_show=["aircraft_mh370"],
        must_not_invent=["four_engine_aircraft"],
        confidence=1.0,
    )
    pack = StoryEvidencePack(
        project_id="prj_test_01",
        claims=[claim],
    )

    assert pack.project_id == "prj_test_01"
    assert len(pack.claims) == 1
    assert pack.get_claim("C001") == claim
    assert pack.get_entity("aircraft_mh370") == entity
    pack.validate_pack()


# ==============================================================================
# Phase 1B / Lead Probe 1 & Mandatory Contract 1: Strict SourceRef
# ==============================================================================
def test_lead_probe1_publisher_only_without_locator_rejected() -> None:
    """Lead Probe 1: Publisher-only source with no URL/locator must reject."""
    with pytest.raises(StoryEvidenceError) as exc_info:
        SourceRef(publisher="Only Publisher", title="", url="")
    assert "MISSING_SOURCE_LOCATOR" in str(exc_info.value) or "INVALID_SOURCE" in str(exc_info.value)


def test_sourceref_empty_or_whitespace_rejected() -> None:
    """Empty or whitespace-only SourceRef values must reject."""
    with pytest.raises(StoryEvidenceError) as exc_info:
        SourceRef(publisher="   ", title="  ", url="   ")
    assert "INVALID_SOURCE" in str(exc_info.value)


def test_sourceref_valid_with_title_and_url_or_path() -> None:
    """SourceRef with title + url or publisher + source_path is valid."""
    s1 = SourceRef(title="Official Report", url="https://example.gov/doc")
    assert s1.title == "Official Report"
    assert s1.url == "https://example.gov/doc"

    s2 = SourceRef(publisher="State Dept", title="Archive #12", source_path="data/sources/doc12.pdf")
    assert s2.source_path == "data/sources/doc12.pdf"


# ==============================================================================
# Phase 1B / Lead Probe 2 & Mandatory Contract 2: Recursive Nested Normalization
# ==============================================================================
def test_lead_probe2_claim_with_empty_nested_source_dict_rejected() -> None:
    """Lead Probe 2: ClaimSpec(..., sources=[{}]) must not bypass SourceRef validation."""
    with pytest.raises(StoryEvidenceError) as exc_info:
        ClaimSpec(
            claim_id="C001",
            claim_text="Confirmed claim with empty source dict",
            claim_type="confirmed",
            entities=[EntitySpec(entity_id="e1", canonical_name="Ent 1")],
            sources=[{}],  # Raw empty dict must be normalized and rejected!
        )
    assert "INVALID_SOURCE" in str(exc_info.value) or "MISSING_SOURCE_LOCATOR" in str(exc_info.value)


def test_claim_with_empty_nested_entity_dict_rejected() -> None:
    """ClaimSpec(..., entities=[{}]) must not bypass EntitySpec validation."""
    source = SourceRef(title="Doc", url="https://doc.local")
    with pytest.raises(StoryEvidenceError) as exc_info:
        ClaimSpec(
            claim_id="C001",
            claim_text="Confirmed claim with empty entity dict",
            claim_type="confirmed",
            entities=[{}],  # Raw empty dict
            sources=[source],
        )
    assert "INVALID_ENTITY" in str(exc_info.value)


def test_pack_with_empty_nested_claim_dict_rejected() -> None:
    """StoryEvidencePack(..., claims=[{}]) must not bypass ClaimSpec validation."""
    with pytest.raises(StoryEvidenceError) as exc_info:
        StoryEvidencePack(project_id="prj_test", claims=[{}])
    assert "INVALID_CLAIM" in str(exc_info.value)


def test_direct_constructor_factory_json_roundtrip_parity() -> None:
    """Parity: direct constructor, from_dict / from_mapping_strict, and JSON roundtrip produce identical objects."""
    source = SourceRef(publisher="ASN", title="Accident Report", url="https://asn.local")
    entity = EntitySpec(
        entity_id="e1",
        canonical_name="Boeing 777-200ER",
        required_candidate_fields=["country", "jurisdiction"],
        attributes={"family": "777", "engine_count": 2},
    )
    claim = ClaimSpec(
        claim_id="C001",
        claim_text="MH370 Boeing 777",
        claim_type="confirmed",
        entities=[entity],
        sources=[source],
        must_show=["e1"],
    )
    pack_direct = StoryEvidencePack(project_id="prj_parity", claims=[claim])

    # Serialized JSON roundtrip
    pack_json_str = json.dumps(pack_direct.to_dict())
    pack_from_json = StoryEvidencePack.from_dict(json.loads(pack_json_str))
    pack_from_mapping = StoryEvidencePack.from_mapping_strict(pack_direct.to_dict())

    assert pack_direct == pack_from_json
    assert pack_direct == pack_from_mapping
    assert all(isinstance(c, ClaimSpec) for c in pack_from_json.claims)
    assert all(isinstance(e, EntitySpec) for c in pack_from_json.claims for e in c.entities)
    assert all(isinstance(s, SourceRef) for c in pack_from_json.claims for s in c.sources)


def test_confirmed_claim_confidence_cannot_substitute_for_source() -> None:
    """F1: Confirmed claim with confidence=1.0 but no sources MUST be rejected."""
    claim = ClaimSpec(
        claim_id="C002",
        claim_text="Tuyên bố quan trọng tự chấm điểm tin cậy cao nhưng thiếu nguồn.",
        claim_type="confirmed",
        entities=[EntitySpec(entity_id="ent_01", canonical_name="Test Entity")],
        sources=[],
        confidence=1.0,
    )
    pack = StoryEvidencePack(project_id="prj_test_02", claims=[claim])

    with pytest.raises(StoryEvidenceError) as exc_info:
        pack.validate_pack()

    assert "MISSING_REQUIRED_EVIDENCE" in str(exc_info.value)
    assert "source" in str(exc_info.value).lower()


def test_pack_structural_invariants_rejected() -> None:
    """F1: project_id, schema_version, confidence bounds, duplicate entity IDs."""
    valid_source = SourceRef(publisher="Official Gazette", title="Decree 12", url="https://gov.vn")
    valid_claim = ClaimSpec(
        claim_id="C001",
        claim_text="Claim text",
        claim_type="confirmed",
        entities=[EntitySpec(entity_id="ent_1", canonical_name="Ent 1")],
        sources=[valid_source],
    )
    with pytest.raises(StoryEvidenceError) as exc_info:
        StoryEvidencePack(project_id="", claims=[valid_claim]).validate_pack()
    assert "INVALID_PROJECT_ID" in str(exc_info.value)

    with pytest.raises(StoryEvidenceError) as exc_info:
        StoryEvidencePack(project_id="prj_test", claims=[]).validate_pack()
    assert "EMPTY_CLAIMS" in str(exc_info.value)

    with pytest.raises(StoryEvidenceError) as exc_info:
        StoryEvidencePack(project_id="prj_test", schema_version="invalid/9.9", claims=[valid_claim]).validate_pack()
    assert "INVALID_SCHEMA_VERSION" in str(exc_info.value)

    with pytest.raises(StoryEvidenceError) as exc_info:
        ClaimSpec(
            claim_id="C002",
            claim_text="Confidence out of range",
            confidence=1.5,
        )
    assert "INVALID_CONFIDENCE" in str(exc_info.value)

    claim_dup = ClaimSpec(
        claim_id="C002",
        claim_text="Duplicate entity",
        claim_type="inferred",
        entities=[EntitySpec(entity_id="ent_1", canonical_name="Duplicate Ent 1")],
    )
    with pytest.raises(StoryEvidenceError) as exc_info:
        StoryEvidencePack(project_id="prj_test", claims=[valid_claim, claim_dup]).validate_pack()
    assert "DUPLICATE_ENTITY_ID" in str(exc_info.value)
