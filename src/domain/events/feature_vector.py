from typing import Any
from uuid import UUID

from pydantic import Field

from domain.events.base import BaseEvent


class FeatureVector(BaseEvent):
    """Extracted features for scoring."""
    schema_version: str = "1.0.0"
    company_id: UUID
    features: dict[str, Any] = Field(default_factory=dict)

__all__ = ["FeatureVector"]
