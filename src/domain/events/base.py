from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)

    schema_version: str = "1.0.0"
    event_id: UUID
    occurred_at: datetime
    workspace_id: UUID
    correlation_id: UUID
    producer: str


__all__ = ["BaseEvent"]
