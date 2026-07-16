"""Hunter.io domain email discovery adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class HunterDomainAdapter(BaseSourceAdapter):
    """Use the Hunter API to find domain-level business emails after qualification."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(base_url="https://api.hunter.io/v2", timeout=30.0)

    @property
    def source_key(self) -> str:
        return "hunter_domain"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        domain = query.get("domain") or self.config.adapter_config.get("domain")
        api_key = query.get("api_key") or self.config.adapter_config.get("api_key")
        if not domain or not api_key:
            return []
        response = await self.client.get(
            "/domain-search",
            params={"domain": domain, "api_key": api_key},
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        return [{"domain": domain, "email": e} for e in data.get("emails", [])]

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        email = raw["email"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": f"{raw['domain']}:{email.get('value', '')}",
            "source_url": f"https://{raw['domain']}",
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": email.get("position", ""),
            "body_excerpt": "",
            "company_name_raw": "",
            "company_domain_raw": raw["domain"],
            "location_raw": "",
            "workplace_type": "",
            "contact_routes_raw": [
                {"type": "named_work_email_approved", "value": email.get("value", "")}
            ],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
