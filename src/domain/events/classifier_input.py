from uuid import UUID

from pydantic import Field

from domain.events.base import BaseEvent


class ClassifierInput(BaseEvent):
    """Input to the classifier."""
    schema_version: str = "1.0.0"
    company_id: UUID
    evidence_ids: list[str] = Field(default_factory=list)

__all__ = ["ClassifierInput"]
