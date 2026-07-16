from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Fact(BaseModel):
    """Fact."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    evidence_record_id: UUID
    company_id: UUID
    fact_type: str
    value: dict[str, Any]
    confidence: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FactCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    evidence_record_id: UUID
    company_id: UUID
    fact_type: str
    value: dict[str, Any]
    confidence: float


class FactUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    evidence_record_id: UUID | None = None
    company_id: UUID | None = None
    fact_type: str | None = None
    value: dict[str, Any] | None = None
    confidence: float | None = None


__all__ = ["Fact", "FactCreate", "FactUpdate"]
