from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Suppression(BaseModel):
    """Suppression rule.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    reason: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SuppressionCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    reason: str
    expires_at: datetime


class SuppressionUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    reason: str | None = None
    expires_at: datetime | None = None


__all__ = ["Suppression", "SuppressionCreate", "SuppressionUpdate"]
