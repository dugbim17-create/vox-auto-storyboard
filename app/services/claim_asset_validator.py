"""ClaimAssetValidator service for fail-closed factual entity and asset verification (Phase 1 & Phase 1B).

Validates candidate asset metadata against StoryEvidencePack claims and EntitySpecs before
asset selection, materialization, or publication:
- Strict typed-only input: requires ClaimSpec instance.
- Explicit required candidate fields & attributes enforcement (fail closed if missing).
- Multi-entity disambiguation: no silent first-entity fallback; ambiguous bindings reject.
- Institution jurisdiction & country validation (e.g. SCB VN vs SCB TH).
- Locale and forbidden placeholder detection (e.g. US J. Doe police files in VN cases).
- Deterministic failure reason precedence:
  1. FORBIDDEN_PLACEHOLDER
  2. MISSING_CANDIDATE_IDENTITY (missing canonical name)
  3. INSTITUTION_JURISDICTION_MISMATCH (forbidden alias, country/jurisdiction mismatch)
  4. LOCALE_MISMATCH (locale mismatch)
  5. ENTITY_ATTRIBUTE_MISMATCH (present attribute value mismatch)
  6. MISSING_CANDIDATE_IDENTITY (missing required fields / missing required attributes)
  7. ENTITY_CANONICAL_MISMATCH (canonical name not matched)
  8. VALIDATION_OK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.story_evidence import ClaimSpec, EntitySpec

# Stable Machine-Readable Reason Codes
ENTITY_CANONICAL_MISMATCH = "ENTITY_CANONICAL_MISMATCH"
ENTITY_ATTRIBUTE_MISMATCH = "ENTITY_ATTRIBUTE_MISMATCH"
INSTITUTION_JURISDICTION_MISMATCH = "INSTITUTION_JURISDICTION_MISMATCH"
LOCALE_MISMATCH = "LOCALE_MISMATCH"
FORBIDDEN_PLACEHOLDER = "FORBIDDEN_PLACEHOLDER"
MISSING_REQUIRED_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
MISSING_CANDIDATE_IDENTITY = "MISSING_CANDIDATE_IDENTITY"
AMBIGUOUS_ENTITY_BINDING = "AMBIGUOUS_ENTITY_BINDING"
VALIDATION_OK = "VALIDATION_OK"


class ClaimValidationError(ValueError):
    """Raised when an asset candidate fails factual claim validation."""

    def __init__(
        self,
        message: str,
        reason_code: str = ENTITY_CANONICAL_MISMATCH,
        entity_id: str | None = None,
        claim_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message
        self.entity_id = entity_id
        self.claim_id = claim_id
        self.details = details or {}


@dataclass(frozen=True)
class ValidationResult:
    """Structured result of a candidate validation check."""

    valid: bool
    reason_code: str
    message: str
    entity_id: str | None = None
    claim_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ClaimAssetValidator:
    """Validator that checks candidate assets against factual evidence contracts."""

    def validate_candidate(
        self,
        *,
        claim: ClaimSpec,
        candidate: dict[str, Any],
        target_entity_id: str | None = None,
    ) -> ValidationResult:
        """Validate an asset candidate against a claim's entities.

        Args:
            claim: The ClaimSpec containing required entities and constraints (typed only).
            candidate: Dict representation of AssetSpec or candidate metadata.
            target_entity_id: Optional specific entity_id to target.
        """
        if not isinstance(claim, ClaimSpec):
            raise TypeError(f"ClaimAssetValidator requires a ClaimSpec instance, got {type(claim).__name__}")

        if not claim.entities:
            return ValidationResult(
                valid=False,
                reason_code=MISSING_REQUIRED_EVIDENCE,
                message=f"Claim '{claim.claim_id}' has no declared entities to validate against.",
                claim_id=claim.claim_id,
            )

        meta = candidate.get("identified_metadata") or candidate.get("metadata") or candidate

        # Disambiguate target entity without silent first-entity fallback
        entity: EntitySpec | None = None
        if target_entity_id:
            entity = claim.get_entity(target_entity_id)
            if not entity:
                return ValidationResult(
                    valid=False,
                    reason_code=MISSING_REQUIRED_EVIDENCE,
                    message=f"Target entity '{target_entity_id}' not found in claim '{claim.claim_id}'.",
                    claim_id=claim.claim_id,
                    entity_id=target_entity_id,
                )
        else:
            # 1. Match by explicit candidate entity binding
            cand_ent_id = candidate.get("intended_entity_id") or candidate.get("entity_id") or meta.get("entity_id")
            if cand_ent_id:
                entity = claim.get_entity(str(cand_ent_id))

            # 2. Match by canonical name or unique alias
            if not entity:
                cand_name = str(meta.get("canonical_name") or meta.get("name") or "").strip().lower()
                if cand_name:
                    matches = [
                        e for e in claim.entities
                        if e.canonical_name.lower() == cand_name or any(a.lower() == cand_name for a in e.aliases)
                    ]
                    if len(matches) == 1:
                        entity = matches[0]
                    elif len(matches) > 1:
                        return ValidationResult(
                            valid=False,
                            reason_code=AMBIGUOUS_ENTITY_BINDING,
                            message=f"Ambiguous candidate binding: candidate name '{cand_name}' matches multiple entities {[e.entity_id for e in matches]} in claim '{claim.claim_id}'.",
                            claim_id=claim.claim_id,
                        )

            # 3. Match by entity with matching forbidden placeholders
            if not entity:
                detected_placeholders = {str(p).upper() for p in (meta.get("detected_placeholders") or [])}
                if detected_placeholders:
                    matching_entities = []
                    for e in claim.entities:
                        e_forb = {str(fp).upper() for fp in e.forbidden_placeholders}
                        if e_forb.intersection(detected_placeholders):
                            matching_entities.append(e)
                    if len(matching_entities) == 1:
                        entity = matching_entities[0]

            # 4. If only 1 entity in claim, bind to it
            if not entity and len(claim.entities) == 1:
                entity = claim.entities[0]

            # 5. Multi-entity claim with no clear binding must fail closed
            if not entity:
                return ValidationResult(
                    valid=False,
                    reason_code=AMBIGUOUS_ENTITY_BINDING,
                    message=f"Multi-entity claim '{claim.claim_id}' requires explicit target_entity_id or unique canonical match among {[e.entity_id for e in claim.entities]}.",
                    claim_id=claim.claim_id,
                )

        return self.validate_entity_binding(entity=entity, candidate_meta=meta, claim_id=claim.claim_id)

    def assert_valid_candidate(
        self,
        *,
        claim: ClaimSpec,
        candidate: dict[str, Any],
        target_entity_id: str | None = None,
    ) -> ValidationResult:
        """Validate candidate and raise ClaimValidationError if invalid."""
        res = self.validate_candidate(
            claim=claim, candidate=candidate, target_entity_id=target_entity_id
        )
        if not res.valid:
            raise ClaimValidationError(
                message=res.message,
                reason_code=res.reason_code,
                entity_id=res.entity_id,
                claim_id=res.claim_id,
                details=res.details,
            )
        return res

    def validate_entity_binding(
        self,
        *,
        entity: EntitySpec,
        candidate_meta: dict[str, Any],
        claim_id: str | None = None,
    ) -> ValidationResult:
        """Validate candidate metadata against an EntitySpec using deterministic precedence."""
        cand_name = str(candidate_meta.get("canonical_name") or candidate_meta.get("name") or "").strip()
        cand_country = candidate_meta.get("country")
        cand_jurisdiction = candidate_meta.get("jurisdiction")
        cand_locale = candidate_meta.get("locale")
        detected_placeholders = {str(p).upper() for p in (candidate_meta.get("detected_placeholders") or [])}

        cand_attrs = dict(candidate_meta.get("attributes") or {})
        for k, v in candidate_meta.items():
            if k not in cand_attrs and k not in {"canonical_name", "name", "country", "jurisdiction", "locale", "detected_placeholders"}:
                cand_attrs[k] = v

        # ---------------------------------------------------------------------
        # Precedence 1: Check FORBIDDEN_PLACEHOLDER
        # ---------------------------------------------------------------------
        forb_placeholders = {str(p).upper() for p in entity.forbidden_placeholders}
        if forb_placeholders and detected_placeholders:
            intersection = forb_placeholders.intersection(detected_placeholders)
            if intersection:
                return ValidationResult(
                    valid=False,
                    reason_code=FORBIDDEN_PLACEHOLDER,
                    message=(
                        f"Detected forbidden placeholder(s) {list(intersection)} for entity "
                        f"'{entity.canonical_name}'."
                    ),
                    entity_id=entity.entity_id,
                    claim_id=claim_id,
                    details={"forbidden": list(intersection)},
                )

        # ---------------------------------------------------------------------
        # Precedence 2: Check missing canonical name
        # ---------------------------------------------------------------------
        if not cand_name:
            return ValidationResult(
                valid=False,
                reason_code=MISSING_CANDIDATE_IDENTITY,
                message=f"Candidate asset is missing canonical name/identity for required entity '{entity.canonical_name}'.",
                entity_id=entity.entity_id,
                claim_id=claim_id,
            )

        # ---------------------------------------------------------------------
        # Precedence 3: Check INSTITUTION_JURISDICTION_MISMATCH (forbidden alias / mismatched country/jurisdiction)
        # ---------------------------------------------------------------------
        forb_aliases = {a.lower() for a in entity.forbidden_aliases}
        if cand_name.lower() in forb_aliases:
            return ValidationResult(
                valid=False,
                reason_code=INSTITUTION_JURISDICTION_MISMATCH,
                message=(
                    f"Candidate name '{cand_name}' (Country: {cand_country or cand_jurisdiction}) "
                    f"is in forbidden aliases list for '{entity.canonical_name}' (Jurisdiction: {entity.jurisdiction})."
                ),
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={
                    "forbidden_alias": cand_name,
                    "candidate_country": cand_country,
                    "candidate_jurisdiction": cand_jurisdiction,
                },
            )

        if entity.jurisdiction and cand_jurisdiction and str(entity.jurisdiction).strip().upper() != str(cand_jurisdiction).strip().upper():
            return ValidationResult(
                valid=False,
                reason_code=INSTITUTION_JURISDICTION_MISMATCH,
                message=(
                    f"Jurisdiction mismatch for institution '{entity.canonical_name}': "
                    f"expected '{entity.jurisdiction}', candidate has '{cand_jurisdiction}'."
                ),
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={
                    "expected_jurisdiction": entity.jurisdiction,
                    "candidate_jurisdiction": cand_jurisdiction,
                },
            )
        if entity.country and cand_country and str(entity.country).strip().lower() != str(cand_country).strip().lower():
            return ValidationResult(
                valid=False,
                reason_code=INSTITUTION_JURISDICTION_MISMATCH,
                message=(
                    f"Country mismatch for entity '{entity.canonical_name}': "
                    f"expected '{entity.country}', candidate has '{cand_country}'."
                ),
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={"expected_country": entity.country, "candidate_country": cand_country},
            )

        # ---------------------------------------------------------------------
        # Precedence 4: Check LOCALE_MISMATCH
        # ---------------------------------------------------------------------
        if entity.locale and cand_locale and str(entity.locale).strip().lower() != str(cand_locale).strip().lower():
            return ValidationResult(
                valid=False,
                reason_code=LOCALE_MISMATCH,
                message=(
                    f"Locale mismatch for entity '{entity.canonical_name}': expected '{entity.locale}', "
                    f"candidate has '{cand_locale}'."
                ),
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={"expected_locale": entity.locale, "candidate_locale": cand_locale},
            )

        # ---------------------------------------------------------------------
        # Precedence 5: Check ENTITY_ATTRIBUTE_MISMATCH (mismatch on present attribute values)
        # ---------------------------------------------------------------------
        for attr_key, exp_val in entity.attributes.items():
            if attr_key in cand_attrs and cand_attrs[attr_key] is not None and str(cand_attrs[attr_key]).strip() != "":
                cand_val = cand_attrs[attr_key]
                if str(exp_val).strip().lower() != str(cand_val).strip().lower():
                    cand_desc = f"{cand_name or 'candidate'} ({attr_key}: {cand_val})"
                    return ValidationResult(
                        valid=False,
                        reason_code=ENTITY_ATTRIBUTE_MISMATCH,
                        message=(
                            f"Attribute mismatch on '{attr_key}' for '{entity.canonical_name}' vs candidate '{cand_desc}': "
                            f"expected '{exp_val}', candidate provides '{cand_val}'."
                        ),
                        entity_id=entity.entity_id,
                        claim_id=claim_id,
                        details={
                            "attribute": attr_key,
                            "expected": exp_val,
                            "candidate": cand_val,
                            "candidate_name": cand_name,
                        },
                    )

        # ---------------------------------------------------------------------
        # Precedence 6: Check MISSING_CANDIDATE_IDENTITY (missing required candidate fields, missing required attributes, missing jurisdiction/country/locale)
        # ---------------------------------------------------------------------
        # Check explicit required_candidate_fields (e.g. country, jurisdiction, locale)
        for req_field in entity.required_candidate_fields:
            cand_val = candidate_meta.get(req_field)
            if cand_val is None or str(cand_val).strip() == "":
                return ValidationResult(
                    valid=False,
                    reason_code=MISSING_CANDIDATE_IDENTITY,
                    message=f"Candidate asset is missing required candidate field '{req_field}' for entity '{entity.canonical_name}'.",
                    entity_id=entity.entity_id,
                    claim_id=claim_id,
                    details={"missing_field": req_field},
                )

        # Check required structured attributes (explicit required_attributes + keys in attributes)
        all_required_attr_keys = set(entity.required_attributes).union(entity.attributes.keys())
        for exp_key in all_required_attr_keys:
            if exp_key not in cand_attrs or cand_attrs[exp_key] is None or str(cand_attrs[exp_key]).strip() == "":
                exp_val = entity.attributes.get(exp_key)
                return ValidationResult(
                    valid=False,
                    reason_code=MISSING_CANDIDATE_IDENTITY,
                    message=f"Candidate asset is missing required structured attribute '{exp_key}' (expected '{exp_val}') for entity '{entity.canonical_name}'.",
                    entity_id=entity.entity_id,
                    claim_id=claim_id,
                    details={"missing_attribute": exp_key, "expected": exp_val},
                )

        if entity.jurisdiction and (cand_jurisdiction is None or str(cand_jurisdiction).strip() == ""):
            return ValidationResult(
                valid=False,
                reason_code=MISSING_CANDIDATE_IDENTITY,
                message=f"Candidate is missing required jurisdiction '{entity.jurisdiction}' for entity '{entity.canonical_name}'.",
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={"expected_jurisdiction": entity.jurisdiction},
            )

        if entity.country and (cand_country is None or str(cand_country).strip() == ""):
            return ValidationResult(
                valid=False,
                reason_code=MISSING_CANDIDATE_IDENTITY,
                message=f"Candidate is missing required country '{entity.country}' for entity '{entity.canonical_name}'.",
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={"expected_country": entity.country},
            )

        if entity.locale and (cand_locale is None or str(cand_locale).strip() == ""):
            return ValidationResult(
                valid=False,
                reason_code=MISSING_CANDIDATE_IDENTITY,
                message=f"Candidate is missing required locale '{entity.locale}' for entity '{entity.canonical_name}'.",
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={"expected_locale": entity.locale},
            )

        # ---------------------------------------------------------------------
        # Precedence 7: Check ENTITY_CANONICAL_MISMATCH
        # ---------------------------------------------------------------------
        valid_names = {entity.canonical_name.strip().lower()}
        valid_names.update(a.strip().lower() for a in entity.aliases)
        if cand_name.strip().lower() not in valid_names:
            return ValidationResult(
                valid=False,
                reason_code=ENTITY_CANONICAL_MISMATCH,
                message=(
                    f"Canonical name mismatch: expected '{entity.canonical_name}' or aliases "
                    f"{list(entity.aliases)}, candidate is '{cand_name}'."
                ),
                entity_id=entity.entity_id,
                claim_id=claim_id,
                details={"expected_name": entity.canonical_name, "candidate_name": cand_name},
            )

        return ValidationResult(
            valid=True,
            reason_code=VALIDATION_OK,
            message=f"Candidate asset verified for entity '{entity.canonical_name}'.",
            entity_id=entity.entity_id,
            claim_id=claim_id,
        )
