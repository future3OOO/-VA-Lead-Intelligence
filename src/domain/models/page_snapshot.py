from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PageSnapshot(BaseModel):
    """PageSnapshot."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    url: HttpUrl
    snapshot_path: str
    etag: str
    fetched_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PageSnapshotCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    url: HttpUrl
    snapshot_path: str
    etag: str
    fetched_at: datetime


class PageSnapshotUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    url: HttpUrl | None = None
    snapshot_path: str | None = None
    etag: str | None = None
    fetched_at: datetime | None = None


__all__ = ["PageSnapshot", "PageSnapshotCreate", "PageSnapshotUpdate"]
