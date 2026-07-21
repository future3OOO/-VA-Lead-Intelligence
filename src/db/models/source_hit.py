import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class SourceHit(Base):
    """Normalized record from a source adapter.."""

    __tablename__ = "source_hit"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "source_key", "content_hash", name="uq_source_hit_content_hash"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace.id"), index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), index=True, nullable=True
    )
    source_key: Mapped[str] = mapped_column(String(255))
    source_native_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(2048))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(String(255))
    body_excerpt: Mapped[str] = mapped_column(Text)
    company_name_raw: Mapped[str] = mapped_column(String(255))
    company_domain_raw: Mapped[str] = mapped_column(String(255))
    location_raw: Mapped[str] = mapped_column(String(255))
    workplace_type: Mapped[str] = mapped_column(String(255))
    intent_label: Mapped[str] = mapped_column(String(255), default="unresolved")
    contact_routes_raw: Mapped[Any] = mapped_column(JSON)
    raw_snapshot_uri: Mapped[str] = mapped_column(String(255), default="")
    content_hash: Mapped[str] = mapped_column(String(255))
    access_policy_version: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = ["SourceHit"]
