from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ReviewAssignment(BaseModel):
    """ReviewAssignment."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    lead_id: UUID
    reviewer_id: UUID
    assigned_at: datetime
    completed_at: datetime
    status: str = "pending"


class ReviewAssignmentCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    lead_id: UUID
    reviewer_id: UUID
    assigned_at: datetime
    completed_at: datetime
    status: str = "pending"


class ReviewAssignmentUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    lead_id: UUID | None = None
    reviewer_id: UUID | None = None
    assigned_at: datetime | None = None
    completed_at: datetime | None = None
    status: str | None = None


__all__ = ["ReviewAssignment", "ReviewAssignmentCreate", "ReviewAssignmentUpdate"]
