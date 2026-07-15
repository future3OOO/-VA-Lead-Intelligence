from uuid import UUID

from domain.events.base import BaseEvent


class EvidenceRecord(BaseEvent):
    """Normalized evidence supporting a lead."""
    schema_version: str = "1.0.0"
    company_id: UUID
    evidence_type: str
    source_event_id: UUID
    signal_strength: float

__all__ = ["EvidenceRecord"]
