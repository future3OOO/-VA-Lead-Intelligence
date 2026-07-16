from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    """AuditEvent."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    actor_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEventCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    actor_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    payload: dict[str, Any]


class AuditEventUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    actor_id: UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    payload: dict[str, Any] | None = None


__all__ = ["AuditEvent", "AuditEventCreate", "AuditEventUpdate"]
