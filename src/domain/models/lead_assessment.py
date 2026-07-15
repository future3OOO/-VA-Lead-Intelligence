from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import LeadStatus


class LeadAssessment(BaseModel):
    """Scored lead.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    campaign_id: UUID
    score: float
    status: LeadStatus = LeadStatus.PENDING
    reason_codes: list[str] = Field(default_factory=list)
    assessed_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class LeadAssessmentCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    campaign_id: UUID
    score: float
    status: LeadStatus = LeadStatus.PENDING
    reason_codes: list[str] = Field(default_factory=list)
    assessed_at: datetime

class LeadAssessmentUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    campaign_id: UUID | None = None
    score: float | None = None
    status: LeadStatus | None = None
    reason_codes: list[str] | None = None
    assessed_at: datetime | None = None

__all__ = ["LeadAssessment", "LeadAssessmentCreate", "LeadAssessmentUpdate"]
