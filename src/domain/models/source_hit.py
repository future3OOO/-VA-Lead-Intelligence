from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.enums import IntentLabel


class SourceHit(BaseModel):
    """Normalized record from a source adapter.."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    company_id: UUID | None
    source_key: str
    source_native_id: str
    source_url: str
    observed_at: datetime
    published_at: datetime
    title: str
    body_excerpt: str
    company_name_raw: str
    company_domain_raw: str
    location_raw: str
    workplace_type: str
    intent_label: IntentLabel = IntentLabel.UNRESOLVED
    contact_routes_raw: Any = Field(default_factory=list)
    raw_snapshot_uri: str = ""
    content_hash: str
    access_policy_version: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SourceHitCreate(BaseModel):
    """Create request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    source_key: str
    source_native_id: str
    source_url: str
    observed_at: datetime
    published_at: datetime
    title: str
    body_excerpt: str
    company_name_raw: str
    company_domain_raw: str
    location_raw: str
    workplace_type: str
    intent_label: IntentLabel = IntentLabel.UNRESOLVED
    contact_routes_raw: Any = Field(default_factory=list)
    raw_snapshot_uri: str = ""
    content_hash: str
    access_policy_version: str


class SourceHitUpdate(BaseModel):
    """Partial update request."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)
    workspace_id: UUID | None = None
    company_id: UUID | None = None
    source_key: str | None = None
    source_native_id: str | None = None
    source_url: str | None = None
    observed_at: datetime | None = None
    published_at: datetime | None = None
    title: str | None = None
    body_excerpt: str | None = None
    company_name_raw: str | None = None
    company_domain_raw: str | None = None
    location_raw: str | None = None
    workplace_type: str | None = None
    intent_label: IntentLabel | None = None
    contact_routes_raw: Any | None = None
    raw_snapshot_uri: str | None = None
    content_hash: str | None = None
    access_policy_version: str | None = None


__all__ = ["SourceHit", "SourceHitCreate", "SourceHitUpdate"]
