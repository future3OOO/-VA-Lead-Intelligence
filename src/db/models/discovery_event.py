import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DiscoveryEvent(Base):
    """Tracked discovery request.."""
    __tablename__ = "discovery_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('campaign.id'), index=True)
    source_id: Mapped[str] = mapped_column(String(255))
    seed_url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(255), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

__all__ = ["DiscoveryEvent"]
