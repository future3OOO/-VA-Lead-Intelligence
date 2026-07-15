from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import RunStatus


class CampaignRun(BaseModel):
    """Single execution of a campaign.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    campaign_id: UUID
    status: RunStatus = RunStatus.PENDING
    started_at: datetime
    completed_at: datetime
    total_discovered: int
    total_qualified: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CampaignRunCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID
    status: RunStatus = RunStatus.PENDING
    started_at: datetime
    completed_at: datetime
    total_discovered: int
    total_qualified: int

class CampaignRunUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID | None = None
    status: RunStatus | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_discovered: int | None = None
    total_qualified: int | None = None

__all__ = ["CampaignRun", "CampaignRunCreate", "CampaignRunUpdate"]
