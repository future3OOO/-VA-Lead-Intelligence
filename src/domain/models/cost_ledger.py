from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CostLedger(BaseModel):
    """Tracked cost event.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    campaign_run_id: UUID
    service: str
    units: float
    unit_cost: float
    currency: str = 'USD'
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CostLedgerCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_run_id: UUID
    service: str
    units: float
    unit_cost: float
    currency: str = 'USD'

class CostLedgerUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_run_id: UUID | None = None
    service: str | None = None
    units: float | None = None
    unit_cost: float | None = None
    currency: str | None = None

__all__ = ["CostLedger", "CostLedgerCreate", "CostLedgerUpdate"]
