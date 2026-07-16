from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class QueryFamily(BaseModel):
    """Versioned query set for source discovery.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    family_key: str
    version: str
    positive_titles: list[str] = []
    positive_task_phrases: list[str] = []
    negative_terms: list[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class QueryFamilyCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    family_key: str
    version: str
    positive_titles: list[str] = []
    positive_task_phrases: list[str] = []
    negative_terms: list[str] = []


class QueryFamilyUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    family_key: str | None = None
    version: str | None = None
    positive_titles: list[str] | None = None
    positive_task_phrases: list[str] | None = None
    negative_terms: list[str] | None = None


__all__ = ["QueryFamily", "QueryFamilyCreate", "QueryFamilyUpdate"]
