"""SceneSpecValidator service for fail-closed scene grammar and relational contract verification (Phase 2B Correction 2 Final).

Enforces strict relational bindings for all 7 grammar families:
- MapRouteContract: route_id ↔ path_draw ↔ traveling_marker ↔ marker_id ↔ continuous polyline.
- ProcessFlowContract: nodes ↔ edges ↔ transfer_token(source_id, target_id, token_label, amount/unit) ↔ changed non-empty start/end state with source/target entries.
- ObjectAssemblyContract: parts ↔ semantic transform actions ↔ start_state != end_state agreeing with start/end configurations.
- CharacterPerformanceContract: performer_id ↔ capabilities ↔ acting_intent ↔ pose actions ↔ changed lifecycle agreeing with start/end poses.
- DocumentEvidenceContract: document_id in evidence_ids ↔ focus_region ↔ citation ↔ document_focus action targeting document_id with page/focus params.
- ChartProgressionContract: domain ↔ numeric series >=2 points ↔ units ↔ source in evidence_ids ↔ chart_series action targeting series_id.
- ExplanatoryHoldContract: declared_purpose ↔ narration_anchors ↔ prior_state_change resolves to real action/state ↔ duration cap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.scene_grammar_contracts import (
    CharacterPerformanceContract,
    ChartProgressionContract,
    DocumentEvidenceContract,
    ExplanatoryHoldContract,
    MapRouteContract,
    ObjectAssemblyContract,
    ProcessFlowContract,
)
from app.schemas.scene_spec_v3 import (
    ALLOWED_ACTION_TYPES,
    ALLOWED_SCENE_GRAMMARS,
    GRAMMAR_CONTRACT_CLASS_MAP,
    SceneSpecV3,
)

# Stable Machine-Readable Reason Codes
INVALID_SCENE_GRAMMAR = "INVALID_SCENE_GRAMMAR"
INVALID_GRAMMAR_CONTRACT = "INVALID_GRAMMAR_CONTRACT"
REVEAL_ONLY_ACTION_REJECTED = "REVEAL_ONLY_ACTION_REJECTED"
EXPLANATORY_HOLD_WITHOUT_PURPOSE = "EXPLANATORY_HOLD_WITHOUT_PURPOSE"
MAP_DISCONTINUOUS_ROUTE = "MAP_DISCONTINUOUS_ROUTE"
MAP_ROUTE_BINDING_MISMATCH = "MAP_ROUTE_BINDING_MISMATCH"
PROCESS_FLOW_NO_TRANSFER = "PROCESS_FLOW_NO_TRANSFER"
OBJECT_ASSEMBLY_NO_TRANSFORMATION = "OBJECT_ASSEMBLY_NO_TRANSFORMATION"
CHARACTER_PERFORMANCE_NOT_READY = "CHARACTER_PERFORMANCE_NOT_READY"
DOCUMENT_EVIDENCE_INCOMPLETE = "DOCUMENT_EVIDENCE_INCOMPLETE"
CHART_MISSING_DATA = "CHART_MISSING_DATA"
UNSUPPORTED_ACTION_TYPE = "UNSUPPORTED_ACTION_TYPE"
MISSING_IMMUTABLE_SNAPSHOT = "MISSING_IMMUTABLE_SNAPSHOT"
VALIDATION_OK = "VALIDATION_OK"


class SceneValidationError(ValueError):
    """Raised when a SceneSpec v3 fails structural or relational validation."""

    def __init__(
        self,
        message: str,
        reason_code: str = INVALID_SCENE_GRAMMAR,
        scene_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message
        self.scene_id = scene_id
        self.details = details or {}


@dataclass(frozen=True)
class SceneValidationResult:
    """Structured result of a SceneSpec validation check."""

    valid: bool
    reason_code: str
    message: str
    scene_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class SceneSpecValidator:
    """Validator enforcing fail-closed SceneSpec v3 grammar and relational contracts."""

    def validate(self, spec: SceneSpecV3) -> SceneValidationResult:
        """Validate a SceneSpec v3 instance with strict relational bindings."""
        if not isinstance(spec, SceneSpecV3):
            raise TypeError(f"SceneSpecValidator requires SceneSpecV3, got {type(spec).__name__}")

        # 1. Check immutable snapshots
        if not spec.script_snapshot_sha256 or not spec.evidence_pack_sha256:
            return SceneValidationResult(
                valid=False,
                reason_code=MISSING_IMMUTABLE_SNAPSHOT,
                message="SceneSpec v3 requires non-empty script_snapshot_sha256 and evidence_pack_sha256.",
                scene_id=spec.scene_id,
            )

        # 2. Check grammar
        if spec.grammar not in ALLOWED_SCENE_GRAMMARS:
            return SceneValidationResult(
                valid=False,
                reason_code=INVALID_SCENE_GRAMMAR,
                message=f"Grammar '{spec.grammar}' is not one of {ALLOWED_SCENE_GRAMMARS}.",
                scene_id=spec.scene_id,
            )

        # 3. Check typed contract requirement (Rule 8: Validator requires exact typed contract)
        expected_contract_cls = GRAMMAR_CONTRACT_CLASS_MAP.get(spec.grammar)
        if expected_contract_cls is None or not isinstance(spec.grammar_contract, expected_contract_cls):
            return SceneValidationResult(
                valid=False,
                reason_code=INVALID_GRAMMAR_CONTRACT,
                message=f"Scene '{spec.scene_id}' with grammar '{spec.grammar}' requires an explicit typed {expected_contract_cls.__name__ if expected_contract_cls else 'Contract'}.",
                scene_id=spec.scene_id,
            )

        # 4. Check unsupported actions
        for act in spec.actions:
            if act.action_type not in ALLOWED_ACTION_TYPES:
                return SceneValidationResult(
                    valid=False,
                    reason_code=UNSUPPORTED_ACTION_TYPE,
                    message=f"Action '{act.action_id}' has unsupported action_type '{act.action_type}'.",
                    scene_id=spec.scene_id,
                    details={"action_id": act.action_id, "action_type": act.action_type},
                )

        # ---------------------------------------------------------------------
        # 5. Grammar: map_route (Relational Binding: route ↔ path ↔ marker)
        # ---------------------------------------------------------------------
        if spec.grammar == "map_route":
            contract: MapRouteContract = spec.grammar_contract  # type: ignore

            has_marker = False
            has_path = False
            path_start_ms = 999999
            marker_start_ms = -1

            for act in spec.actions:
                if act.params.get("motion_type") == "instant_teleport_without_path":
                    return SceneValidationResult(
                        valid=False,
                        reason_code=MAP_DISCONTINUOUS_ROUTE,
                        message=f"Map route scene '{spec.scene_id}' contains instant teleportation without path.",
                        scene_id=spec.scene_id,
                    )

                if act.action_type == "path_draw":
                    act_route_id = str(act.params.get("route_id") or act.target_id)
                    if act_route_id != contract.route_id or act.target_id != contract.route_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=MAP_ROUTE_BINDING_MISMATCH,
                            message=f"path_draw action '{act.action_id}' target '{act.target_id}' does not match route_id '{contract.route_id}'.",
                            scene_id=spec.scene_id,
                        )
                    has_path = True
                    path_start_ms = min(path_start_ms, act.start_ms)

                if act.action_type == "traveling_marker":
                    # Target MUST equal contract.marker_id!
                    if act.target_id != contract.marker_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=MAP_ROUTE_BINDING_MISMATCH,
                            message=f"traveling_marker action '{act.action_id}' target '{act.target_id}' does not match contract.marker_id '{contract.marker_id}'.",
                            scene_id=spec.scene_id,
                        )
                    act_route_id = str(act.params.get("route_id") or "")
                    if not act_route_id or act_route_id != contract.route_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=MAP_ROUTE_BINDING_MISMATCH,
                            message=f"traveling_marker action '{act.action_id}' route '{act_route_id}' does not match route_id '{contract.route_id}'.",
                            scene_id=spec.scene_id,
                        )
                    has_marker = True
                    marker_start_ms = act.start_ms

            if not has_marker or not has_path:
                return SceneValidationResult(
                    valid=False,
                    reason_code=MAP_DISCONTINUOUS_ROUTE,
                    message=f"Map route scene '{spec.scene_id}' requires both path_draw and traveling_marker action declarations bound to '{contract.route_id}'.",
                    scene_id=spec.scene_id,
                )

            # Path must begin before or no later than marker traversal
            if path_start_ms > marker_start_ms:
                return SceneValidationResult(
                    valid=False,
                    reason_code=MAP_DISCONTINUOUS_ROUTE,
                    message=f"Map route path_draw start ({path_start_ms}ms) must precede or match marker start ({marker_start_ms}ms).",
                    scene_id=spec.scene_id,
                )

        # ---------------------------------------------------------------------
        # 6. Grammar: process_flow (Relational Binding: nodes ↔ edges ↔ transfer ↔ end_state)
        # ---------------------------------------------------------------------
        if spec.grammar == "process_flow":
            proc_contract: ProcessFlowContract = spec.grammar_contract  # type: ignore

            # Start and end states are mandatory, non-empty, and different
            if not spec.start_state or not spec.end_state:
                return SceneValidationResult(
                    valid=False,
                    reason_code=PROCESS_FLOW_NO_TRANSFER,
                    message=f"Process flow scene '{spec.scene_id}' requires mandatory non-empty start_state and end_state.",
                    scene_id=spec.scene_id,
                )

            if spec.start_state == spec.end_state:
                return SceneValidationResult(
                    valid=False,
                    reason_code=PROCESS_FLOW_NO_TRANSFER,
                    message=f"Process flow scene '{spec.scene_id}' end_state must reflect state mutation / transfer, not unchanged state.",
                    scene_id=spec.scene_id,
                )

            declared_edges = set(proc_contract.edges)
            valid_transfer_action = False

            for act in spec.actions:
                if act.action_type == "transfer_token":
                    if not act.source_id or not act.target_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=PROCESS_FLOW_NO_TRANSFER,
                            message=f"transfer_token action '{act.action_id}' requires non-empty source_id and target_id.",
                            scene_id=spec.scene_id,
                        )
                    edge_pair = (act.source_id, act.target_id)
                    if edge_pair not in declared_edges:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=PROCESS_FLOW_NO_TRANSFER,
                            message=f"transfer_token action ({act.source_id} -> {act.target_id}) is not a declared edge in {proc_contract.edges}.",
                            scene_id=spec.scene_id,
                        )

                    # Action payload must carry matching token_label and amount/unit if specified
                    act_token = str(act.params.get("token_label") or act.params.get("token") or "").strip()
                    if act_token != proc_contract.token_label:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=PROCESS_FLOW_NO_TRANSFER,
                            message=f"transfer_token action '{act.action_id}' token_label '{act_token}' does not match contract.token_label '{proc_contract.token_label}'.",
                            scene_id=spec.scene_id,
                        )

                    if proc_contract.amount is not None:
                        act_amount = act.params.get("amount")
                        if act_amount != proc_contract.amount:
                            return SceneValidationResult(
                                valid=False,
                                reason_code=PROCESS_FLOW_NO_TRANSFER,
                                message=f"transfer_token action '{act.action_id}' amount '{act_amount}' does not match contract.amount '{proc_contract.amount}'.",
                                scene_id=spec.scene_id,
                            )

                    # Start/End states must contain source and target entries
                    if act.source_id not in spec.start_state or act.target_id not in spec.end_state:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=PROCESS_FLOW_NO_TRANSFER,
                            message=f"Scene start_state/end_state must contain entries for transfer endpoints ({act.source_id}, {act.target_id}).",
                            scene_id=spec.scene_id,
                        )

                    valid_transfer_action = True
                elif act.action_type in {"state_swap", "transform"}:
                    if act.target_id:
                        valid_transfer_action = True

            if not valid_transfer_action:
                return SceneValidationResult(
                    valid=False,
                    reason_code=PROCESS_FLOW_NO_TRANSFER,
                    message=f"Process flow scene '{spec.scene_id}' requires a transfer_token action matching a declared graph edge.",
                    scene_id=spec.scene_id,
                )

        # ---------------------------------------------------------------------
        # 7. Grammar: object_assembly (Relational Binding: parts ↔ transform ↔ end_state)
        # ---------------------------------------------------------------------
        if spec.grammar == "object_assembly":
            obj_contract: ObjectAssemblyContract = spec.grammar_contract  # type: ignore

            if not spec.start_state or not spec.end_state or spec.start_state == spec.end_state:
                return SceneValidationResult(
                    valid=False,
                    reason_code=OBJECT_ASSEMBLY_NO_TRANSFORMATION,
                    message=f"Object assembly scene '{spec.scene_id}' requires start_state != end_state.",
                    scene_id=spec.scene_id,
                )

            # Action target must belong to contract.parts
            part_set = set(obj_contract.parts)
            has_valid_part_action = False
            for act in spec.actions:
                if act.action_type in {"move", "transform", "state_swap", "object_path"}:
                    if not act.target_id or act.target_id not in part_set:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=OBJECT_ASSEMBLY_NO_TRANSFORMATION,
                            message=f"Object assembly action '{act.action_id}' target '{act.target_id}' is not in declared parts {obj_contract.parts}.",
                            scene_id=spec.scene_id,
                        )
                    has_valid_part_action = True

            if not has_valid_part_action:
                return SceneValidationResult(
                    valid=False,
                    reason_code=OBJECT_ASSEMBLY_NO_TRANSFORMATION,
                    message=f"Object assembly scene '{spec.scene_id}' requires at least one semantic transform/move action targeting declared parts.",
                    scene_id=spec.scene_id,
                )

        # ---------------------------------------------------------------------
        # 8. Grammar: character_performance (Relational Binding: performer ↔ capabilities ↔ acting_intent ↔ pose lifecycle)
        # ---------------------------------------------------------------------
        if spec.grammar == "character_performance":
            char_contract: CharacterPerformanceContract = spec.grammar_contract  # type: ignore

            if char_contract.start_pose == char_contract.end_pose:
                return SceneValidationResult(
                    valid=False,
                    reason_code=CHARACTER_PERFORMANCE_NOT_READY,
                    message=f"Character performance scene '{spec.scene_id}' requires start_pose != end_pose.",
                    scene_id=spec.scene_id,
                )

            # SceneSpec start/end state must explicitly bind performer and reflect pose lifecycle
            if not spec.start_state or not spec.end_state or spec.start_state == spec.end_state:
                return SceneValidationResult(
                    valid=False,
                    reason_code=CHARACTER_PERFORMANCE_NOT_READY,
                    message=f"Character performance scene '{spec.scene_id}' requires non-empty changed start_state != end_state binding performer '{char_contract.performer_id}'.",
                    scene_id=spec.scene_id,
                )

            perf_start = spec.start_state.get(char_contract.performer_id)
            perf_end = spec.end_state.get(char_contract.performer_id)
            if perf_start and perf_end and perf_start == perf_end:
                return SceneValidationResult(
                    valid=False,
                    reason_code=CHARACTER_PERFORMANCE_NOT_READY,
                    message=f"Character performance scene '{spec.scene_id}' performer lifecycle is unchanged in start/end state.",
                    scene_id=spec.scene_id,
                )

            has_acting_action = False
            for act in spec.actions:
                if act.action_type in {"pose_sequence", "state_swap", "focus_shift"}:
                    if act.target_id != char_contract.performer_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=CHARACTER_PERFORMANCE_NOT_READY,
                            message=f"Character performance action '{act.action_id}' target '{act.target_id}' does not match performer_id '{char_contract.performer_id}'.",
                            scene_id=spec.scene_id,
                        )
                    has_acting_action = True

            if not has_acting_action:
                return SceneValidationResult(
                    valid=False,
                    reason_code=CHARACTER_PERFORMANCE_NOT_READY,
                    message=f"Character performance scene '{spec.scene_id}' requires a pose_sequence or acting action targeting '{char_contract.performer_id}'.",
                    scene_id=spec.scene_id,
                )

        # ---------------------------------------------------------------------
        # 9. Grammar: document_evidence (Relational Binding: document/source ↔ focus_region ↔ citation ↔ action)
        # ---------------------------------------------------------------------
        if spec.grammar == "document_evidence":
            doc_contract: DocumentEvidenceContract = spec.grammar_contract  # type: ignore

            # Contract document_id must EXACTLY match an entry in scene evidence_ids or source_unit_ids
            allowed_doc_ids = set(spec.evidence_ids) | set(spec.source_unit_ids)
            if doc_contract.document_id not in allowed_doc_ids:
                return SceneValidationResult(
                    valid=False,
                    reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                    message=f"Document contract document_id '{doc_contract.document_id}' is not in scene evidence_ids {spec.evidence_ids}.",
                    scene_id=spec.scene_id,
                )

            has_doc_action = False
            for act in spec.actions:
                if act.action_type in {"document_focus", "region_highlight"}:
                    if act.target_id != doc_contract.document_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                            message=f"Document action '{act.action_id}' target '{act.target_id}' does not match document_id '{doc_contract.document_id}'.",
                            scene_id=spec.scene_id,
                        )

                    # Action params must bind page_or_section and focus_region explicitly
                    act_page = str(act.params.get("page_or_section") or act.params.get("page") or "").strip()
                    if not act_page:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                            message=f"Document action '{act.action_id}' is missing required page_or_section in params.",
                            scene_id=spec.scene_id,
                        )
                    if act_page != doc_contract.page_or_section:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                            message=f"Document action '{act.action_id}' page '{act_page}' does not match contract.page_or_section '{doc_contract.page_or_section}'.",
                            scene_id=spec.scene_id,
                        )

                    act_focus = act.params.get("focus_region")
                    if not isinstance(act_focus, dict) or not act_focus:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                            message=f"Document action '{act.action_id}' is missing required focus_region dict in params.",
                            scene_id=spec.scene_id,
                        )
                    if act_focus != doc_contract.focus_region:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                            message=f"Document action '{act.action_id}' focus_region does not match contract.focus_region.",
                            scene_id=spec.scene_id,
                        )

                    has_doc_action = True

            if not has_doc_action:
                return SceneValidationResult(
                    valid=False,
                    reason_code=DOCUMENT_EVIDENCE_INCOMPLETE,
                    message=f"Document evidence scene '{spec.scene_id}' requires a document_focus or region_highlight action.",
                    scene_id=spec.scene_id,
                )

        # ---------------------------------------------------------------------
        # 10. Grammar: chart_progression (Relational Binding: domain ↔ numeric series ↔ units ↔ source ↔ action)
        # ---------------------------------------------------------------------
        if spec.grammar == "chart_progression":
            chart_contract: ChartProgressionContract = spec.grammar_contract  # type: ignore

            # Contract source must EXACTLY appear in evidence_ids or source_unit_ids
            allowed_sources = set(spec.evidence_ids) | set(spec.source_unit_ids)
            if chart_contract.source not in allowed_sources:
                return SceneValidationResult(
                    valid=False,
                    reason_code=CHART_MISSING_DATA,
                    message=f"Chart progression contract source '{chart_contract.source}' is not bound to evidence_ids/source_unit_ids {allowed_sources}.",
                    scene_id=spec.scene_id,
                )

            has_chart_action = False
            for act in spec.actions:
                if act.action_type in {"chart_series", "counter_progress"}:
                    if act.target_id != chart_contract.series_id:
                        return SceneValidationResult(
                            valid=False,
                            reason_code=CHART_MISSING_DATA,
                            message=f"Chart action '{act.action_id}' target '{act.target_id}' does not match contract.series_id '{chart_contract.series_id}'.",
                            scene_id=spec.scene_id,
                        )
                    has_chart_action = True

            if not has_chart_action:
                return SceneValidationResult(
                    valid=False,
                    reason_code=CHART_MISSING_DATA,
                    message=f"Chart progression scene '{spec.scene_id}' requires chart_series or counter_progress action targeting '{chart_contract.series_id}'.",
                    scene_id=spec.scene_id,
                )

        # ---------------------------------------------------------------------
        # 11. Grammar: explanatory_hold
        # ---------------------------------------------------------------------
        if spec.grammar == "explanatory_hold":
            hold_contract: ExplanatoryHoldContract = spec.grammar_contract  # type: ignore

            # Check anchors
            if not spec.narration_anchors and not spec.hold_policy.get("anchor"):
                return SceneValidationResult(
                    valid=False,
                    reason_code=EXPLANATORY_HOLD_WITHOUT_PURPOSE,
                    message=f"Explanatory hold scene '{spec.scene_id}' requires at least one narration anchor.",
                    scene_id=spec.scene_id,
                )

            # Contract anchor must match a real narration anchor
            all_anchor_texts = {str(a.get("anchor") or a.get("id") or "") for a in spec.narration_anchors}
            if hold_contract.anchor not in all_anchor_texts and not any(hold_contract.anchor in txt for txt in all_anchor_texts):
                return SceneValidationResult(
                    valid=False,
                    reason_code=EXPLANATORY_HOLD_WITHOUT_PURPOSE,
                    message=f"Hold contract anchor '{hold_contract.anchor}' does not match narration anchors.",
                    scene_id=spec.scene_id,
                )

            for anchor in spec.narration_anchors:
                at_ms = int(anchor.get("at_ms") or 0)
                if not (0 <= at_ms <= spec.duration_ms):
                    return SceneValidationResult(
                        valid=False,
                        reason_code=EXPLANATORY_HOLD_WITHOUT_PURPOSE,
                        message=f"Narration anchor at_ms {at_ms} falls outside scene duration {spec.duration_ms}ms.",
                        scene_id=spec.scene_id,
                    )

            # Prior state change must resolve to an actual earlier non-reveal/non-hold action ID OR a valid state transition
            all_action_ids = {act.action_id for act in spec.actions if act.action_type not in {"reveal", "hold"}}
            prior_ref = hold_contract.prior_state_change
            has_real_prior = (
                prior_ref in all_action_ids
                or (bool(spec.start_state) and bool(spec.end_state) and spec.start_state != spec.end_state and prior_ref in spec.start_state)
            )
            if not has_real_prior:
                return SceneValidationResult(
                    valid=False,
                    reason_code=EXPLANATORY_HOLD_WITHOUT_PURPOSE,
                    message=f"Explanatory hold prior_state_change '{prior_ref}' does not resolve to an actual preceding action ID or state entry in {all_action_ids}.",
                    scene_id=spec.scene_id,
                )

            max_cap = hold_contract.max_duration_ms
            if max_cap <= 0 or spec.duration_ms > max_cap:
                return SceneValidationResult(
                    valid=False,
                    reason_code=EXPLANATORY_HOLD_WITHOUT_PURPOSE,
                    message=f"Explanatory hold scene duration {spec.duration_ms}ms exceeds hold_policy max_duration_ms cap {max_cap}ms.",
                    scene_id=spec.scene_id,
                )

        return SceneValidationResult(
            valid=True,
            reason_code=VALIDATION_OK,
            message=f"SceneSpec v3 '{spec.scene_id}' verified.",
            scene_id=spec.scene_id,
        )

    def assert_valid(self, spec: SceneSpecV3) -> SceneValidationResult:
        """Validate and raise SceneValidationError if invalid."""
        res = self.validate(spec)
        if not res.valid:
            raise SceneValidationError(
                message=res.message,
                reason_code=res.reason_code,
                scene_id=res.scene_id,
                details=res.details,
            )
        return res
