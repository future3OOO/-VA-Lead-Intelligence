from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class OperationalMetadata(BaseModel):
    """OperationalMetadata."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    key: str
    value: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class OperationalMetadataCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    key: str
    value: dict[str, Any] = Field(default_factory=dict)

class OperationalMetadataUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    key: str | None = None
    value: dict[str, Any] | None = None

__all__ = ["OperationalMetadata", "OperationalMetadataCreate", "OperationalMetadataUpdate"]
