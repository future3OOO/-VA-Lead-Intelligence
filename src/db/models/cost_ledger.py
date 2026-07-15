import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CostLedger(Base):
    """Tracked cost event.."""
    __tablename__ = "cost_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workspace.id'), index=True)
    campaign_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('campaign_run.id'))
    service: Mapped[str] = mapped_column(String(255))
    units: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(255), default='USD')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

__all__ = ["CostLedger"]
