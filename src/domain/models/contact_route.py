from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ContactRoute(BaseModel):
    """ContactRoute."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    route_type: str
    value: str
    is_verified: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContactRouteCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    route_type: str
    value: str
    is_verified: bool


class ContactRouteUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    route_type: str | None = None
    value: str | None = None
    is_verified: bool | None = None


__all__ = ["ContactRoute", "ContactRouteCreate", "ContactRouteUpdate"]
