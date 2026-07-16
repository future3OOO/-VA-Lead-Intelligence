"""Breezy HR public job-board JSON feed adapter."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class BreezyJobsAdapter(BaseSourceAdapter):
    """Fetch public job postings from a Breezy HR career site JSON feed."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(timeout=30.0)

    @property
    def source_key(self) -> str:
        return "breezy_jobs"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        account = query.get("account") or self.config.adapter_config.get("account")
        if not account:
            return []
        url = f"https://{account}.breezy.hr/json"
        response = await self.client.get(url, params={"verbose": "true"})
        response.raise_for_status()
        jobs = response.json()
        return [{"account": account, "job": job} for job in jobs]

    def _company_name(self, job: dict[str, Any], account: str) -> str:
        company = job.get("company") or {}
        name = company.get("name", "")
        return name.strip() or account

    def _location(self, job: dict[str, Any]) -> str:
        loc = job.get("location") or {}
        parts = []
        if loc.get("city"):
            parts.append(loc["city"])
        if loc.get("state") and isinstance(loc["state"], dict) and loc["state"].get("name"):
            parts.append(loc["state"]["name"])
        if loc.get("country") and isinstance(loc["country"], dict) and loc["country"].get("name"):
            parts.append(loc["country"]["name"])
        if not parts and loc.get("name"):
            parts.append(loc["name"])
        return ", ".join(parts)

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = raw["job"]
        description = re.sub(r"<[^>]+>", "", job.get("description") or "")
        company_name = self._company_name(job, raw["account"])
        published = job.get("published_date")
        if published:
            try:
                published = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                published = datetime.now(timezone.utc)
        else:
            published = datetime.now(timezone.utc)
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": job.get("id", ""),
            "source_url": job.get("url") or f"https://{raw['account']}.breezy.hr",
            "observed_at": datetime.now(timezone.utc),
            "published_at": published,
            "title": job.get("name", ""),
            "body_excerpt": description[:2000],
            "company_name_raw": company_name,
            "company_domain_raw": "",
            "location_raw": self._location(job),
            "workplace_type": "",
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
