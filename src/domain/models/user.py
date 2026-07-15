from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class User(BaseModel):
    """User."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    full_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    email: EmailStr
    full_name: str

class UserUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    email: EmailStr | None = None
    full_name: str | None = None

__all__ = ["User", "UserCreate", "UserUpdate"]
