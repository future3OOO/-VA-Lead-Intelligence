from uuid import UUID

from pydantic import Field

from domain.events.base import BaseEvent


class CompanyResolved(BaseEvent):
    """Company identity resolved and normalized."""
    schema_version: str = "1.0.0"
    company_id: UUID
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)

__all__ = ["CompanyResolved"]
