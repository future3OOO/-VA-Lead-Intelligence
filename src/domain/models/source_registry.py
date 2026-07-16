from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SourceRegistry(BaseModel):
    """Configured source adapter registration.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    source_key: str
    source_class: str
    access_mode: str
    status: str = "enabled"
    owner: str
    terms_review_status: str
    terms_reviewed_at: datetime
    allowed_outputs: Any = []
    allowed_fields: Any = []
    raw_retention_days: int
    normalized_retention_days: int
    rate_limit: dict[str, Any] = {}
    kill_switch: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SourceRegistryCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_key: str
    source_class: str
    access_mode: str
    status: str = "enabled"
    owner: str
    terms_review_status: str
    terms_reviewed_at: datetime
    allowed_outputs: Any = []
    allowed_fields: Any = []
    raw_retention_days: int
    normalized_retention_days: int
    rate_limit: dict[str, Any] = {}
    kill_switch: str


class SourceRegistryUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_key: str | None = None
    source_class: str | None = None
    access_mode: str | None = None
    status: str | None = None
    owner: str | None = None
    terms_review_status: str | None = None
    terms_reviewed_at: datetime | None = None
    allowed_outputs: Any | None = None
    allowed_fields: Any | None = None
    raw_retention_days: int | None = None
    normalized_retention_days: int | None = None
    rate_limit: dict[str, Any] | None = None
    kill_switch: str | None = None


__all__ = ["SourceRegistry", "SourceRegistryCreate", "SourceRegistryUpdate"]
