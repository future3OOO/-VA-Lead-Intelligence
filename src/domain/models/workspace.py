from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Workspace(BaseModel):
    """Tenant workspace.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    name: str
    slug: str
    billing_email: EmailStr
    plan: str = "trial"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkspaceCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    name: str
    slug: str
    billing_email: EmailStr
    plan: str = "trial"


class WorkspaceUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    name: str | None = None
    slug: str | None = None
    billing_email: EmailStr | None = None
    plan: str | None = None


__all__ = ["Workspace", "WorkspaceCreate", "WorkspaceUpdate"]
