from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from config.enums import SourceType


class AtsBoard(BaseModel):
    """Parsed ATS board.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    provider: SourceType
    board_url: HttpUrl
    board_token: str
    last_fetched_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AtsBoardCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    provider: SourceType
    board_url: HttpUrl
    board_token: str
    last_fetched_at: datetime

class AtsBoardUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    provider: SourceType | None = None
    board_url: HttpUrl | None = None
    board_token: str | None = None
    last_fetched_at: datetime | None = None

__all__ = ["AtsBoard", "AtsBoardCreate", "AtsBoardUpdate"]
