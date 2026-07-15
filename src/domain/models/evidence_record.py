from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecord(BaseModel):
    """EvidenceRecord."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID
    source_event_id: UUID
    evidence_type: str
    signal_strength: float
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceRecordCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID
    source_event_id: UUID
    evidence_type: str
    signal_strength: float
    extracted_facts: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecordUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    source_event_id: UUID | None = None
    evidence_type: str | None = None
    signal_strength: float | None = None
    extracted_facts: dict[str, Any] | None = None


__all__ = ["EvidenceRecord", "EvidenceRecordCreate", "EvidenceRecordUpdate"]
