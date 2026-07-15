from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import CampaignStatus


class Campaign(BaseModel):
    """Outreach campaign definition.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    name: str
    status: CampaignStatus = CampaignStatus.DRAFT
    capability_filter: list[str] = Field(default_factory=list)
    score_threshold: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CampaignCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    name: str
    status: CampaignStatus = CampaignStatus.DRAFT
    capability_filter: list[str] = Field(default_factory=list)
    score_threshold: float

class CampaignUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    name: str | None = None
    status: CampaignStatus | None = None
    capability_filter: list[str] | None = None
    score_threshold: float | None = None

__all__ = ["Campaign", "CampaignCreate", "CampaignUpdate"]
