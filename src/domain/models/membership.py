from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import MembershipRole


class Membership(BaseModel):
    """Membership."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    user_id: UUID
    role: MembershipRole
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MembershipCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    user_id: UUID
    role: MembershipRole

class MembershipUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    user_id: UUID | None = None
    role: MembershipRole | None = None

__all__ = ["Membership", "MembershipCreate", "MembershipUpdate"]
