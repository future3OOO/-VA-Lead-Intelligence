from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import ReviewDecision


class ReviewDecisionRecord(BaseModel):
    """ReviewDecisionRecord."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    lead_id: UUID
    reviewer_id: UUID
    decision: ReviewDecision
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReviewDecisionRecordCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    lead_id: UUID
    reviewer_id: UUID
    decision: ReviewDecision
    reason: str

class ReviewDecisionRecordUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    lead_id: UUID | None = None
    reviewer_id: UUID | None = None
    decision: ReviewDecision | None = None
    reason: str | None = None

__all__ = ["ReviewDecisionRecord", "ReviewDecisionRecordCreate", "ReviewDecisionRecordUpdate"]
