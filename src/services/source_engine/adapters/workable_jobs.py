"""Workable public widget API adapter."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class WorkableJobsAdapter(BaseSourceAdapter):
    """Fetch public job postings from a Workable careers widget."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://apply.workable.com/api/v1/widget/accounts",
            timeout=30.0,
        )

    @property
    def source_key(self) -> str:
        return "workable_jobs"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        account = query.get("account") or self.config.adapter_config.get("account")
        if not account:
            return []
        response = await self.client.get(f"/{account}?details=true")
        response.raise_for_status()
        data = response.json()
        account_name = data.get("name", account)
        jobs = data.get("jobs", [])
        return [{"account": account, "account_name": account_name, "job": job} for job in jobs]

    _EMPLOYER_RE = re.compile(
        r"^([A-Z][A-Za-z0-9 &\.,\-'&]+?)\s+is\s+(?:hiring|seeking|looking)", re.I
    )

    def _extract_employer(self, description: str, account_name: str) -> str:
        clean = re.sub(r"<[^>]+>", "", description).strip()
        match = self._EMPLOYER_RE.match(clean)
        if match:
            return match.group(1).strip()
        return account_name

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = raw["job"]
        description = re.sub(r"<[^>]+>", "", job.get("description") or "")
        locations = job.get("locations") or []
        if locations:
            location = ", ".join(
                f"{loc.get('city', '')}, {loc.get('country', '')}".strip(", ")
                for loc in locations
                if loc.get("city") or loc.get("country")
            )
        else:
            location = f"{job.get('city', '')}, {job.get('country', '')}".strip(", ")
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": job.get("shortcode", ""),
            "source_url": job.get("url") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": job.get("published_on")
            or job.get("created_at")
            or datetime.now(timezone.utc),
            "title": job.get("title", ""),
            "body_excerpt": description[:2000],
            "company_name_raw": self._extract_employer(description, raw["account_name"]),
            "company_domain_raw": "",
            "location_raw": location,
            "workplace_type": "Remote"
            if job.get("telecommuting")
            else (job.get("workplaceType") or ""),
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
