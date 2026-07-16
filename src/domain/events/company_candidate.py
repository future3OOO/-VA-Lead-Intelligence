from typing import Any

from domain.events.base import BaseEvent


class CompanyCandidate(BaseEvent):
    """Candidate company identified by a discovery adapter."""

    schema_version: str = "1.0.0"
    company_name: str
    domain: str
    source_payload: dict[str, Any]


__all__ = ["CompanyCandidate"]
