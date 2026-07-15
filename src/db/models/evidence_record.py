import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class EvidenceRecord(Base):
    """EvidenceRecord."""
    __tablename__ = "evidence_record"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('company.id'), index=True)
    source_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('source_event.id'), index=True)
    evidence_type: Mapped[str] = mapped_column(String(255))
    signal_strength: Mapped[float] = mapped_column(Float)
    extracted_facts: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

__all__ = ["EvidenceRecord"]
