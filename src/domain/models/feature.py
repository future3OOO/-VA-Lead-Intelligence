from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Feature(BaseModel):
    """Extracted feature for scoring.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    feature_name: str
    feature_value: dict[str, Any] = Field(default_factory=dict)
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FeatureCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    feature_name: str
    feature_value: dict[str, Any] = Field(default_factory=dict)
    source: str

class FeatureUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    feature_name: str | None = None
    feature_value: dict[str, Any] | None = None
    source: str | None = None

__all__ = ["Feature", "FeatureCreate", "FeatureUpdate"]
