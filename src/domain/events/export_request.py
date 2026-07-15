from pydantic import Field

from domain.events.base import BaseEvent


class ExportRequest(BaseEvent):
    """Request to export leads."""
    schema_version: str = "1.0.0"
    lead_ids: list[str] = Field(default_factory=list)
    destination: str

__all__ = ["ExportRequest"]
