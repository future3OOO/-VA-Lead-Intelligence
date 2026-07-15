from datetime import datetime
from uuid import UUID

from config.enums import OutcomeType
from domain.events.base import BaseEvent


class OutcomeEvent(BaseEvent):
    """Outcome from outreach."""
    schema_version: str = "1.0.0"
    lead_id: UUID
    outcome_type: OutcomeType
    occurred_at: datetime

__all__ = ["OutcomeEvent"]
