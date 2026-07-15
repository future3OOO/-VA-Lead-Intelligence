from uuid import UUID

from pydantic import Field

from domain.events.base import BaseEvent


class ClassifierOutput(BaseEvent):
    """Output from the classifier."""

    schema_version: str = "1.0.0"
    company_id: UUID
    predicted_capabilities: list[str] = Field(default_factory=list)
    confidence: float


__all__ = ["ClassifierOutput"]
