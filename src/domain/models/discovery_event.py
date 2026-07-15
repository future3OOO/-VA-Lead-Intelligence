from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from config.enums import RunStatus


class DiscoveryEvent(BaseModel):
    """Tracked discovery request.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    campaign_id: UUID
    source_id: str
    seed_url: HttpUrl
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DiscoveryEventCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID
    source_id: str
    seed_url: HttpUrl
    status: RunStatus = RunStatus.PENDING


class DiscoveryEventUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID | None = None
    source_id: str | None = None
    seed_url: HttpUrl | None = None
    status: RunStatus | None = None


__all__ = ["DiscoveryEvent", "DiscoveryEventCreate", "DiscoveryEventUpdate"]
