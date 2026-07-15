from uuid import UUID

from domain.events.base import BaseEvent


class JobSignal(BaseEvent):
    """Normalized job posting signal."""
    schema_version: str = "1.0.0"
    ats_board_id: UUID
    job_id: str
    title: str
    location: str
    description_text: str
    remote_allowed: bool

__all__ = ["JobSignal"]
