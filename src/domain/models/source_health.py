from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SourceHealth(BaseModel):
    """Source adapter health.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    source_id: str
    healthy: bool
    last_checked_at: datetime
    error_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SourceHealthCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_id: str
    healthy: bool
    last_checked_at: datetime
    error_count: int

class SourceHealthUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_id: str | None = None
    healthy: bool | None = None
    last_checked_at: datetime | None = None
    error_count: int | None = None

__all__ = ["SourceHealth", "SourceHealthCreate", "SourceHealthUpdate"]
