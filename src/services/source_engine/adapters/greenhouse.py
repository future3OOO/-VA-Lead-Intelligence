"""Greenhouse public job-board adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class GreenhouseJobsAdapter(BaseSourceAdapter):
    """Fetch public job postings from Greenhouse boards."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://boards-api.greenhouse.io/v1/boards",
            timeout=30.0,
        )

    @property
    def source_key(self) -> str:
        return "greenhouse_jobs"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        board_token = query.get("board_token") or self.config.adapter_config.get("board_token")
        if not board_token:
            return []
        url = f"/{board_token}/jobs?content=true"
        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        return [
            {
                "board_token": board_token,
                "job": job,
                "source_url": job.get("absolute_url", ""),
            }
            for job in jobs
        ]

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = raw["job"]
        title = job.get("title", "")
        location_list = job.get("location", [])
        if isinstance(location_list, list):
            location = ", ".join(loc.get("name", "") for loc in location_list)
        else:
            location = str(location_list)
        body = (job.get("content") or "") + " " + (job.get("internal_content") or "")
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": str(job.get("id", "")),
            "source_url": raw.get("source_url") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": job.get("updated_at") or datetime.now(timezone.utc),
            "title": title,
            "body_excerpt": body[:2000],
            "company_name_raw": raw["board_token"],
            "company_domain_raw": "",
            "location_raw": location,
            "workplace_type": job.get("workplace_type", ""),
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
