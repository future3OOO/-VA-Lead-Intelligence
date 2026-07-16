import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SourceRun(Base):
    """Execution record for a source adapter run.."""

    __tablename__ = "source_run"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace.id"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign.id"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(255), default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hits_total: Mapped[int] = mapped_column(Integer)
    hits_qualified_total: Mapped[int] = mapped_column(Integer)
    hits_duplicate_total: Mapped[int] = mapped_column(Integer)
    errors_total: Mapped[int] = mapped_column(Integer)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = ["SourceRun"]
