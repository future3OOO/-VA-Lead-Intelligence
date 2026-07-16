"""Ashby public job-board adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class AshbyJobsAdapter(BaseSourceAdapter):
    """Fetch public job postings from Ashby."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://api.ashbyhq.com/posting-api",
            timeout=30.0,
        )

    @property
    def source_key(self) -> str:
        return "ashby_jobs"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        subdomain = query.get("subdomain") or self.config.adapter_config.get("subdomain")
        if not subdomain:
            return []
        response = await self.client.get(f"/job-posting?subdomain={subdomain}")
        response.raise_for_status()
        data = response.json()
        return [{"subdomain": subdomain, "posting": p} for p in data.get("results", [])]

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        posting = raw["posting"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": posting.get("id", ""),
            "source_url": posting.get("jobUrl") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": posting.get("createdAt") or datetime.now(timezone.utc),
            "title": posting.get("title", ""),
            "body_excerpt": (posting.get("description") or "")[:2000],
            "company_name_raw": raw["subdomain"],
            "company_domain_raw": "",
            "location_raw": posting.get("location", ""),
            "workplace_type": posting.get("employmentType", ""),
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
