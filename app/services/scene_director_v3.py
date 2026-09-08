"""SceneDirectorV3 service for planning, validating, and persisting SceneSpec v3 (Phase 2B Correction 1).

Orchestrates semantic visual planning:
- Complete input request envelope fingerprinting and in-process deduplication across identical planning requests
- Atomic manifest persistence via temporary file replace
- Tamper-detection on load (verifies spec_sha256 and planning_fingerprint against actual content and path)
- Fail-closed validation via SceneSpecValidator
- Production planning route join
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.schemas.scene_grammar_contracts import GrammarContractType
from app.schemas.scene_spec_v3 import (
    SceneAction,
    SceneSpecV3,
    compute_scene_spec_hash,
)
from app.schemas.story_evidence import StoryEvidencePack
from app.services.scene_spec_validator import SceneSpecValidator

SPEC_INTEGRITY_MISMATCH = "SPEC_INTEGRITY_MISMATCH"


class SceneDirectorV3Error(ValueError):
    """Raised when SceneDirectorV3 fails to plan, validate, or load a scene."""

    def __init__(self, message: str, reason_code: str = "DIRECTOR_ERROR") -> None:
        super().__init__(f"[{reason_code}] {message}")
        self.reason_code = reason_code
        self.message = message


def compute_planning_fingerprint(
    *,
    project_id: str,
    scene_id: str,
    script_snapshot_sha256: str,
    evidence_pack_sha256: str,
    grammar: str,
    visual_thesis: str = "",
    duration_ms: int = 4000,
    purpose: str = "body",
    source_unit_ids: list[str] | tuple[str, ...] | None = None,
    evidence_ids: list[str] | tuple[str, ...] | None = None,
    must_show: list[str] | tuple[str, ...] | None = None,
    must_not_invent: list[str] | tuple[str, ...] | None = None,
    asset_requirements: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    authority_order: list[str] | tuple[str, ...] | None = None,
    narration_anchors: list[Any] | tuple[Any, ...] | None = None,
    actions: list[Any] | tuple[Any, ...] | None = None,
    grammar_contract: Any = None,
    params: dict[str, Any] | None = None,
    start_state: dict[str, Any] | None = None,
    end_state: dict[str, Any] | None = None,
    hold_policy: dict[str, Any] | None = None,
    exit_policy: dict[str, Any] | None = None,
    composition: dict[str, Any] | None = None,
    continuity_in: dict[str, Any] | None = None,
    continuity_out: dict[str, Any] | None = None,
    renderer_profile: str = "vox_classic",
    seed_policy: dict[str, Any] | None = None,
    fps: int = 30,
    motion_fps: int = 12,
    planner_version: str = "v3.0",
) -> str:
    """Compute deterministic fingerprint covering the complete approved planning request envelope (F5)."""
    actions_list = [a.to_dict() if hasattr(a, "to_dict") else a for a in (actions or [])]
    actions_json = json.dumps(actions_list, sort_keys=True, ensure_ascii=False)

    contract_dict = grammar_contract.to_dict() if hasattr(grammar_contract, "to_dict") else (grammar_contract or {})
    contract_json = json.dumps(contract_dict, sort_keys=True, ensure_ascii=False)
    params_json = json.dumps(params or {}, sort_keys=True, ensure_ascii=False)

    sources_json = json.dumps(list(source_unit_ids or []), sort_keys=True, ensure_ascii=False)
    evidence_json = json.dumps(list(evidence_ids or []), sort_keys=True, ensure_ascii=False)
    must_show_json = json.dumps(list(must_show or []), sort_keys=True, ensure_ascii=False)
    must_not_json = json.dumps(list(must_not_invent or []), sort_keys=True, ensure_ascii=False)
    assets_json = json.dumps(list(asset_requirements or []), sort_keys=True, ensure_ascii=False)
    eff_authority = list(authority_order or ("source_verified", "procedural", "licensed_search", "ai_generated"))
    authority_json = json.dumps(eff_authority, sort_keys=True, ensure_ascii=False)
    anchors_json = json.dumps(list(narration_anchors or []), sort_keys=True, ensure_ascii=False)

    start_json = json.dumps(start_state or {}, sort_keys=True, ensure_ascii=False)
    end_json = json.dumps(end_state or {}, sort_keys=True, ensure_ascii=False)
    hold_json = json.dumps(hold_policy or {}, sort_keys=True, ensure_ascii=False)
    exit_json = json.dumps(exit_policy or {}, sort_keys=True, ensure_ascii=False)
    comp_json = json.dumps(composition or {}, sort_keys=True, ensure_ascii=False)
    cont_in_json = json.dumps(continuity_in or {}, sort_keys=True, ensure_ascii=False)
    cont_out_json = json.dumps(continuity_out or {}, sort_keys=True, ensure_ascii=False)
    seed_json = json.dumps(seed_policy or {}, sort_keys=True, ensure_ascii=False)

    eff_profile = str(renderer_profile or "vox_classic")
    eff_fps = int(fps or 30)
    eff_motion_fps = int(motion_fps or 12)
    eff_purpose = str(purpose or "body")

    raw = (
        f"{project_id}:{scene_id}:{script_snapshot_sha256}:{evidence_pack_sha256}:"
        f"{eff_purpose}:{grammar}:{visual_thesis}:{duration_ms}:"
        f"{sources_json}:{evidence_json}:{must_show_json}:{must_not_json}:{assets_json}:{authority_json}:{anchors_json}:"
        f"{actions_json}:{contract_json}:{params_json}:"
        f"{start_json}:{end_json}:{hold_json}:{exit_json}:{comp_json}:{cont_in_json}:{cont_out_json}:"
        f"{eff_profile}:{seed_json}:{eff_fps}:{eff_motion_fps}:{planner_version}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SceneDirectorV3:
    """Production service for directing, validating, and persisting SceneSpec v3."""

    def __init__(
        self,
        planner_provider: Any = None,
        storage_root: str | Path | None = None,
    ) -> None:
        self.planner_provider = planner_provider
        self.storage_root = Path(storage_root) if storage_root else Path(".hermes/evidence/vox-v3/phase2/scenes")
        self.validator = SceneSpecValidator()
        self._fingerprint_registry: dict[str, SceneSpecV3] = {}

    def compute_fingerprint(
        self,
        *,
        project_id: str,
        scene_id: str,
        script_text: str,
        evidence_pack: StoryEvidencePack,
        grammar: str,
        visual_thesis: str = "",
        duration_ms: int = 4000,
        purpose: str = "body",
        source_unit_ids: list[str] | tuple[str, ...] | None = None,
        evidence_ids: list[str] | tuple[str, ...] | None = None,
        must_show: list[str] | tuple[str, ...] | None = None,
        must_not_invent: list[str] | tuple[str, ...] | None = None,
        asset_requirements: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
        authority_order: list[str] | tuple[str, ...] | None = None,
        narration_anchors: list[Any] | tuple[Any, ...] | None = None,
        actions: list[Any] | None = None,
        grammar_contract: Any = None,
        params: dict[str, Any] | None = None,
        start_state: dict[str, Any] | None = None,
        end_state: dict[str, Any] | None = None,
        hold_policy: dict[str, Any] | None = None,
        exit_policy: dict[str, Any] | None = None,
        composition: dict[str, Any] | None = None,
        continuity_in: dict[str, Any] | None = None,
        continuity_out: dict[str, Any] | None = None,
        renderer_profile: str = "vox_classic",
        seed_policy: dict[str, Any] | None = None,
        fps: int = 30,
        motion_fps: int = 12,
        planner_version: str = "v3.0",
    ) -> str:
        """Compute fingerprint from script, evidence snapshots, and full visual parameters."""
        script_hash = hashlib.sha256(script_text.encode("utf-8")).hexdigest()
        evidence_hash = hashlib.sha256(json.dumps(evidence_pack.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()
        return compute_planning_fingerprint(
            project_id=project_id,
            scene_id=scene_id,
            script_snapshot_sha256=script_hash,
            evidence_pack_sha256=evidence_hash,
            purpose=purpose,
            grammar=grammar,
            visual_thesis=visual_thesis,
            duration_ms=duration_ms,
            source_unit_ids=source_unit_ids,
            evidence_ids=evidence_ids,
            must_show=must_show,
            must_not_invent=must_not_invent,
            asset_requirements=asset_requirements,
            authority_order=authority_order,
            narration_anchors=narration_anchors,
            actions=actions,
            grammar_contract=grammar_contract,
            params=params,
            start_state=start_state,
            end_state=end_state,
            hold_policy=hold_policy,
            exit_policy=exit_policy,
            composition=composition,
            continuity_in=continuity_in,
            continuity_out=continuity_out,
            renderer_profile=renderer_profile,
            seed_policy=seed_policy,
            fps=fps,
            motion_fps=motion_fps,
            planner_version=planner_version,
        )

    def plan_scene(
        self,
        *,
        project_id: str,
        scene_id: str,
        script_text: str,
        evidence_pack: StoryEvidencePack,
        grammar: str,
        visual_thesis: str,
        duration_ms: int = 4000,
        purpose: str = "body",
        source_unit_ids: tuple[str, ...] | list[str] | None = None,
        evidence_ids: tuple[str, ...] | list[str] | None = None,
        must_show: tuple[str, ...] | list[str] | None = None,
        must_not_invent: tuple[str, ...] | list[str] | None = None,
        asset_requirements: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
        authority_order: tuple[str, ...] | list[str] | None = None,
        narration_anchors: tuple[dict[str, Any], ...] | list[Any] | None = None,
        actions: list[SceneAction] | None = None,
        grammar_contract: GrammarContractType | None = None,
        params: dict[str, Any] | None = None,
        start_state: dict[str, Any] | None = None,
        end_state: dict[str, Any] | None = None,
        hold_policy: dict[str, Any] | None = None,
        exit_policy: dict[str, Any] | None = None,
        composition: dict[str, Any] | None = None,
        continuity_in: dict[str, Any] | None = None,
        continuity_out: dict[str, Any] | None = None,
        renderer_profile: str = "vox_classic",
        seed_policy: dict[str, Any] | None = None,
        fps: int = 30,
        motion_fps: int = 12,
        revision: int = 1,
    ) -> SceneSpecV3:
        """Create and validate a SceneSpec v3, reusing identical fingerprint if registered."""
        script_hash = hashlib.sha256(script_text.encode("utf-8")).hexdigest()
        evidence_hash = hashlib.sha256(json.dumps(evidence_pack.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()

        eff_evidence_ids = tuple(evidence_ids) if evidence_ids is not None else tuple(c.claim_id for c in evidence_pack.claims)

        fingerprint = compute_planning_fingerprint(
            project_id=project_id,
            scene_id=scene_id,
            script_snapshot_sha256=script_hash,
            evidence_pack_sha256=evidence_hash,
            purpose=purpose,
            grammar=grammar,
            visual_thesis=visual_thesis,
            duration_ms=duration_ms,
            source_unit_ids=source_unit_ids,
            evidence_ids=eff_evidence_ids,
            must_show=must_show,
            must_not_invent=must_not_invent,
            asset_requirements=asset_requirements,
            authority_order=authority_order,
            narration_anchors=narration_anchors,
            actions=actions,
            grammar_contract=grammar_contract,
            params=params,
            start_state=start_state,
            end_state=end_state,
            hold_policy=hold_policy,
            exit_policy=exit_policy,
            composition=composition,
            continuity_in=continuity_in,
            continuity_out=continuity_out,
            renderer_profile=renderer_profile,
            seed_policy=seed_policy,
            fps=fps,
            motion_fps=motion_fps,
        )

        if fingerprint in self._fingerprint_registry:
            return self._fingerprint_registry[fingerprint]

        spec = SceneSpecV3(
            project_id=project_id,
            scene_id=scene_id,
            revision=revision,
            script_snapshot_sha256=script_hash,
            evidence_pack_sha256=evidence_hash,
            source_unit_ids=tuple(source_unit_ids or []),
            evidence_ids=eff_evidence_ids,
            purpose=purpose,
            grammar=grammar,
            visual_thesis=visual_thesis,
            must_show=tuple(must_show or []),
            must_not_invent=tuple(must_not_invent or []),
            asset_requirements=tuple(asset_requirements or []),
            authority_order=tuple(authority_order or ("source_verified", "procedural", "licensed_search", "ai_generated")),
            narration_anchors=tuple(narration_anchors or []),
            duration_ms=duration_ms,
            actions=tuple(actions or []),
            grammar_contract=grammar_contract,
            params=dict(params or {}),
            start_state=dict(start_state or {}),
            end_state=dict(end_state or {}),
            hold_policy=dict(hold_policy or {}),
            exit_policy=dict(exit_policy or {}),
            composition=dict(composition or {}),
            continuity_in=dict(continuity_in or {}),
            continuity_out=dict(continuity_out or {}),
            renderer_profile=renderer_profile,
            seed_policy=dict(seed_policy or {}),
            fps=fps,
            motion_fps=motion_fps,
            planning_fingerprint=fingerprint,
        )

        self.validator.assert_valid(spec)
        self._fingerprint_registry[fingerprint] = spec
        return spec

    def persist_scene_spec(
        self,
        spec: SceneSpecV3,
        project_root: Path | None = None,
    ) -> Path:
        """Persist SceneSpec v3 manifest to disk atomically via temporary file replace."""
        root = project_root or self.storage_root
        target_dir = root / spec.project_id / "scenes" / spec.scene_id / f"rev_{spec.revision:03d}"
        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = target_dir / "scene_spec_v3.json"
        tmp_path = target_dir / f"scene_spec_v3.json.tmp_{os.getpid()}"

        content = json.dumps(spec.to_dict(), indent=2, ensure_ascii=False)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Atomic replace
        os.replace(tmp_path, manifest_path)
        return manifest_path

    def load_scene_spec(
        self,
        *,
        project_id: str,
        scene_id: str,
        revision: int = 1,
        project_root: Path | None = None,
    ) -> SceneSpecV3:
        """Load, verify hash integrity & fingerprint (tamper detection), and validate SceneSpec v3."""
        root = project_root or self.storage_root
        manifest_path = root / project_id / "scenes" / scene_id / f"rev_{revision:03d}" / "scene_spec_v3.json"
        if not manifest_path.is_file():
            raise SceneDirectorV3Error(
                f"SceneSpec manifest not found at {manifest_path}",
                reason_code="MANIFEST_NOT_FOUND",
            )

        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        # Path vs Content check
        if data.get("project_id") != project_id or data.get("scene_id") != scene_id or int(data.get("revision") or 1) != revision:
            raise SceneDirectorV3Error(
                f"Path parameter mismatch on {manifest_path}: content declares {data.get('project_id')}/{data.get('scene_id')}/rev_{data.get('revision')}.",
                reason_code=SPEC_INTEGRITY_MISMATCH,
            )

        stored_hash = str(data.get("spec_sha256") or "")
        computed_hash = compute_scene_spec_hash(data)
        if stored_hash != computed_hash:
            raise SceneDirectorV3Error(
                f"Persisted SceneSpec hash mismatch on {manifest_path} (stored={stored_hash} vs computed={computed_hash}). Manifest was modified or tampered.",
                reason_code=SPEC_INTEGRITY_MISMATCH,
            )

        spec = SceneSpecV3.from_dict(data)

        # Verify planning fingerprint integrity against recomputed envelope
        if spec.planning_fingerprint:
            expected_fingerprint = compute_planning_fingerprint(
                project_id=spec.project_id,
                scene_id=spec.scene_id,
                script_snapshot_sha256=spec.script_snapshot_sha256,
                evidence_pack_sha256=spec.evidence_pack_sha256,
                purpose=spec.purpose,
                grammar=spec.grammar,
                visual_thesis=spec.visual_thesis,
                duration_ms=spec.duration_ms,
                source_unit_ids=list(spec.source_unit_ids),
                evidence_ids=list(spec.evidence_ids),
                must_show=list(spec.must_show),
                must_not_invent=list(spec.must_not_invent),
                asset_requirements=list(spec.asset_requirements),
                authority_order=list(spec.authority_order),
                narration_anchors=list(spec.narration_anchors),
                actions=list(spec.actions),
                grammar_contract=spec.grammar_contract,
                params=spec.params,
                start_state=spec.start_state,
                end_state=spec.end_state,
                hold_policy=spec.hold_policy,
                exit_policy=spec.exit_policy,
                composition=spec.composition,
                continuity_in=spec.continuity_in,
                continuity_out=spec.continuity_out,
                renderer_profile=spec.renderer_profile,
                seed_policy=spec.seed_policy,
                fps=spec.fps,
                motion_fps=spec.motion_fps,
            )
            if spec.planning_fingerprint != expected_fingerprint:
                raise SceneDirectorV3Error(
                    f"Persisted SceneSpec planning_fingerprint mismatch on {manifest_path} (stored={spec.planning_fingerprint} vs expected={expected_fingerprint}).",
                    reason_code=SPEC_INTEGRITY_MISMATCH,
                )

        self.validator.assert_valid(spec)
        return spec
