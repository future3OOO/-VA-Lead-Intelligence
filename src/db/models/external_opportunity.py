import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ExternalOpportunity(Base):
    """Explicit work posting with unresolved client.."""

    __tablename__ = "external_opportunity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace.id"), index=True
    )
    source_hit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_hit.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(255))
    external_opportunity_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    buyer_intent_label: Mapped[str] = mapped_column(String(255), default="unresolved")
    budget_hint: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(255), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


__all__ = ["ExternalOpportunity"]
