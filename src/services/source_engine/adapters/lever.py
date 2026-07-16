"""Lever public job-board adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class LeverJobsAdapter(BaseSourceAdapter):
    """Fetch public job postings from Lever."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://api.lever.co/v0/postings",
            timeout=30.0,
        )

    @property
    def source_key(self) -> str:
        return "lever_jobs"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        site = query.get("site") or self.config.adapter_config.get("site")
        if not site:
            return []
        response = await self.client.get(f"/{site}?mode=json")
        response.raise_for_status()
        postings = response.json()
        return [{"site": site, "posting": p} for p in postings]

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        posting = raw["posting"]
        text = posting.get("description", "") + " " + str(posting.get("lists", ""))
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": posting.get("id", ""),
            "source_url": posting.get("urls", {}).get("apply") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": posting.get("createdAt") or datetime.now(timezone.utc),
            "title": posting.get("text", ""),
            "body_excerpt": text[:2000],
            "company_name_raw": raw["site"],
            "company_domain_raw": "",
            "location_raw": posting.get("categories", {}).get("location", ""),
            "workplace_type": posting.get("categories", {}).get("workplaceType", ""),
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
