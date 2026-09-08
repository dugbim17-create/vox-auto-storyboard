"""Scene ORM model (MASTER_PLAN section 6.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), index=True)
    scene_id: Mapped[str] = mapped_column(String(64), index=True)
    order: Mapped[int] = mapped_column(default=1)
    script_start_char: Mapped[int] = mapped_column(default=0)
    script_end_char: Mapped[int] = mapped_column(default=0)
    narration_text: Mapped[str] = mapped_column(Text, default="")
    purpose: Mapped[str] = mapped_column(String(64), default="")
    estimated_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    actual_voice_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_summary: Mapped[str] = mapped_column(Text, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_constraints: Mapped[str] = mapped_column(Text, default="")  # JSON list
    motion_prompt: Mapped[str] = mapped_column(Text, default="")
    motion_template: Mapped[str] = mapped_column(String(128), default="")
    transition_out: Mapped[str] = mapped_column(String(64), default="hard_cut")
    status: Mapped[str] = mapped_column(String(32), default="PLANNED")
    selected_image_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_motion_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project = relationship("Project", back_populates="scenes")
