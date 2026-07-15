from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import ExportStatus


class ExportRecord(BaseModel):
    """Lead export request and result.."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    campaign_id: UUID
    status: ExportStatus = ExportStatus.PENDING
    lead_ids: list[str] = Field(default_factory=list)
    destination: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime

class ExportRecordCreate(BaseModel):
    """Create request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID
    status: ExportStatus = ExportStatus.PENDING
    lead_ids: list[str] = Field(default_factory=list)
    destination: str
    completed_at: datetime

class ExportRecordUpdate(BaseModel):
    """Partial update request."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    campaign_id: UUID | None = None
    status: ExportStatus | None = None
    lead_ids: list[str] | None = None
    destination: str | None = None
    completed_at: datetime | None = None

__all__ = ["ExportRecord", "ExportRecordCreate", "ExportRecordUpdate"]
