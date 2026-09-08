"""Unit tests for ClaimAssetValidator real production API (Phase 1 & Phase 1B Strict Contracts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas.story_evidence import ClaimSpec, EntitySpec, SourceRef
from app.services.claim_asset_validator import (
    ENTITY_ATTRIBUTE_MISMATCH,
    FORBIDDEN_PLACEHOLDER,
    INSTITUTION_JURISDICTION_MISMATCH,
    LOCALE_MISMATCH,
    MISSING_CANDIDATE_IDENTITY,
    VALIDATION_OK,
    ClaimAssetValidator,
    ClaimValidationError,
    ValidationResult,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "vox_v3"


def load_fixture(rel_path: str) -> dict[str, Any]:
    with open(FIXTURES_DIR / rel_path, encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# Phase 1B / Lead Probe 3: Entity requiring jurisdiction & country fails closed
# ==============================================================================
def test_lead_probe3_candidate_missing_jurisdiction_rejected() -> None:
    """Lead Probe 3: Entity requiring jurisdiction=VN & country=Vietnam rejected when candidate has country only."""
    entity = EntitySpec(
        entity_id="inst_scb",
        canonical_name="Saigon Commercial Bank",
        country="Vietnam",
        jurisdiction="VN",
        required_candidate_fields=["country", "jurisdiction"],
    )
    source = SourceRef(title="Official Registry", url="https://sbv.gov.vn")
    claim = ClaimSpec(
        claim_id="C002",
        claim_text="SCB VN institution",
        claim_type="confirmed",
        entities=[entity],
        sources=[source],
    )

    validator = ClaimAssetValidator()

    # Candidate provides country="Vietnam" but completely omits jurisdiction
    candidate_country_only = {
        "asset_id": "a_scb_incomplete",
        "identified_metadata": {
            "canonical_name": "Saigon Commercial Bank",
            "country": "Vietnam",
            # missing jurisdiction="VN"
        },
    }
    result = validator.validate_candidate(claim=claim, candidate=candidate_country_only)
    assert not result.valid
    assert result.reason_code == MISSING_CANDIDATE_IDENTITY
    assert "jurisdiction" in result.message


def test_candidate_missing_country_rejected() -> None:
    """Entity requiring country and jurisdiction rejected when candidate has jurisdiction only."""
    entity = EntitySpec(
        entity_id="inst_scb",
        canonical_name="Saigon Commercial Bank",
        country="Vietnam",
        jurisdiction="VN",
        required_candidate_fields=["country", "jurisdiction"],
    )
    source = SourceRef(title="Official Registry", url="https://sbv.gov.vn")
    claim = ClaimSpec(
        claim_id="C002",
        claim_text="SCB VN institution",
        claim_type="confirmed",
        entities=[entity],
        sources=[source],
    )
    validator = ClaimAssetValidator()

    candidate_jurisdiction_only = {
        "asset_id": "a_scb_incomplete2",
        "identified_metadata": {
            "canonical_name": "Saigon Commercial Bank",
            "jurisdiction": "VN",
            # missing country="Vietnam"
        },
    }
    result = validator.validate_candidate(claim=claim, candidate=candidate_jurisdiction_only)
    assert not result.valid
    assert result.reason_code == MISSING_CANDIDATE_IDENTITY
    assert "country" in result.message


def test_alias_match_cannot_waive_required_disambiguators() -> None:
    """Candidate matching alias but missing required disambiguating fields must reject."""
    entity = EntitySpec(
        entity_id="inst_scb",
        canonical_name="Saigon Commercial Bank",
        aliases=["SCB"],
        country="Vietnam",
        jurisdiction="VN",
        required_candidate_fields=["country", "jurisdiction"],
    )
    source = SourceRef(title="Official Registry", url="https://sbv.gov.vn")
    claim = ClaimSpec(
        claim_id="C002",
        claim_text="SCB VN institution",
        claim_type="confirmed",
        entities=[entity],
        sources=[source],
    )
    validator = ClaimAssetValidator()

    # Candidate uses alias 'SCB' with no country or jurisdiction
    alias_cand = {
        "asset_id": "a_alias_only",
        "identified_metadata": {"canonical_name": "SCB"},
    }
    result = validator.validate_candidate(claim=claim, candidate=alias_cand)
    assert not result.valid
    assert result.reason_code == MISSING_CANDIDATE_IDENTITY


def test_typed_claim_only_accepted_by_validator() -> None:
    """ClaimAssetValidator rejects untyped mappings for claim parameter."""
    validator = ClaimAssetValidator()
    with pytest.raises(TypeError) as exc_info:
        validator.validate_candidate(claim={"claim_id": "C1"}, candidate={})  # type: ignore[arg-type]
    assert "ClaimSpec" in str(exc_info.value)


# ==============================================================================
# Tracer 2: MH370 Aircraft Validation
# ==============================================================================
def test_tracer2_mh370_candidate_rejected_via_validator_api() -> None:
    claim_dict = load_fixture("claims/claim_mh370.json")
    claim = ClaimSpec.from_dict(claim_dict)
    bad_asset_dict = load_fixture("assets/asset_mh370_b747_mismatch.json")

    validator = ClaimAssetValidator()
    result = validator.validate_candidate(claim=claim, candidate=bad_asset_dict)

    assert isinstance(result, ValidationResult)
    assert not result.valid
    assert result.reason_code == ENTITY_ATTRIBUTE_MISMATCH
    assert "Boeing 747" in result.message or "747" in result.message

    with pytest.raises(ClaimValidationError) as exc_info:
        validator.assert_valid_candidate(claim=claim, candidate=bad_asset_dict)
    assert exc_info.value.reason_code == ENTITY_ATTRIBUTE_MISMATCH


# ==============================================================================
# Tracer 3: SCB Institution / Jurisdiction Validation
# ==============================================================================
def test_tracer3_scb_thailand_rejected_despite_shared_alias() -> None:
    claim_dict = load_fixture("claims/claim_scb_vn.json")
    claim = ClaimSpec.from_dict(claim_dict)
    bad_scb_dict = load_fixture("assets/asset_scb_thailand_mismatch.json")

    validator = ClaimAssetValidator()
    result = validator.validate_candidate(claim=claim, candidate=bad_scb_dict)

    assert not result.valid
    assert result.reason_code == INSTITUTION_JURISDICTION_MISMATCH
    assert "Thailand" in result.message or "TH" in result.message

    with pytest.raises(ClaimValidationError) as exc_info:
        validator.assert_valid_candidate(claim=claim, candidate=bad_scb_dict)
    assert exc_info.value.reason_code == INSTITUTION_JURISDICTION_MISMATCH


# ==============================================================================
# Tracer 4: True Crime US Placeholder in VN Case
# ==============================================================================
def test_tracer4_us_placeholder_rejected_for_vn_case() -> None:
    claim_dict = load_fixture("claims/claim_true_crime_vn.json")
    claim = ClaimSpec.from_dict(claim_dict)
    bad_placeholder_dict = load_fixture("assets/asset_true_crime_us_placeholder.json")

    validator = ClaimAssetValidator()
    result = validator.validate_candidate(claim=claim, candidate=bad_placeholder_dict)

    assert not result.valid
    assert result.reason_code in (FORBIDDEN_PLACEHOLDER, LOCALE_MISMATCH)

    with pytest.raises(ClaimValidationError) as exc_info:
        validator.assert_valid_candidate(claim=claim, candidate=bad_placeholder_dict)
    assert exc_info.value.reason_code in (FORBIDDEN_PLACEHOLDER, LOCALE_MISMATCH)


# ==============================================================================
# Tracer 5: Valid Exact Assets Accepted for all Three Classes
# ==============================================================================
def test_tracer5_valid_exact_assets_accepted() -> None:
    validator = ClaimAssetValidator()

    # 1. Valid MH370 B777 asset
    claim1 = ClaimSpec.from_dict(load_fixture("claims/claim_mh370.json"))
    valid_b777_candidate = {
        "asset_id": "asset_b777_exact",
        "file_path": "tests/fixtures/vox_v3/assets/asset_b777_exact.png",
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
    res1 = validator.validate_candidate(claim=claim1, candidate=valid_b777_candidate)
    assert res1.valid
    assert res1.reason_code == VALIDATION_OK
    validator.assert_valid_candidate(claim=claim1, candidate=valid_b777_candidate)

    # 2. Valid SCB Vietnam asset
    claim2 = ClaimSpec.from_dict(load_fixture("claims/claim_scb_vn.json"))
    valid_scb_candidate = {
        "asset_id": "asset_scb_vn_exact",
        "file_path": "tests/fixtures/vox_v3/assets/asset_scb_vn_exact.png",
        "identified_metadata": {
            "canonical_name": "Saigon Commercial Bank",
            "vietnamese_name": "Ngân hàng Thương mại Cổ phần Sài Gòn",
            "jurisdiction": "VN",
            "country": "Vietnam",
            "ticker_alias": "SCB",
            "headquarters": "TP. Hồ Chí Minh, Việt Nam",
        },
    }
    res2 = validator.validate_candidate(claim=claim2, candidate=valid_scb_candidate)
    assert res2.valid
    assert res2.reason_code == VALIDATION_OK
    validator.assert_valid_candidate(claim=claim2, candidate=valid_scb_candidate)

    # 3. Valid VN Documentary Casefile asset
    claim3 = ClaimSpec.from_dict(load_fixture("claims/claim_true_crime_vn.json"))
    valid_tc_candidate = {
        "asset_id": "asset_tc_vn_exact",
        "intended_entity_id": "doc_casefile_vn",
        "file_path": "tests/fixtures/vox_v3/assets/asset_tc_vn_exact.png",
        "identified_metadata": {
            "canonical_name": "Hồ sơ vụ án hình sự Việt Nam",
            "country": "Vietnam",
            "locale": "vi-VN",
            "detected_placeholders": [],
        },
    }
    res3 = validator.validate_candidate(claim=claim3, candidate=valid_tc_candidate)
    assert res3.valid
    assert res3.reason_code == VALIDATION_OK
    validator.assert_valid_candidate(claim=claim3, candidate=valid_tc_candidate)
