from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import OutcomeType


class Outcome(BaseModel):
    """Outreach outcome.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    lead_id: UUID
    outcome_type: OutcomeType
    occurred_at: datetime
    notes: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OutcomeCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    lead_id: UUID
    outcome_type: OutcomeType
    occurred_at: datetime
    notes: str


class OutcomeUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    lead_id: UUID | None = None
    outcome_type: OutcomeType | None = None
    occurred_at: datetime | None = None
    notes: str | None = None


__all__ = ["Outcome", "OutcomeCreate", "OutcomeUpdate"]
