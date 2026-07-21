"""SmartRecruiters public posting adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class SmartRecruitersAdapter(BaseSourceAdapter):
    """Fetch public job postings from SmartRecruiters."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://api.smartrecruiters.com",
            timeout=30.0,
        )

    @property
    def source_key(self) -> str:
        return "smartrecruiters_postings"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        company_id = query.get("company_id") or self.config.adapter_config.get("company_id")
        api_key = query.get("api_key") or self.config.adapter_config.get("api_key")
        if not company_id:
            return []
        headers = {"X-SmartToken": api_key} if api_key else {}
        response = await self._request(
            "GET",
            f"/v1/companies/{company_id}/postings",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return [{"company_id": company_id, "posting": p} for p in data.get("content", [])]

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        posting = raw["posting"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": posting.get("id", ""),
            "source_url": posting.get("applyUrl") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": posting.get("releasedDate") or datetime.now(timezone.utc),
            "title": posting.get("title", ""),
            "body_excerpt": (posting.get("jobDescription") or "")[:2000],
            "company_name_raw": raw["company_id"],
            "company_domain_raw": "",
            "location_raw": posting.get("location", {}).get("city", ""),
            "workplace_type": posting.get("workplaceType", ""),
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
