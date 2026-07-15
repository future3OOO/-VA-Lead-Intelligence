from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CompanyIdentifier(BaseModel):
    """CompanyIdentifier."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    source: str
    external_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CompanyIdentifierCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    source: str
    external_id: str


class CompanyIdentifierUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    source: str | None = None
    external_id: str | None = None


__all__ = ["CompanyIdentifier", "CompanyIdentifierCreate", "CompanyIdentifierUpdate"]
