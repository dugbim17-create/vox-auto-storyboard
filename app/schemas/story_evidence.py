"""Typed StoryEvidencePack and ClaimSpec schema with strict recursive normalization (Phase 1B).

Implements fail-closed factual contracts for StoryEvidencePack v1:
- Project, claim, and source identities
- Claim types: confirmed | inferred | illustrative
- Strict SourceRef: requires identity (publisher or title) AND independent locator (url, source_path, source_id, document_id).
- Recursive nested normalization across direct constructors, mapping factories, and JSON roundtrips.
- Canonical named entities with explicit required candidate fields/attributes:
  (canonical_name, aliases, jurisdiction/country, locale, forbidden placeholders/aliases, required_candidate_fields, required_attributes, structured attributes)
- Strict validation gates: confirmed claims require at least one valid SourceRef.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ALLOWED_CLAIM_TYPES = {"confirmed", "inferred", "illustrative"}
VALID_SCHEMA_VERSION = "story_evidence/1.0"


class StoryEvidenceError(ValueError):
    """Raised when story evidence schema or validation fails."""

    def __init__(self, message: str, reason_code: str = "INVALID_EVIDENCE") -> None:
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message


@dataclass(frozen=True)
class SourceRef:
    """Archival / verified source reference for a factual claim.

    Phase 1B strict contract:
    - At least one identity field: non-empty publisher or title
    - At least one independent locator: non-empty url, source_path, source_id, or document_id
    """

    publisher: str = ""
    title: str = ""
    url: str = ""
    source_path: str = ""
    source_id: str = ""
    document_id: str = ""
    license: str = ""
    retrieved_at: str = ""

    def __post_init__(self) -> None:
        pub = str(self.publisher or "").strip()
        tit = str(self.title or "").strip()
        has_identity = bool(pub or tit)
        if not has_identity:
            raise StoryEvidenceError(
                "SourceRef requires an identity field (non-empty publisher or title).",
                reason_code="INVALID_SOURCE",
            )

        u = str(self.url or "").strip()
        sp = str(self.source_path or "").strip()
        sid = str(self.source_id or "").strip()
        did = str(self.document_id or "").strip()
        has_locator = bool(u or sp or sid or did)
        if not has_locator:
            raise StoryEvidenceError(
                "SourceRef requires an independent locator (non-empty url, source_path, source_id, or document_id).",
                reason_code="MISSING_SOURCE_LOCATOR",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "title": self.title,
            "url": self.url,
            "source_path": self.source_path,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "license": self.license,
            "retrieved_at": self.retrieved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRef:
        if not isinstance(data, dict):
            raise StoryEvidenceError(
                f"SourceRef mapping must be a dict, got {type(data).__name__}",
                reason_code="INVALID_SOURCE",
            )
        return cls(
            publisher=str(data.get("publisher") or ""),
            title=str(data.get("title") or ""),
            url=str(data.get("url") or ""),
            source_path=str(data.get("source_path") or ""),
            source_id=str(data.get("source_id") or ""),
            document_id=str(data.get("document_id") or ""),
            license=str(data.get("license") or ""),
            retrieved_at=str(data.get("retrieved_at") or ""),
        )


@dataclass(frozen=True)
class EntitySpec:
    """Canonical named entity with disambiguating metadata and explicit required candidate fields."""

    entity_id: str
    canonical_name: str
    entity_type: str = "entity"
    aliases: tuple[str, ...] = ()
    jurisdiction: str | None = None
    country: str | None = None
    locale: str | None = None
    forbidden_placeholders: tuple[str, ...] = ()
    forbidden_aliases: tuple[str, ...] = ()
    required_candidate_fields: tuple[str, ...] = ()
    required_attributes: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.entity_id or not str(self.entity_id).strip():
            raise StoryEvidenceError("entity_id is required", reason_code="INVALID_ENTITY")
        if not self.canonical_name or not str(self.canonical_name).strip():
            raise StoryEvidenceError("canonical_name is required", reason_code="INVALID_ENTITY")

        if isinstance(self.aliases, (list, set)):
            object.__setattr__(self, "aliases", tuple(self.aliases))
        if isinstance(self.forbidden_placeholders, (list, set)):
            object.__setattr__(self, "forbidden_placeholders", tuple(self.forbidden_placeholders))
        if isinstance(self.forbidden_aliases, (list, set)):
            object.__setattr__(self, "forbidden_aliases", tuple(self.forbidden_aliases))
        if isinstance(self.required_candidate_fields, (list, set)):
            object.__setattr__(self, "required_candidate_fields", tuple(self.required_candidate_fields))
        if isinstance(self.required_attributes, (list, set)):
            object.__setattr__(self, "required_attributes", tuple(self.required_attributes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type,
            "aliases": list(self.aliases),
            "jurisdiction": self.jurisdiction,
            "country": self.country,
            "locale": self.locale,
            "forbidden_placeholders": list(self.forbidden_placeholders),
            "forbidden_aliases": list(self.forbidden_aliases),
            "required_candidate_fields": list(self.required_candidate_fields),
            "required_attributes": list(self.required_attributes),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntitySpec:
        if not isinstance(data, dict):
            raise StoryEvidenceError(
                f"EntitySpec mapping must be a dict, got {type(data).__name__}",
                reason_code="INVALID_ENTITY",
            )
        known_fields = {
            "entity_id",
            "canonical_name",
            "entity_type",
            "type",
            "aliases",
            "jurisdiction",
            "country",
            "locale",
            "forbidden_placeholders",
            "forbidden_aliases",
            "required_candidate_fields",
            "required_attributes",
            "attributes",
        }
        attrs = dict(data.get("attributes") or {})
        for k, v in data.items():
            if k not in known_fields and k not in attrs:
                attrs[k] = v

        aliases_raw = data.get("aliases") or []
        forb_p_raw = data.get("forbidden_placeholders") or []
        forb_a_raw = data.get("forbidden_aliases") or []
        req_cand_raw = data.get("required_candidate_fields") or []
        req_attr_raw = data.get("required_attributes") or []

        return cls(
            entity_id=str(data.get("entity_id") or ""),
            canonical_name=str(data.get("canonical_name") or ""),
            entity_type=str(data.get("entity_type") or data.get("type") or "entity"),
            aliases=tuple(aliases_raw),
            jurisdiction=data.get("jurisdiction"),
            country=data.get("country"),
            locale=data.get("locale"),
            forbidden_placeholders=tuple(forb_p_raw),
            forbidden_aliases=tuple(forb_a_raw),
            required_candidate_fields=tuple(req_cand_raw),
            required_attributes=tuple(req_attr_raw),
            attributes=attrs,
        )


@dataclass(frozen=True)
class ClaimSpec:
    """Factual claim with evidence requirements and bounds.

    Phase 1B: Constructor recursively normalizes entities and sources.
    """

    claim_id: str
    claim_text: str
    claim_type: Literal["confirmed", "inferred", "illustrative"] = "confirmed"
    date: str | None = None
    place: str | None = None
    entities: tuple[EntitySpec, ...] = ()
    sources: tuple[SourceRef, ...] = ()
    must_show: tuple[str, ...] = ()
    must_not_invent: tuple[str, ...] = ()
    confidence: float = 1.0
    claim_risk: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id or not str(self.claim_id).strip():
            raise StoryEvidenceError("claim_id is required", reason_code="INVALID_CLAIM")
        if not self.claim_text or not str(self.claim_text).strip():
            raise StoryEvidenceError("claim_text is required", reason_code="INVALID_CLAIM")
        if self.claim_type not in ALLOWED_CLAIM_TYPES:
            raise StoryEvidenceError(
                f"claim_type '{self.claim_type}' must be one of {ALLOWED_CLAIM_TYPES}",
                reason_code="INVALID_CLAIM_TYPE",
            )
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise StoryEvidenceError(
                f"confidence {self.confidence} must be in range [0.0, 1.0]",
                reason_code="INVALID_CONFIDENCE",
            )

        # Recursive normalization of entities
        norm_entities: list[EntitySpec] = []
        for item in self.entities:
            if isinstance(item, EntitySpec):
                norm_entities.append(item)
            elif isinstance(item, dict):
                norm_entities.append(EntitySpec.from_dict(item))
            else:
                raise StoryEvidenceError(
                    f"Invalid entity item of type {type(item).__name__}",
                    reason_code="INVALID_ENTITY",
                )
        object.__setattr__(self, "entities", tuple(norm_entities))

        # Recursive normalization of sources
        norm_sources: list[SourceRef] = []
        for item in self.sources:
            if isinstance(item, SourceRef):
                norm_sources.append(item)
            elif isinstance(item, dict):
                norm_sources.append(SourceRef.from_dict(item))
            else:
                raise StoryEvidenceError(
                    f"Invalid source item of type {type(item).__name__}",
                    reason_code="INVALID_SOURCE",
                )
        object.__setattr__(self, "sources", tuple(norm_sources))

        if isinstance(self.must_show, (list, set)):
            object.__setattr__(self, "must_show", tuple(self.must_show))
        if isinstance(self.must_not_invent, (list, set)):
            object.__setattr__(self, "must_not_invent", tuple(self.must_not_invent))

    def get_entity(self, entity_id: str) -> EntitySpec | None:
        for ent in self.entities:
            if ent.entity_id == entity_id:
                return ent
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "date": self.date,
            "place": self.place,
            "entities": [e.to_dict() for e in self.entities],
            "sources": [s.to_dict() for s in self.sources],
            "must_show": list(self.must_show),
            "must_not_invent": list(self.must_not_invent),
            "confidence": self.confidence,
            "claim_risk": self.claim_risk,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaimSpec:
        if not isinstance(data, dict):
            raise StoryEvidenceError(
                f"ClaimSpec mapping must be a dict, got {type(data).__name__}",
                reason_code="INVALID_CLAIM",
            )
        entities = tuple(
            EntitySpec.from_dict(item) if isinstance(item, dict) else item
            for item in data.get("entities") or []
        )
        sources = tuple(
            SourceRef.from_dict(item) if isinstance(item, dict) else item
            for item in data.get("sources") or []
        )
        return cls(
            claim_id=str(data.get("claim_id") or ""),
            claim_text=str(data.get("claim_text") or ""),
            claim_type=data.get("claim_type") or "confirmed",
            date=data.get("date"),
            place=data.get("place"),
            entities=entities,
            sources=sources,
            must_show=tuple(data.get("must_show") or []),
            must_not_invent=tuple(data.get("must_not_invent") or []),
            confidence=float(data.get("confidence") if data.get("confidence") is not None else 1.0),
            claim_risk=data.get("claim_risk"),
        )


@dataclass(frozen=True)
class StoryEvidencePack:
    """Top-level container for a project's verified evidence baseline.

    Phase 1B: Constructor recursively normalizes claims.
    """

    project_id: str
    schema_version: str = VALID_SCHEMA_VERSION
    claims: tuple[ClaimSpec, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        norm_claims: list[ClaimSpec] = []
        for item in self.claims:
            if isinstance(item, ClaimSpec):
                norm_claims.append(item)
            elif isinstance(item, dict):
                norm_claims.append(ClaimSpec.from_dict(item))
            else:
                raise StoryEvidenceError(
                    f"Invalid claim item of type {type(item).__name__}",
                    reason_code="INVALID_CLAIM",
                )
        object.__setattr__(self, "claims", tuple(norm_claims))

    def get_claim(self, claim_id: str) -> ClaimSpec | None:
        for c in self.claims:
            if c.claim_id == claim_id:
                return c
        return None

    def get_entity(self, entity_id: str) -> EntitySpec | None:
        for c in self.claims:
            ent = c.get_entity(entity_id)
            if ent is not None:
                return ent
        return None

    def validate_pack(self) -> None:
        """Validate integrity and fail-closed rules across all claims."""
        if not self.project_id or not str(self.project_id).strip():
            raise StoryEvidenceError("StoryEvidencePack requires non-empty project_id", reason_code="INVALID_PROJECT_ID")

        if self.schema_version != VALID_SCHEMA_VERSION:
            raise StoryEvidenceError(
                f"Invalid schema_version '{self.schema_version}', expected '{VALID_SCHEMA_VERSION}'",
                reason_code="INVALID_SCHEMA_VERSION",
            )

        if not self.claims:
            raise StoryEvidenceError("StoryEvidencePack requires at least one claim", reason_code="EMPTY_CLAIMS")

        seen_claim_ids: set[str] = set()
        seen_entity_ids: set[str] = set()

        for claim in self.claims:
            if claim.claim_id in seen_claim_ids:
                raise StoryEvidenceError(
                    f"Duplicate claim_id: {claim.claim_id}", reason_code="DUPLICATE_CLAIM_ID"
                )
            seen_claim_ids.add(claim.claim_id)

            for entity in claim.entities:
                if entity.entity_id in seen_entity_ids:
                    raise StoryEvidenceError(
                        f"Duplicate entity_id '{entity.entity_id}' found in claim '{claim.claim_id}'.",
                        reason_code="DUPLICATE_ENTITY_ID",
                    )
                seen_entity_ids.add(entity.entity_id)

            if claim.claim_type == "confirmed" and not claim.sources:
                raise StoryEvidenceError(
                    f"Confirmed claim '{claim.claim_id}' lacks external source citations (SourceRef required; confidence cannot substitute).",
                    reason_code="MISSING_REQUIRED_EVIDENCE",
                )

            declared_entity_ids = {e.entity_id for e in claim.entities}
            for must_id in claim.must_show:
                if must_id not in declared_entity_ids:
                    raise StoryEvidenceError(
                        f"Claim '{claim.claim_id}' must_show entity '{must_id}' not found in declared entities.",
                        reason_code="MISSING_ENTITY",
                    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "claims": [c.to_dict() for c in self.claims],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryEvidencePack:
        if not isinstance(data, dict):
            raise StoryEvidenceError(
                f"StoryEvidencePack mapping must be a dict, got {type(data).__name__}",
                reason_code="INVALID_EVIDENCE_PACK",
            )
        claims = tuple(
            ClaimSpec.from_dict(item) if isinstance(item, dict) else item
            for item in data.get("claims") or []
        )
        return cls(
            project_id=str(data.get("project_id") or ""),
            schema_version=str(data.get("schema_version") or VALID_SCHEMA_VERSION),
            claims=claims,
            created_at=str(data.get("created_at") or ""),
        )

    @classmethod
    def from_mapping_strict(cls, data: dict[str, Any]) -> StoryEvidencePack:
        pack = cls.from_dict(data)
        pack.validate_pack()
        return pack
