from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import SourceType


class SourceEvent(BaseModel):
    """Raw source event.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    source_id: str
    source_type: SourceType
    raw_payload: dict[str, Any]
    received_at: datetime = Field(default_factory=datetime.utcnow)


class SourceEventCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_id: str
    source_type: SourceType
    raw_payload: dict[str, Any]


class SourceEventUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_id: str | None = None
    source_type: SourceType | None = None
    raw_payload: dict[str, Any] | None = None


__all__ = ["SourceEvent", "SourceEventCreate", "SourceEventUpdate"]
