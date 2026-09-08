"""Repository layer for CRUD over the SQLite store (P1-T02)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    Project,
    ProviderJob,
    QuizProject,
    RenderAttempt,
    Scene,
    StateEvent,
    VoiceProfile,
)
from app.schemas.quiz import validate_quiz_project


def _now() -> datetime:
    return datetime.now(UTC)


class ProjectRepo:
    @staticmethod
    def create(session: Session, *, project_id: str, **fields) -> Project:
        proj = Project(project_id=project_id, **fields)
        session.add(proj)
        return proj

    @staticmethod
    def get(session: Session, project_id: str) -> Project | None:
        return session.get(Project, project_id)

    @staticmethod
    def list(session: Session, limit: int = 100) -> list[Project]:
        return list(session.scalars(select(Project).order_by(Project.created_at.desc()).limit(limit)))

    @staticmethod
    def update_status(session: Session, project_id: str, status: str) -> Project | None:
        proj = session.get(Project, project_id)
        if proj is None:
            return None
        proj.status = status
        proj.updated_at = _now()
        return proj


class QuizProjectRepo:
    @staticmethod
    def upsert(session: Session, document: dict) -> QuizProject:
        validated = validate_quiz_project(document)
        project_id = str(validated.get("project_id") or "").strip()
        if not project_id:
            raise ValueError("quiz project_id is required")
        approval = validated.get("approval") or {}
        row = session.get(QuizProject, project_id)
        payload = json.dumps(validated, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fields = {
            "schema_version": str(validated["schema_version"]),
            "status": str(approval.get("status") or "draft"),
            "approval_fingerprint": approval.get("content_fingerprint"),
            "document_json": payload,
        }
        if row is None:
            row = QuizProject(quiz_project_id=project_id, **fields)
            session.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = _now()
        session.flush()
        return row

    @staticmethod
    def get_document(session: Session, project_id: str) -> dict | None:
        row = session.get(QuizProject, project_id)
        return json.loads(row.document_json) if row is not None else None


class SceneRepo:
    @staticmethod
    def add(session: Session, project_id: str, **fields) -> Scene:
        scene = Scene(project_id=project_id, **fields)
        session.add(scene)
        return scene

    @staticmethod
    def get(session: Session, project_id: str, scene_id: str) -> Scene | None:
        stmt = select(Scene).where(Scene.project_id == project_id, Scene.scene_id == scene_id)
        return session.scalars(stmt).first()

    @staticmethod
    def list(session: Session, project_id: str) -> list[Scene]:
        stmt = select(Scene).where(Scene.project_id == project_id).order_by(Scene.order)
        return list(session.scalars(stmt))

    @staticmethod
    def update_status(session: Session, project_id: str, scene_id: str, status: str) -> Scene | None:
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None:
            return None
        scene.status = status
        scene.updated_at = _now()
        return scene

    @staticmethod
    def update_image_prompt(session: Session, project_id: str, scene_id: str, prompt: str) -> Scene | None:
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None:
            return None
        scene.image_prompt = prompt.strip()
        scene.updated_at = _now()
        return scene

    @staticmethod
    def set_selected_image(session: Session, project_id: str, scene_id: str, asset_id: str | None) -> Scene | None:
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None:
            return None
        scene.selected_image_asset_id = asset_id
        scene.updated_at = _now()
        return scene


class AssetRepo:
    @staticmethod
    def add(session: Session, project_id: str, scene_id: str, **fields) -> Asset:
        asset = Asset(project_id=project_id, scene_id=scene_id, **fields)
        session.add(asset)
        return asset

    @staticmethod
    def upsert(session: Session, project_id: str, scene_id: str, **fields) -> Asset:
        cache_identity = str(fields.get("cache_identity") or "")
        existing = None
        if cache_identity:
            existing = session.scalars(
                select(Asset).where(
                    Asset.project_id == project_id,
                    Asset.scene_id == scene_id,
                    Asset.cache_identity == cache_identity,
                )
            ).first()
        if existing is None:
            existing = AssetRepo.get_by_asset_id(
                session, project_id, scene_id, str(fields["asset_id"])
            )
        if existing is None:
            return AssetRepo.add(session, project_id, scene_id, **fields)
        for key, value in fields.items():
            setattr(existing, key, value)
        session.flush()
        return existing

    @staticmethod
    def list(session: Session, project_id: str, scene_id: str | None = None) -> list[Asset]:
        stmt = select(Asset).where(Asset.project_id == project_id)
        if scene_id is not None:
            stmt = stmt.where(Asset.scene_id == scene_id)
        return list(session.scalars(stmt))

    @staticmethod
    def get_by_asset_id(session: Session, project_id: str, scene_id: str, asset_id: str) -> Asset | None:
        stmt = select(Asset).where(Asset.project_id == project_id, Asset.scene_id == scene_id, Asset.asset_id == asset_id)
        return session.scalars(stmt).first()

    @staticmethod
    def get_selected_for_scene(session: Session, project_id: str, scene_id: str) -> Asset | None:
        scene = SceneRepo.get(session, project_id, scene_id)
        if scene is None or not scene.selected_image_asset_id:
            return None
        asset = AssetRepo.get_by_asset_id(session, project_id, scene_id, scene.selected_image_asset_id)
        if asset is None or not asset.selected:
            return None
        return asset

    @staticmethod
    def set_selected(session: Session, asset_id: int, selected: bool) -> Asset | None:
        asset = session.get(Asset, asset_id)
        if asset is None:
            return None
        asset.selected = selected
        return asset

    @staticmethod
    def mark_scene_stale(session: Session, project_id: str, scene_id: str) -> int:
        assets = AssetRepo.list(session, project_id, scene_id)
        for asset in assets:
            asset.selected = False
        SceneRepo.set_selected_image(session, project_id, scene_id, None)
        return len(assets)


class StateEventRepo:
    @staticmethod
    def record(session: Session, *, project_id: str, to_state: str, from_state: str = "", scene_id: str | None = None, reason: str = "") -> StateEvent:
        event = StateEvent(project_id=project_id, scene_id=scene_id, from_state=from_state, to_state=to_state, reason=reason)
        session.add(event)
        return event

    @staticmethod
    def list(session: Session, project_id: str, limit: int = 200) -> list[StateEvent]:
        stmt = select(StateEvent).where(StateEvent.project_id == project_id).order_by(StateEvent.created_at).limit(limit)
        return list(session.scalars(stmt))


class ProviderJobRepo:
    @staticmethod
    def add(session: Session, project_id: str, scene_id: str, **fields) -> ProviderJob:
        job = ProviderJob(project_id=project_id, scene_id=scene_id, **fields)
        session.add(job)
        return job

    @staticmethod
    def update_status(session: Session, job_id: int, status: str, error: str = "") -> ProviderJob | None:
        job = session.get(ProviderJob, job_id)
        if job is None:
            return None
        job.status = status
        if error:
            job.error = error
        job.updated_at = _now()
        return job


class RenderAttemptRepo:
    @staticmethod
    def add(session: Session, project_id: str, scene_id: str, **fields) -> RenderAttempt:
        attempt = RenderAttempt(project_id=project_id, scene_id=scene_id, **fields)
        session.add(attempt)
        return attempt

    @staticmethod
    def update_status(session: Session, attempt_id: int, status: str, error: str = "") -> RenderAttempt | None:
        attempt = session.get(RenderAttempt, attempt_id)
        if attempt is None:
            return None
        attempt.status = status
        if error:
            attempt.error = error
        return attempt

    @staticmethod
    def mark_scene_stale(session: Session, project_id: str, scene_id: str) -> int:
        stmt = select(RenderAttempt).where(RenderAttempt.project_id == project_id, RenderAttempt.scene_id == scene_id, RenderAttempt.kind == "scene")
        attempts = list(session.scalars(stmt))
        for attempt in attempts:
            if attempt.status in {"succeeded", "completed", "validated"}:
                attempt.status = "stale"
        return len(attempts)


class VoiceProfileRepo:
    @staticmethod
    def upsert(session: Session, **fields) -> VoiceProfile:
        profile_id = fields.get("voice_profile_id")
        if not profile_id:
            raise ValueError("voice_profile_id is required")
        existing = session.scalars(select(VoiceProfile).where(VoiceProfile.voice_profile_id == profile_id)).first()
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            return existing
        profile = VoiceProfile(**fields)
        session.add(profile)
        return profile

    @staticmethod
    def get(session: Session, profile_id: str) -> VoiceProfile | None:
        return session.scalars(select(VoiceProfile).where(VoiceProfile.voice_profile_id == profile_id)).first()

    @staticmethod
    def list(session: Session) -> list[VoiceProfile]:
        return list(session.scalars(select(VoiceProfile).order_by(VoiceProfile.voice_profile_id)))
