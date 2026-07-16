import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SourceRegistry(Base):
    """Configured source adapter registration.."""

    __tablename__ = "source_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace.id"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(255))
    source_class: Mapped[str] = mapped_column(String(255))
    access_mode: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(255), default="enabled")
    owner: Mapped[str] = mapped_column(String(255))
    terms_review_status: Mapped[str] = mapped_column(String(255))
    terms_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    allowed_outputs: Mapped[Any] = mapped_column(JSON)
    allowed_fields: Mapped[Any] = mapped_column(JSON)
    raw_retention_days: Mapped[int] = mapped_column(Integer)
    normalized_retention_days: Mapped[int] = mapped_column(Integer)
    rate_limit: Mapped[dict[str, Any]] = mapped_column(JSON)
    kill_switch: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


__all__ = ["SourceRegistry"]
