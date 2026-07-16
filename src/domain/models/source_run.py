from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import RunStatus


class SourceRun(BaseModel):
    """Execution record for a source adapter run.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    campaign_id: UUID
    source_key: str
    status: RunStatus = RunStatus.PENDING
    started_at: datetime
    completed_at: datetime
    hits_total: int
    hits_qualified_total: int
    hits_duplicate_total: int
    errors_total: int
    checkpoint: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SourceRunCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID
    source_key: str
    status: RunStatus = RunStatus.PENDING
    started_at: datetime
    completed_at: datetime
    hits_total: int
    hits_qualified_total: int
    hits_duplicate_total: int
    errors_total: int
    checkpoint: dict[str, Any]


class SourceRunUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID | None = None
    source_key: str | None = None
    status: RunStatus | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    hits_total: int | None = None
    hits_qualified_total: int | None = None
    hits_duplicate_total: int | None = None
    errors_total: int | None = None
    checkpoint: dict[str, Any] | None = None


__all__ = ["SourceRun", "SourceRunCreate", "SourceRunUpdate"]
