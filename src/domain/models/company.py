from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Company(BaseModel):
    """Normalized company.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    canonical_name: str
    primary_domain: str
    country_code: str
    industry: str
    employee_count: int
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CompanyCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    canonical_name: str
    primary_domain: str
    country_code: str
    industry: str
    employee_count: int
    status: str = "active"


class CompanyUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    canonical_name: str | None = None
    primary_domain: str | None = None
    country_code: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    status: str | None = None


__all__ = ["Company", "CompanyCreate", "CompanyUpdate"]
