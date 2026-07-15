from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CompanyAlias(BaseModel):
    """CompanyAlias."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    alias: str
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CompanyAliasCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    alias: str
    source: str


class CompanyAliasUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    alias: str | None = None
    source: str | None = None


__all__ = ["CompanyAlias", "CompanyAliasCreate", "CompanyAliasUpdate"]
