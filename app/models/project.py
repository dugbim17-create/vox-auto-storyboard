"""Project ORM model (MASTER_PLAN section 6.1)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="INGESTED")
    script_source: Mapped[str] = mapped_column(String(512), default="")
    script_hash: Mapped[str] = mapped_column(String(64), default="")
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9")
    fps: Mapped[int] = mapped_column(default=30)
    style_preset: Mapped[str] = mapped_column(String(64), default="editorial_collage")
    image_provider: Mapped[str] = mapped_column(String(32), default="cliproxy")
    motion_tier: Mapped[str] = mapped_column(String(32), default="local")
    voice_profile_id: Mapped[str] = mapped_column(String(64), default="voice_vi_01")
    script_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
