from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    """Job posting.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    ats_board_id: UUID
    external_job_id: str
    title: str
    location: str
    description_text: str
    remote_allowed: bool
    posted_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    ats_board_id: UUID
    external_job_id: str
    title: str
    location: str
    description_text: str
    remote_allowed: bool
    posted_at: datetime


class JobUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    ats_board_id: UUID | None = None
    external_job_id: str | None = None
    title: str | None = None
    location: str | None = None
    description_text: str | None = None
    remote_allowed: bool | None = None
    posted_at: datetime | None = None


__all__ = ["Job", "JobCreate", "JobUpdate"]
