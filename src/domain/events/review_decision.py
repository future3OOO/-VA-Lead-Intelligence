from uuid import UUID

from config.enums import ReviewDecision
from domain.events.base import BaseEvent


class ReviewDecisionEvent(BaseEvent):
    """Human review decision on a lead."""
    schema_version: str = "1.0.0"
    lead_id: UUID
    decision: ReviewDecision
    reviewer_id: UUID

__all__ = ["ReviewDecisionEvent"]
