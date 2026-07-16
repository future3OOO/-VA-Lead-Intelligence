from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import IntentLabel


class ExternalOpportunity(BaseModel):
    """Explicit work posting with unresolved client.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    source_hit_id: UUID
    platform: str
    external_opportunity_id: str
    title: str
    description: str
    buyer_intent_label: IntentLabel = IntentLabel.UNRESOLVED
    budget_hint: str
    country_code: str
    status: str = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExternalOpportunityCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_hit_id: UUID
    platform: str
    external_opportunity_id: str
    title: str
    description: str
    buyer_intent_label: IntentLabel = IntentLabel.UNRESOLVED
    budget_hint: str
    country_code: str
    status: str = "open"


class ExternalOpportunityUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    source_hit_id: UUID | None = None
    platform: str | None = None
    external_opportunity_id: str | None = None
    title: str | None = None
    description: str | None = None
    buyer_intent_label: IntentLabel | None = None
    budget_hint: str | None = None
    country_code: str | None = None
    status: str | None = None


__all__ = ["ExternalOpportunity", "ExternalOpportunityCreate", "ExternalOpportunityUpdate"]
