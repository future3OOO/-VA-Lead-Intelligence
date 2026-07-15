from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CompanyRelationship(BaseModel):
    """CompanyRelationship."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    parent_company_id: UUID
    child_company_id: UUID
    relationship_type: str


class CompanyRelationshipCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    parent_company_id: UUID
    child_company_id: UUID
    relationship_type: str


class CompanyRelationshipUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    parent_company_id: UUID | None = None
    child_company_id: UUID | None = None
    relationship_type: str | None = None


__all__ = ["CompanyRelationship", "CompanyRelationshipCreate", "CompanyRelationshipUpdate"]
