from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Scorecard(BaseModel):
    """Released scorecard version metadata.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    version: str
    config_path: str
    is_active: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScorecardCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    version: str
    config_path: str
    is_active: bool


class ScorecardUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    version: str | None = None
    config_path: str | None = None
    is_active: bool | None = None


__all__ = ["Scorecard", "ScorecardCreate", "ScorecardUpdate"]
