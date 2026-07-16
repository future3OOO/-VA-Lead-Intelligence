from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SourcePolicy(BaseModel):
    """SourcePolicy."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    source_id: str
    config: dict[str, Any]
    effective_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SourcePolicyCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_id: str
    config: dict[str, Any]
    effective_at: datetime


class SourcePolicyUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_id: str | None = None
    config: dict[str, Any] | None = None
    effective_at: datetime | None = None


__all__ = ["SourcePolicy", "SourcePolicyCreate", "SourcePolicyUpdate"]
