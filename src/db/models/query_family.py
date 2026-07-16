import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class QueryFamily(Base):
    """Versioned query set for source discovery.."""

    __tablename__ = "query_family"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace.id"), index=True
    )
    family_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(255))
    positive_titles: Mapped[list[str]] = mapped_column(JSON)
    positive_task_phrases: Mapped[list[str]] = mapped_column(JSON)
    negative_terms: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


__all__ = ["QueryFamily"]
