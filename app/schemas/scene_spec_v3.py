"""SceneSpec v3 Typed Contract with Relational Grammar Contracts (Phase 2B Correction 1).

Defines the single authoritative v3 scene contract:
- Explicit typed relational grammar contract matching primary grammar exactly
- Strict schema invariants (schema_version exact, revision > 0, 64-hex hashes, nondecreasing action starts)
- Collection invariants (no duplicate/empty IDs in source_unit_ids, evidence_ids)
- Application-owned authority fields (revision, hashes, approval/vision status)
- Strict recursive normalization across constructors, mapping factories, and JSON roundtrips
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.scene_grammar_contracts import (
    CharacterPerformanceContract,
    ChartProgressionContract,
    DocumentEvidenceContract,
    ExplanatoryHoldContract,
    GrammarContractError,
    GrammarContractType,
    MapRouteContract,
    ObjectAssemblyContract,
    ProcessFlowContract,
)

ALLOWED_SCENE_GRAMMARS = {
    "character_performance",
    "object_assembly",
    "map_route",
    "chart_progression",
    "process_flow",
    "document_evidence",
    "explanatory_hold",
}

GRAMMAR_CONTRACT_CLASS_MAP: dict[str, type] = {
    "map_route": MapRouteContract,
    "process_flow": ProcessFlowContract,
    "object_assembly": ObjectAssemblyContract,
    "character_performance": CharacterPerformanceContract,
    "document_evidence": DocumentEvidenceContract,
    "chart_progression": ChartProgressionContract,
    "explanatory_hold": ExplanatoryHoldContract,
}

ALLOWED_ACTION_TYPES = {
    "reveal",
    "traveling_marker",
    "path_draw",
    "transfer_token",
    "chart_series",
    "counter_progress",
    "document_focus",
    "region_highlight",
    "state_swap",
    "pose_sequence",
    "hold",
    "exit_policy",
    "move",
    "transform",
    "focus_shift",
}

VALID_SCENE_SPEC_VERSION = "scene_spec/3.0"
HEX_64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class SceneSpecV3Error(ValueError):
    """Raised when a SceneSpec v3 contract is invalid."""

    def __init__(self, message: str, reason_code: str = "INVALID_SCENE_SPEC") -> None:
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message


def compute_scene_spec_hash(payload: dict[str, Any]) -> str:
    """Compute canonical SHA-256 hash of a SceneSpec payload excluding dynamic authority fields."""
    filtered = {
        k: v for k, v in payload.items()
        if k not in {"spec_sha256", "approval_status", "vision_status"}
    }
    canonical_json = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _check_unique_ids(items: tuple[str, ...], name: str) -> None:
    seen: set[str] = set()
    for s in items:
        cleaned = str(s).strip()
        if not cleaned:
            raise SceneSpecV3Error(f"{name} contains empty identifier.", reason_code="INVALID_COLLECTION_ITEM")
        if cleaned in seen:
            raise SceneSpecV3Error(f"Duplicate identifier '{cleaned}' in {name}.", reason_code="DUPLICATE_COLLECTION_ITEM")
        seen.add(cleaned)


@dataclass(frozen=True)
class SceneAction:
    """Typed procedural action track within a SceneSpec v3."""

    action_id: str
    action_type: str
    target_id: str = ""
    source_id: str = ""
    start_ms: int = 0
    duration_ms: int = 1000
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_id or not str(self.action_id).strip():
            raise SceneSpecV3Error("action_id is required", reason_code="INVALID_ACTION")
        if not self.action_type or not str(self.action_type).strip():
            raise SceneSpecV3Error("action_type is required", reason_code="INVALID_ACTION")
        if self.start_ms < 0:
            raise SceneSpecV3Error(f"Action '{self.action_id}' start_ms cannot be negative.", reason_code="INVALID_ACTION_TIMING")
        if self.duration_ms <= 0:
            raise SceneSpecV3Error(f"Action '{self.action_id}' duration_ms must be positive.", reason_code="INVALID_ACTION_TIMING")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target_id": self.target_id,
            "source_id": self.source_id,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneAction:
        if not isinstance(data, dict):
            raise SceneSpecV3Error(
                f"SceneAction mapping must be a dict, got {type(data).__name__}",
                reason_code="INVALID_ACTION",
            )
        return cls(
            action_id=str(data.get("action_id") or data.get("id") or ""),
            action_type=str(data.get("action_type") or data.get("type") or data.get("action") or ""),
            target_id=str(data.get("target_id") or data.get("target") or ""),
            source_id=str(data.get("source_id") or data.get("source") or ""),
            start_ms=int(data.get("start_ms") if data.get("start_ms") is not None else data.get("at_ms") or 0),
            duration_ms=int(data.get("duration_ms") or 1000),
            params=dict(data.get("params") or {}),
        )


@dataclass(frozen=True)
class SceneSpecV3:
    """Canonical SceneSpec v3 schema with typed relational grammar contract."""

    project_id: str
    scene_id: str
    revision: int = 1
    schema_version: str = VALID_SCENE_SPEC_VERSION
    script_snapshot_sha256: str = ""
    evidence_pack_sha256: str = ""
    source_unit_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    purpose: str = "body"
    grammar: str = "explanatory_hold"
    visual_thesis: str = ""
    must_show: tuple[str, ...] = ()
    must_not_invent: tuple[str, ...] = ()
    asset_requirements: tuple[dict[str, Any], ...] = ()
    authority_order: tuple[str, ...] = ("source_verified", "procedural", "licensed_search", "ai_generated")
    narration_anchors: tuple[dict[str, Any], ...] = ()
    start_state: dict[str, Any] = field(default_factory=dict)
    actions: tuple[SceneAction, ...] = ()
    end_state: dict[str, Any] = field(default_factory=dict)
    hold_policy: dict[str, Any] = field(default_factory=dict)
    exit_policy: dict[str, Any] = field(default_factory=dict)
    composition: dict[str, Any] = field(default_factory=dict)
    continuity_in: dict[str, Any] = field(default_factory=dict)
    continuity_out: dict[str, Any] = field(default_factory=dict)
    renderer_profile: str = "vox_classic"
    seed_policy: dict[str, Any] = field(default_factory=dict)
    grammar_contract: GrammarContractType | None = None
    approval_status: str = "pending"
    vision_status: str = "pending"
    duration_ms: int = 4000
    fps: int = 30
    motion_fps: int = 12
    params: dict[str, Any] = field(default_factory=dict)
    spec_sha256: str = ""
    planning_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.project_id or not str(self.project_id).strip():
            raise SceneSpecV3Error("project_id is required", reason_code="INVALID_PROJECT_ID")
        if not self.scene_id or not str(self.scene_id).strip():
            raise SceneSpecV3Error("scene_id is required", reason_code="INVALID_SCENE_ID")

        # Invariants: schema_version, revision, fingerprint
        if self.schema_version != VALID_SCENE_SPEC_VERSION:
            raise SceneSpecV3Error(
                f"schema_version must be exactly '{VALID_SCENE_SPEC_VERSION}', got '{self.schema_version}'",
                reason_code="INVALID_SCHEMA_VERSION",
            )
        if not isinstance(self.revision, int) or self.revision <= 0:
            raise SceneSpecV3Error(
                f"revision must be an integer > 0, got '{self.revision}'",
                reason_code="INVALID_REVISION",
            )
        if self.planning_fingerprint and not HEX_64_PATTERN.match(self.planning_fingerprint):
            raise SceneSpecV3Error(
                f"planning_fingerprint must be 64 hex chars, got '{self.planning_fingerprint}'",
                reason_code="INVALID_FINGERPRINT",
            )

        if not self.script_snapshot_sha256 or not str(self.script_snapshot_sha256).strip():
            raise SceneSpecV3Error("script_snapshot_sha256 is required", reason_code="MISSING_IMMUTABLE_SNAPSHOT")
        if not HEX_64_PATTERN.match(self.script_snapshot_sha256):
            raise SceneSpecV3Error("script_snapshot_sha256 must be exactly 64 hex characters", reason_code="INVALID_SNAPSHOT_HASH")

        if not self.evidence_pack_sha256 or not str(self.evidence_pack_sha256).strip():
            raise SceneSpecV3Error("evidence_pack_sha256 is required", reason_code="MISSING_IMMUTABLE_SNAPSHOT")
        if not HEX_64_PATTERN.match(self.evidence_pack_sha256):
            raise SceneSpecV3Error("evidence_pack_sha256 must be exactly 64 hex characters", reason_code="INVALID_SNAPSHOT_HASH")

        if not self.visual_thesis or not str(self.visual_thesis).strip():
            raise SceneSpecV3Error("visual_thesis is required and cannot be empty", reason_code="INVALID_VISUAL_THESIS")

        if self.duration_ms <= 0:
            raise SceneSpecV3Error("duration_ms must be positive", reason_code="INVALID_DURATION")
        if self.fps <= 0 or self.motion_fps <= 0 or self.motion_fps > self.fps:
            raise SceneSpecV3Error("fps and motion_fps must be positive, and motion_fps <= fps", reason_code="INVALID_FPS")

        if self.grammar not in ALLOWED_SCENE_GRAMMARS:
            raise SceneSpecV3Error(
                f"grammar '{self.grammar}' must be one of {ALLOWED_SCENE_GRAMMARS}",
                reason_code="INVALID_SCENE_GRAMMAR",
            )

        # Exact grammar contract class verification (F2)
        if self.grammar_contract is not None:
            expected_cls = GRAMMAR_CONTRACT_CLASS_MAP.get(self.grammar)
            if isinstance(self.grammar_contract, dict):
                if expected_cls:
                    try:
                        parsed = expected_cls.from_dict(self.grammar_contract)
                        object.__setattr__(self, "grammar_contract", parsed)
                    except GrammarContractError as exc:
                        raise SceneSpecV3Error(exc.message, reason_code=exc.reason_code) from exc
            elif expected_cls and not isinstance(self.grammar_contract, expected_cls):
                raise SceneSpecV3Error(
                    f"grammar '{self.grammar}' requires contract of type {expected_cls.__name__}, got {type(self.grammar_contract).__name__}",
                    reason_code="INVALID_GRAMMAR_CONTRACT",
                )

        # Normalize and validate collections (F4: no duplicates/empty strings)
        if isinstance(self.source_unit_ids, (list, set)):
            object.__setattr__(self, "source_unit_ids", tuple(self.source_unit_ids))
        _check_unique_ids(self.source_unit_ids, "source_unit_ids")

        if isinstance(self.evidence_ids, (list, set)):
            object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        _check_unique_ids(self.evidence_ids, "evidence_ids")

        if isinstance(self.must_show, (list, set)):
            object.__setattr__(self, "must_show", tuple(self.must_show))
        _check_unique_ids(self.must_show, "must_show")

        if isinstance(self.must_not_invent, (list, set)):
            object.__setattr__(self, "must_not_invent", tuple(self.must_not_invent))
        _check_unique_ids(self.must_not_invent, "must_not_invent")

        if isinstance(self.asset_requirements, (list, set)):
            object.__setattr__(self, "asset_requirements", tuple(self.asset_requirements))
        if isinstance(self.authority_order, (list, set)):
            object.__setattr__(self, "authority_order", tuple(self.authority_order))
        if isinstance(self.narration_anchors, (list, set)):
            object.__setattr__(self, "narration_anchors", tuple(self.narration_anchors))

        # Normalize and validate actions (F3: nondecreasing start_ms)
        norm_actions: list[SceneAction] = []
        seen_action_ids: set[str] = set()
        last_start_ms = -1
        for item in self.actions:
            if isinstance(item, SceneAction):
                act_obj = item
            elif isinstance(item, dict):
                act_obj = SceneAction.from_dict(item)
            else:
                raise SceneSpecV3Error(f"Invalid action item of type {type(item).__name__}", reason_code="INVALID_ACTION")

            if act_obj.action_id in seen_action_ids:
                raise SceneSpecV3Error(f"Duplicate action_id '{act_obj.action_id}' in scene '{self.scene_id}'.", reason_code="DUPLICATE_ACTION_ID")
            seen_action_ids.add(act_obj.action_id)

            if act_obj.start_ms < last_start_ms:
                raise SceneSpecV3Error(
                    f"Action '{act_obj.action_id}' start_ms {act_obj.start_ms} is earlier than previous action start_ms {last_start_ms}.",
                    reason_code="INVALID_ACTION_TIMING",
                )
            last_start_ms = act_obj.start_ms

            if act_obj.start_ms + act_obj.duration_ms > self.duration_ms:
                raise SceneSpecV3Error(
                    f"Action '{act_obj.action_id}' ({act_obj.start_ms}ms + {act_obj.duration_ms}ms = {act_obj.start_ms + act_obj.duration_ms}ms) exceeds scene duration {self.duration_ms}ms.",
                    reason_code="INVALID_ACTION_TIMING",
                )

            norm_actions.append(act_obj)

        object.__setattr__(self, "actions", tuple(norm_actions))

        # Always recompute authority spec_sha256 from actual content
        raw = self.to_dict()
        h = compute_scene_spec_hash(raw)
        object.__setattr__(self, "spec_sha256", h)

    def to_dict(self) -> dict[str, Any]:
        contract_dict = self.grammar_contract.to_dict() if self.grammar_contract is not None else None
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "scene_id": self.scene_id,
            "revision": self.revision,
            "script_snapshot_sha256": self.script_snapshot_sha256,
            "evidence_pack_sha256": self.evidence_pack_sha256,
            "source_unit_ids": list(self.source_unit_ids),
            "evidence_ids": list(self.evidence_ids),
            "purpose": self.purpose,
            "grammar": self.grammar,
            "visual_thesis": self.visual_thesis,
            "must_show": list(self.must_show),
            "must_not_invent": list(self.must_not_invent),
            "asset_requirements": list(self.asset_requirements),
            "authority_order": list(self.authority_order),
            "narration_anchors": list(self.narration_anchors),
            "start_state": dict(self.start_state),
            "actions": [a.to_dict() for a in self.actions],
            "end_state": dict(self.end_state),
            "hold_policy": dict(self.hold_policy),
            "exit_policy": dict(self.exit_policy),
            "composition": dict(self.composition),
            "continuity_in": dict(self.continuity_in),
            "continuity_out": dict(self.continuity_out),
            "renderer_profile": self.renderer_profile,
            "seed_policy": dict(self.seed_policy),
            "grammar_contract": contract_dict,
            "approval_status": self.approval_status,
            "vision_status": self.vision_status,
            "duration_ms": self.duration_ms,
            "fps": self.fps,
            "motion_fps": self.motion_fps,
            "params": dict(self.params),
            "spec_sha256": self.spec_sha256,
            "planning_fingerprint": self.planning_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneSpecV3:
        if not isinstance(data, dict):
            raise SceneSpecV3Error(
                f"SceneSpecV3 mapping must be a dict, got {type(data).__name__}",
                reason_code="INVALID_SCENE_SPEC",
            )
        actions = tuple(
            SceneAction.from_dict(item) if isinstance(item, dict) else item
            for item in data.get("actions") or []
        )

        grammar = str(data.get("grammar") or "explanatory_hold")
        contract_data = data.get("grammar_contract") or data.get("params") or {}

        # Parse matching typed grammar contract strictly (F1 & F2)
        parsed_contract: GrammarContractType | None = None
        expected_cls = GRAMMAR_CONTRACT_CLASS_MAP.get(grammar)

        if isinstance(contract_data, (MapRouteContract, ProcessFlowContract, ObjectAssemblyContract, CharacterPerformanceContract, DocumentEvidenceContract, ChartProgressionContract, ExplanatoryHoldContract)):
            if expected_cls and not isinstance(contract_data, expected_cls):
                raise SceneSpecV3Error(
                    f"grammar '{grammar}' requires contract of type {expected_cls.__name__}, got {type(contract_data).__name__}",
                    reason_code="INVALID_GRAMMAR_CONTRACT",
                )
            parsed_contract = contract_data
        elif isinstance(contract_data, dict) and contract_data:
            try:
                if grammar == "map_route" and ("route_spec" in contract_data or "route_id" in contract_data or "declared_polyline" in contract_data):
                    route_dict = contract_data.get("route_spec") if "route_spec" in contract_data else contract_data
                    if isinstance(route_dict, dict):
                        parsed_contract = MapRouteContract.from_dict(route_dict)
                elif grammar == "process_flow" and ("process_spec" in contract_data or "nodes" in contract_data or "edges" in contract_data):
                    proc_dict = contract_data.get("process_spec") if "process_spec" in contract_data else contract_data
                    if isinstance(proc_dict, dict):
                        parsed_contract = ProcessFlowContract.from_dict(proc_dict)
                elif grammar == "object_assembly" and ("parts" in contract_data or "assembly_intent" in contract_data):
                    parsed_contract = ObjectAssemblyContract.from_dict(contract_data)
                elif grammar == "character_performance" and ("character_spec" in contract_data or "performer_id" in contract_data or "puppet_id" in contract_data):
                    char_dict = contract_data.get("character_spec") if "character_spec" in contract_data else contract_data
                    if isinstance(char_dict, dict):
                        parsed_contract = CharacterPerformanceContract.from_dict(char_dict)
                elif grammar == "document_evidence" and ("document_spec" in contract_data or "document_id" in contract_data):
                    doc_dict = contract_data.get("document_spec") if "document_spec" in contract_data else contract_data
                    if isinstance(doc_dict, dict):
                        parsed_contract = DocumentEvidenceContract.from_dict(doc_dict)
                elif grammar == "chart_progression" and ("chart_spec" in contract_data or "series" in contract_data):
                    chart_dict = contract_data.get("chart_spec") if "chart_spec" in contract_data else contract_data
                    if isinstance(chart_dict, dict):
                        parsed_contract = ChartProgressionContract.from_dict(chart_dict)
                elif grammar == "explanatory_hold" and ("hold_policy" in data or "declared_purpose" in contract_data):
                    hold_dict = data.get("hold_policy") or contract_data
                    if isinstance(hold_dict, dict) and "declared_purpose" in hold_dict:
                        parsed_contract = ExplanatoryHoldContract.from_dict(hold_dict)
            except GrammarContractError as exc:
                raise SceneSpecV3Error(exc.message, reason_code=exc.reason_code) from exc

        return cls(
            project_id=str(data.get("project_id") or ""),
            scene_id=str(data.get("scene_id") or ""),
            revision=int(data.get("revision") if data.get("revision") is not None else 1),
            schema_version=str(data.get("schema_version") or VALID_SCENE_SPEC_VERSION),
            script_snapshot_sha256=str(data.get("script_snapshot_sha256") or ""),
            evidence_pack_sha256=str(data.get("evidence_pack_sha256") or ""),
            source_unit_ids=tuple(data.get("source_unit_ids") or []),
            evidence_ids=tuple(data.get("evidence_ids") or []),
            purpose=str(data.get("purpose") or "body"),
            grammar=grammar,
            visual_thesis=str(data.get("visual_thesis") or ""),
            must_show=tuple(data.get("must_show") or []),
            must_not_invent=tuple(data.get("must_not_invent") or []),
            asset_requirements=tuple(data.get("asset_requirements") or []),
            authority_order=tuple(data.get("authority_order") or ("source_verified", "procedural", "licensed_search", "ai_generated")),
            narration_anchors=tuple(data.get("narration_anchors") or []),
            start_state=dict(data.get("start_state") or {}),
            actions=actions,
            end_state=dict(data.get("end_state") or {}),
            hold_policy=dict(data.get("hold_policy") or {}),
            exit_policy=dict(data.get("exit_policy") or {}),
            composition=dict(data.get("composition") or {}),
            continuity_in=dict(data.get("continuity_in") or {}),
            continuity_out=dict(data.get("continuity_out") or {}),
            renderer_profile=str(data.get("renderer_profile") or "vox_classic"),
            seed_policy=dict(data.get("seed_policy") or {}),
            grammar_contract=parsed_contract,
            approval_status="pending",
            vision_status="pending",
            duration_ms=int(data.get("duration_ms") or 4000),
            fps=int(data.get("fps") or 30),
            motion_fps=int(data.get("motion_fps") or 12),
            params=dict(data.get("params") or {}),
            planning_fingerprint=str(data.get("planning_fingerprint") or ""),
        )
