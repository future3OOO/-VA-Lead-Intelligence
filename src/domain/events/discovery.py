from uuid import UUID

from pydantic import HttpUrl

from domain.events.base import BaseEvent


class Discovery(BaseEvent):
    """Initial discovery request for a seed."""
    schema_version: str = "1.0.0"
    seed_url: HttpUrl
    source_id: str
    campaign_id: UUID

__all__ = ["Discovery"]
