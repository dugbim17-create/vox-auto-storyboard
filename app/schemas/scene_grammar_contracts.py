"""Typed Relational Grammar Contracts for SceneSpec v3 (Phase 2B Correction 2 Final).

Defines explicit typed dataclass contracts for each of the 7 core grammars:
- MapRouteContract (route ↔ path ↔ marker ↔ coordinate/uncertainty authority)
- ProcessFlowContract (nodes ↔ edges ↔ transfer ↔ token/value ↔ end_state)
- ObjectAssemblyContract (parts ↔ transform ↔ assembly lifecycle)
- CharacterPerformanceContract (performer ↔ capabilities ↔ acting intent ↔ pose lifecycle)
- DocumentEvidenceContract (document/source ↔ page/section ↔ focus_region ↔ citation ↔ action)
- ChartProgressionContract (domain ↔ numeric series >=2 points ↔ units ↔ source ↔ action)
- ExplanatoryHoldContract (purpose ↔ prior change ↔ narration anchor ↔ duration cap)

CRITICAL: Never invent relational authority in from_dict / factories.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


class GrammarContractError(ValueError):
    """Raised when a relational grammar contract is invalid."""

    def __init__(self, message: str, reason_code: str = "INVALID_GRAMMAR_CONTRACT") -> None:
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message


def _is_strict_number(val: Any) -> bool:
    """Check if value is an int or float, strictly excluding bool."""
    if isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return not (math.isnan(val) or math.isinf(val))


def _check_unique_non_empty_ids(items: tuple[str, ...], name: str, reason_code: str) -> None:
    """Check that collection has non-empty unique string IDs."""
    seen: set[str] = set()
    for item in items:
        s = str(item).strip()
        if not s:
            raise GrammarContractError(f"{name} cannot contain empty strings", reason_code=reason_code)
        if s in seen:
            raise GrammarContractError(f"Duplicate entry '{s}' in {name}", reason_code=reason_code)
        seen.add(s)


@dataclass(frozen=True)
class MapRouteContract:
    """Relational contract for map_route scenes."""

    route_id: str
    marker_id: str
    declared_polyline: tuple[tuple[float, float], ...]
    continuous_path: bool = True
    coordinate_authority: str = "wgs84_projected"
    uncertainty_policy: str = "none"
    origin_label: str = ""
    destination_label: str = ""

    def __post_init__(self) -> None:
        if not self.route_id or not str(self.route_id).strip():
            raise GrammarContractError("route_id is required for map_route", reason_code="MAP_DISCONTINUOUS_ROUTE")

        if not self.marker_id or not str(self.marker_id).strip():
            raise GrammarContractError("marker_id is required for map_route", reason_code="MAP_DISCONTINUOUS_ROUTE")

        if not self.coordinate_authority or not str(self.coordinate_authority).strip():
            raise GrammarContractError("coordinate_authority is required for map_route", reason_code="MAP_DISCONTINUOUS_ROUTE")

        if not self.uncertainty_policy or not str(self.uncertainty_policy).strip():
            raise GrammarContractError("uncertainty_policy is required for map_route", reason_code="MAP_DISCONTINUOUS_ROUTE")

        if not self.continuous_path:
            raise GrammarContractError("continuous_path must be True for map_route", reason_code="MAP_DISCONTINUOUS_ROUTE")

        if not isinstance(self.declared_polyline, (list, tuple)) or len(self.declared_polyline) < 2:
            raise GrammarContractError("declared_polyline must have at least 2 coordinate points", reason_code="MAP_DISCONTINUOUS_ROUTE")

        norm_poly: list[tuple[float, float]] = []
        for pt in self.declared_polyline:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                raise GrammarContractError(f"Invalid polyline point {pt}", reason_code="MAP_DISCONTINUOUS_ROUTE")
            x, y = pt[0], pt[1]
            if not _is_strict_number(x) or not _is_strict_number(y):
                raise GrammarContractError(f"Non-numeric/bool coordinate in point {pt}", reason_code="MAP_DISCONTINUOUS_ROUTE")
            norm_poly.append((float(x), float(y)))

        object.__setattr__(self, "declared_polyline", tuple(norm_poly))

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "marker_id": self.marker_id,
            "declared_polyline": [list(pt) for pt in self.declared_polyline],
            "continuous_path": self.continuous_path,
            "coordinate_authority": self.coordinate_authority,
            "uncertainty_policy": self.uncertainty_policy,
            "origin_label": self.origin_label,
            "destination_label": self.destination_label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapRouteContract:
        if not isinstance(data, dict):
            raise GrammarContractError("MapRouteContract data must be a dict", reason_code="MAP_DISCONTINUOUS_ROUTE")

        route_id = str(data.get("route_id") or "").strip()
        marker_id = str(data.get("marker_id") or data.get("target_marker") or data.get("marker") or "").strip()
        coord_auth = str(data.get("coordinate_authority") or "").strip()
        uncert = str(data.get("uncertainty_policy") or "").strip()

        if not route_id:
            raise GrammarContractError("route_id is required in MapRouteContract", reason_code="MAP_DISCONTINUOUS_ROUTE")
        if not marker_id:
            raise GrammarContractError("marker_id is required in MapRouteContract", reason_code="MAP_DISCONTINUOUS_ROUTE")
        if not coord_auth:
            raise GrammarContractError("coordinate_authority is required in MapRouteContract", reason_code="MAP_DISCONTINUOUS_ROUTE")
        if not uncert:
            raise GrammarContractError("uncertainty_policy is required in MapRouteContract", reason_code="MAP_DISCONTINUOUS_ROUTE")

        return cls(
            route_id=route_id,
            marker_id=marker_id,
            declared_polyline=tuple(data.get("declared_polyline") or ()),
            continuous_path=bool(data.get("continuous_path", True)),
            coordinate_authority=coord_auth,
            uncertainty_policy=uncert,
            origin_label=str(data.get("origin_label") or ""),
            destination_label=str(data.get("destination_label") or ""),
        )


@dataclass(frozen=True)
class ProcessFlowContract:
    """Relational contract for process_flow scenes."""

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    token_label: str
    has_direction: bool = True
    has_token_transfer: bool = True
    has_state_mutation: bool = False
    amount: float | int | None = None
    unit: str = ""

    def __post_init__(self) -> None:
        if not self.nodes:
            raise GrammarContractError("ProcessFlowContract requires non-empty nodes list", reason_code="PROCESS_FLOW_NO_TRANSFER")
        _check_unique_non_empty_ids(self.nodes, "nodes", "PROCESS_FLOW_NO_TRANSFER")

        if not self.edges:
            raise GrammarContractError("ProcessFlowContract requires non-empty edges list", reason_code="PROCESS_FLOW_NO_TRANSFER")
        if not self.has_direction:
            raise GrammarContractError("has_direction must be True for process_flow", reason_code="PROCESS_FLOW_NO_TRANSFER")
        if not (self.has_token_transfer or self.has_state_mutation):
            raise GrammarContractError("Process flow requires token transfer or state mutation", reason_code="PROCESS_FLOW_NO_TRANSFER")

        if self.has_token_transfer and (not self.token_label or not str(self.token_label).strip()):
            raise GrammarContractError("token_label is required when has_token_transfer=True", reason_code="PROCESS_FLOW_NO_TRANSFER")

        # Validate amount and unit if amount or unit is provided
        if self.amount is not None:
            if not _is_strict_number(self.amount):
                raise GrammarContractError("amount must be a numeric value, strictly non-bool", reason_code="PROCESS_FLOW_NO_TRANSFER")
            if not self.unit or not str(self.unit).strip():
                raise GrammarContractError("unit is required when amount is specified", reason_code="PROCESS_FLOW_NO_TRANSFER")

        # Validate that edge endpoints exist in nodes and no self-loops
        node_set = set(self.nodes)
        norm_edges: list[tuple[str, str]] = []
        for edge in self.edges:
            if not isinstance(edge, (list, tuple)) or len(edge) < 2:
                raise GrammarContractError(f"Invalid edge format {edge}", reason_code="PROCESS_FLOW_NO_TRANSFER")
            src, dst = str(edge[0]).strip(), str(edge[1]).strip()
            if not src or not dst:
                raise GrammarContractError(f"Edge {edge} has empty source or target", reason_code="PROCESS_FLOW_NO_TRANSFER")
            if src not in node_set or dst not in node_set:
                raise GrammarContractError(f"Edge {edge} references undeclared nodes outside {self.nodes}", reason_code="PROCESS_FLOW_NO_TRANSFER")
            if src == dst:
                raise GrammarContractError(f"Self-loop edge ({src}, {dst}) is rejected in process_flow", reason_code="PROCESS_FLOW_NO_TRANSFER")
            norm_edges.append((src, dst))

        object.__setattr__(self, "nodes", tuple(str(n).strip() for n in self.nodes))
        object.__setattr__(self, "edges", tuple(norm_edges))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "edges": [list(e) for e in self.edges],
            "token_label": self.token_label,
            "has_direction": self.has_direction,
            "has_token_transfer": self.has_token_transfer,
            "has_state_mutation": self.has_state_mutation,
            "amount": self.amount,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProcessFlowContract:
        if not isinstance(data, dict):
            raise GrammarContractError("ProcessFlowContract data must be a dict", reason_code="PROCESS_FLOW_NO_TRANSFER")

        nodes_raw = data.get("nodes")
        edges_raw = data.get("edges")
        token_lbl = str(data.get("token_label") or data.get("token") or "").strip()

        if not nodes_raw:
            raise GrammarContractError("ProcessFlowContract requires explicit non-empty 'nodes' list", reason_code="PROCESS_FLOW_NO_TRANSFER")
        if not edges_raw:
            raise GrammarContractError("ProcessFlowContract requires explicit non-empty 'edges' list", reason_code="PROCESS_FLOW_NO_TRANSFER")

        has_transfer = bool(data.get("has_token_transfer", True))
        if has_transfer and not token_lbl:
            raise GrammarContractError("token_label is required in ProcessFlowContract when has_token_transfer=True", reason_code="PROCESS_FLOW_NO_TRANSFER")

        amount_val = data.get("amount")
        if amount_val is not None and not _is_strict_number(amount_val):
            raise GrammarContractError("amount must be a numeric value, strictly non-bool", reason_code="PROCESS_FLOW_NO_TRANSFER")

        unit_val = str(data.get("unit") or "").strip()
        if amount_val is not None and not unit_val:
            raise GrammarContractError("unit is required when amount is specified in ProcessFlowContract", reason_code="PROCESS_FLOW_NO_TRANSFER")

        return cls(
            nodes=tuple(nodes_raw),
            edges=tuple(edges_raw),
            token_label=token_lbl,
            has_direction=bool(data.get("has_direction", True)),
            has_token_transfer=has_transfer,
            has_state_mutation=bool(data.get("has_state_mutation", False)),
            amount=amount_val,
            unit=unit_val,
        )


@dataclass(frozen=True)
class ObjectAssemblyContract:
    """Relational contract for object_assembly scenes."""

    parts: tuple[str, ...]
    assembly_intent: str
    start_configuration: str
    end_configuration: str

    def __post_init__(self) -> None:
        if not self.parts:
            raise GrammarContractError("ObjectAssemblyContract requires declared parts", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")
        _check_unique_non_empty_ids(self.parts, "parts", "OBJECT_ASSEMBLY_NO_TRANSFORMATION")

        if not self.assembly_intent or not str(self.assembly_intent).strip():
            raise GrammarContractError("assembly_intent is required", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")
        if not self.start_configuration or not str(self.start_configuration).strip():
            raise GrammarContractError("start_configuration is required", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")
        if not self.end_configuration or not str(self.end_configuration).strip():
            raise GrammarContractError("end_configuration is required", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")
        if self.start_configuration == self.end_configuration:
            raise GrammarContractError("start_configuration must differ from end_configuration", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")

        object.__setattr__(self, "parts", tuple(str(p).strip() for p in self.parts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parts": list(self.parts),
            "assembly_intent": self.assembly_intent,
            "start_configuration": self.start_configuration,
            "end_configuration": self.end_configuration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObjectAssemblyContract:
        if not isinstance(data, dict):
            raise GrammarContractError("ObjectAssemblyContract data must be a dict", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")

        parts = data.get("parts")
        if not parts:
            raise GrammarContractError("parts list is required in ObjectAssemblyContract", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")

        intent = str(data.get("assembly_intent") or "").strip()
        start_cfg = str(data.get("start_configuration") or "").strip()
        end_cfg = str(data.get("end_configuration") or "").strip()

        if not intent:
            raise GrammarContractError("assembly_intent is required in ObjectAssemblyContract", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")
        if not start_cfg:
            raise GrammarContractError("start_configuration is required in ObjectAssemblyContract", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")
        if not end_cfg:
            raise GrammarContractError("end_configuration is required in ObjectAssemblyContract", reason_code="OBJECT_ASSEMBLY_NO_TRANSFORMATION")

        return cls(
            parts=tuple(parts),
            assembly_intent=intent,
            start_configuration=start_cfg,
            end_configuration=end_cfg,
        )


@dataclass(frozen=True)
class CharacterPerformanceContract:
    """Relational contract for character_performance scenes."""

    performer_id: str
    capabilities: tuple[str, ...]
    acting_intent: str
    start_pose: str
    end_pose: str

    def __post_init__(self) -> None:
        if not self.performer_id or not str(self.performer_id).strip():
            raise GrammarContractError("performer_id is required", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not self.capabilities:
            raise GrammarContractError("capabilities list is required", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        _check_unique_non_empty_ids(self.capabilities, "capabilities", "CHARACTER_PERFORMANCE_NOT_READY")

        if not self.acting_intent or not str(self.acting_intent).strip():
            raise GrammarContractError("acting_intent is required", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not self.start_pose or not str(self.start_pose).strip():
            raise GrammarContractError("start_pose is required", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not self.end_pose or not str(self.end_pose).strip():
            raise GrammarContractError("end_pose is required", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if self.start_pose == self.end_pose:
            raise GrammarContractError("start_pose must differ from end_pose for performance lifecycle", reason_code="CHARACTER_PERFORMANCE_NOT_READY")

        object.__setattr__(self, "capabilities", tuple(str(c).strip() for c in self.capabilities))

    def to_dict(self) -> dict[str, Any]:
        return {
            "performer_id": self.performer_id,
            "capabilities": list(self.capabilities),
            "acting_intent": self.acting_intent,
            "start_pose": self.start_pose,
            "end_pose": self.end_pose,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterPerformanceContract:
        if not isinstance(data, dict):
            raise GrammarContractError("CharacterPerformanceContract data must be a dict", reason_code="CHARACTER_PERFORMANCE_NOT_READY")

        performer_id = str(data.get("performer_id") or data.get("puppet_id") or "").strip()
        caps = data.get("capabilities")
        intent = str(data.get("acting_intent") or "").strip()
        start_p = str(data.get("start_pose") or "").strip()
        end_p = str(data.get("end_pose") or "").strip()

        if not performer_id:
            raise GrammarContractError("performer_id is required in CharacterPerformanceContract", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not caps:
            raise GrammarContractError("capabilities list is required in CharacterPerformanceContract (ready=True cannot substitute)", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not intent:
            raise GrammarContractError("acting_intent is required in CharacterPerformanceContract", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not start_p:
            raise GrammarContractError("start_pose is required in CharacterPerformanceContract", reason_code="CHARACTER_PERFORMANCE_NOT_READY")
        if not end_p:
            raise GrammarContractError("end_pose is required in CharacterPerformanceContract", reason_code="CHARACTER_PERFORMANCE_NOT_READY")

        return cls(
            performer_id=performer_id,
            capabilities=tuple(caps),
            acting_intent=intent,
            start_pose=start_p,
            end_pose=end_p,
        )


@dataclass(frozen=True)
class DocumentEvidenceContract:
    """Relational contract for document_evidence scenes."""

    document_id: str
    page_or_section: str
    focus_region: dict[str, Any]
    citation: str
    display_policy: str = "overlay_highlight"

    def __post_init__(self) -> None:
        if not self.document_id or not str(self.document_id).strip():
            raise GrammarContractError("document_id is required", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not self.page_or_section or not str(self.page_or_section).strip():
            raise GrammarContractError("page_or_section is required", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not self.focus_region or not isinstance(self.focus_region, dict):
            raise GrammarContractError("focus_region dict is required", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not self.citation or not str(self.citation).strip():
            raise GrammarContractError("citation is required", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not self.display_policy or not str(self.display_policy).strip():
            raise GrammarContractError("display_policy is required", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_or_section": self.page_or_section,
            "focus_region": dict(self.focus_region),
            "citation": self.citation,
            "display_policy": self.display_policy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentEvidenceContract:
        if not isinstance(data, dict):
            raise GrammarContractError("DocumentEvidenceContract data must be a dict", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")

        doc_id = str(data.get("document_id") or "").strip()
        page_sec = str(data.get("page_or_section") or "").strip()
        focus_reg = data.get("focus_region")
        cit = str(data.get("citation") or "").strip()
        disp_pol = str(data.get("display_policy") or "").strip()

        if not doc_id:
            raise GrammarContractError("document_id is required in DocumentEvidenceContract", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not page_sec:
            raise GrammarContractError("page_or_section is required in DocumentEvidenceContract (no page_1 default allowed)", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not focus_reg or not isinstance(focus_reg, dict):
            raise GrammarContractError("focus_region dict is required in DocumentEvidenceContract", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not cit:
            raise GrammarContractError("citation is required in DocumentEvidenceContract", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")
        if not disp_pol:
            raise GrammarContractError("display_policy is required in DocumentEvidenceContract", reason_code="DOCUMENT_EVIDENCE_INCOMPLETE")

        return cls(
            document_id=doc_id,
            page_or_section=page_sec,
            focus_region=dict(focus_reg),
            citation=cit,
            display_policy=disp_pol,
        )


@dataclass(frozen=True)
class ChartProgressionContract:
    """Relational contract for chart_progression scenes."""

    domain: str
    series_id: str
    series: tuple[float | int, ...]
    units: str
    source: str
    progression_intent: str

    def __post_init__(self) -> None:
        if not self.domain or not str(self.domain).strip():
            raise GrammarContractError("domain is required for chart_progression", reason_code="CHART_MISSING_DATA")
        if not self.series_id or not str(self.series_id).strip():
            raise GrammarContractError("series_id is required for chart_progression", reason_code="CHART_MISSING_DATA")
        if not isinstance(self.series, (list, tuple)) or len(self.series) < 2:
            raise GrammarContractError("series must have at least 2 numeric values", reason_code="CHART_MISSING_DATA")
        for val in self.series:
            if not _is_strict_number(val):
                raise GrammarContractError(f"Non-numeric/bool value in series: {val}", reason_code="CHART_MISSING_DATA")
        if not self.units or not str(self.units).strip():
            raise GrammarContractError("units is required for chart_progression", reason_code="CHART_MISSING_DATA")
        if not self.source or not str(self.source).strip():
            raise GrammarContractError("source citation is required for chart_progression", reason_code="CHART_MISSING_DATA")
        if not self.progression_intent or not str(self.progression_intent).strip():
            raise GrammarContractError("progression_intent is required for chart_progression", reason_code="CHART_MISSING_DATA")

        object.__setattr__(self, "series", tuple(self.series))

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "series_id": self.series_id,
            "series": list(self.series),
            "units": self.units,
            "source": self.source,
            "progression_intent": self.progression_intent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartProgressionContract:
        if not isinstance(data, dict):
            raise GrammarContractError("ChartProgressionContract data must be a dict", reason_code="CHART_MISSING_DATA")

        dom = str(data.get("domain") or "").strip()
        series_id = str(data.get("series_id") or data.get("target_series") or "main_series").strip()
        series_raw = data.get("series")
        units = str(data.get("units") or "").strip()
        source = str(data.get("source") or "").strip()
        intent = str(data.get("progression_intent") or "").strip()

        if not dom:
            raise GrammarContractError("domain is required in ChartProgressionContract (no time_domain default allowed)", reason_code="CHART_MISSING_DATA")
        if not series_id:
            raise GrammarContractError("series_id is required in ChartProgressionContract", reason_code="CHART_MISSING_DATA")
        if not series_raw or not isinstance(series_raw, (list, tuple)):
            raise GrammarContractError("series list is required in ChartProgressionContract", reason_code="CHART_MISSING_DATA")
        if not units:
            raise GrammarContractError("units is required in ChartProgressionContract", reason_code="CHART_MISSING_DATA")
        if not source:
            raise GrammarContractError("source is required in ChartProgressionContract", reason_code="CHART_MISSING_DATA")
        if not intent:
            raise GrammarContractError("progression_intent is required in ChartProgressionContract", reason_code="CHART_MISSING_DATA")

        return cls(
            domain=dom,
            series_id=series_id,
            series=tuple(series_raw),
            units=units,
            source=source,
            progression_intent=intent,
        )


@dataclass(frozen=True)
class ExplanatoryHoldContract:
    """Relational contract for explanatory_hold scenes."""

    declared_purpose: str
    prior_state_change: str
    anchor: str
    max_duration_ms: int = 5000

    def __post_init__(self) -> None:
        if not self.declared_purpose or not str(self.declared_purpose).strip():
            raise GrammarContractError("declared_purpose is required for explanatory_hold", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")
        if not self.prior_state_change or not str(self.prior_state_change).strip():
            raise GrammarContractError("prior_state_change is required for explanatory_hold", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")
        if not self.anchor or not str(self.anchor).strip():
            raise GrammarContractError("anchor is required for explanatory_hold", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")
        if self.max_duration_ms <= 0:
            raise GrammarContractError("max_duration_ms must be positive", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")

    def to_dict(self) -> dict[str, Any]:
        return {
            "declared_purpose": self.declared_purpose,
            "prior_state_change": self.prior_state_change,
            "anchor": self.anchor,
            "max_duration_ms": self.max_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExplanatoryHoldContract:
        if not isinstance(data, dict):
            raise GrammarContractError("ExplanatoryHoldContract data must be a dict", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")

        purpose = str(data.get("declared_purpose") or "").strip()
        prior = str(data.get("prior_state_change") or "").strip()
        anchor = str(data.get("anchor") or "").strip()

        if not purpose:
            raise GrammarContractError("declared_purpose is required in ExplanatoryHoldContract", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")
        if not prior:
            raise GrammarContractError("prior_state_change is required in ExplanatoryHoldContract (no state_transition default allowed)", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")
        if not anchor:
            raise GrammarContractError("anchor is required in ExplanatoryHoldContract", reason_code="EXPLANATORY_HOLD_WITHOUT_PURPOSE")

        return cls(
            declared_purpose=purpose,
            prior_state_change=prior,
            anchor=anchor,
            max_duration_ms=int(data.get("max_duration_ms") or 5000),
        )


GrammarContractType = (
    MapRouteContract
    | ProcessFlowContract
    | ObjectAssemblyContract
    | CharacterPerformanceContract
    | DocumentEvidenceContract
    | ChartProgressionContract
    | ExplanatoryHoldContract
)
