from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class JobHistory(BaseModel):
    """JobHistory."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    job_id: UUID
    title: str
    changed_at: datetime
    change_type: str

class JobHistoryCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    job_id: UUID
    title: str
    changed_at: datetime
    change_type: str

class JobHistoryUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    job_id: UUID | None = None
    title: str | None = None
    changed_at: datetime | None = None
    change_type: str | None = None

__all__ = ["JobHistory", "JobHistoryCreate", "JobHistoryUpdate"]
