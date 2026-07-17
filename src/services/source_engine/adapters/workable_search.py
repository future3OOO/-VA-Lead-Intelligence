"""Workable cross-customer job search API adapter (public jobs.workable.com search)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class WorkableSearchAdapter(BaseSourceAdapter):
    """Search and fetch public job postings from Workable's meta-search API.

    This adapter calls ``https://jobs.workable.com/api/v1/jobs`` with polite
    pagination. It is intentionally bounded to location + workplace-aware queries
    so the engine targets remote/hybrid, region-specific small-business leads.
    """

    _REMOTE_KEYWORDS = re.compile(
        r"\b(remote|hybrid|wfh|work from home|work at home|telecommut)\b", re.I
    )
    _ONSITE_KEYWORDS = re.compile(
        r"\b(on[-\s]?site|on site|in[-\s]?office|in office|office[-\s]?based|site[-\s]?based)\b",
        re.I,
    )

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://jobs.workable.com/api/v1",
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )

    @property
    def source_key(self) -> str:
        return "workable_search"

    def _is_remote_friendly(self, job: dict[str, Any]) -> bool:
        """Return True if the job is explicitly remote/hybrid or reads as such."""
        workplace = (job.get("workplace") or "").lower()
        if workplace in {"remote", "hybrid"}:
            return True
        if workplace == "on_site":
            return False

        text = f"{job.get('title', '')} {job.get('description', '')}"
        has_remote = bool(self._REMOTE_KEYWORDS.search(text))
        has_onsite = bool(self._ONSITE_KEYWORDS.search(text))
        if has_onsite and not has_remote:
            return False
        return has_remote

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        queries = query.get("queries") or self.config.adapter_config.get("queries") or [""]
        locations = query.get("locations") or self.config.adapter_config.get("locations") or [""]
        max_pages = int(query.get("max_pages") or self.config.adapter_config.get("max_pages", 200))

        results: list[dict[str, Any]] = []
        for q in queries:
            for loc in locations:
                params: dict[str, Any] = {}
                if q:
                    params["query"] = q
                if loc:
                    params["location"] = loc
                page_token: str | None = None
                for _ in range(max_pages):
                    if page_token:
                        params["pageToken"] = page_token
                    elif "pageToken" in params:
                        del params["pageToken"]
                    await self.rate_limiter.acquire()
                    response = await self.client.get("/jobs", params=params)
                    response.raise_for_status()
                    data = response.json()
                    jobs = data.get("jobs", [])
                    for job in jobs:
                        if not self._is_remote_friendly(job):
                            continue
                        results.append({"job": job, "query": q, "location": loc})
                    page_token = data.get("nextPageToken")
                    if not page_token or not jobs:
                        break
        return results

    def _parse_domain(self, website: str) -> str:
        if not website:
            return ""
        parsed = urlparse(website)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _location_text(self, job: dict[str, Any]) -> str:
        locations = job.get("locations") or []
        if locations:
            return "; ".join(str(loc) for loc in locations if loc)
        loc = job.get("location") or {}
        parts = [loc.get("city"), loc.get("subregion"), loc.get("countryName")]
        return ", ".join(p for p in parts if p)

    def _published_at(self, job: dict[str, Any]) -> datetime:
        raw = job.get("created") or job.get("updated") or job.get("published_on")
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = raw["job"]
        company = job.get("company") or {}
        job_description = re.sub(r"<[^>]+>", "", job.get("description") or "")
        company_description = re.sub(r"<[^>]+>", "", company.get("description") or "")
        full_description = f"{company_description}\n\n{job_description}".strip()
        company_name = company.get("title") or job.get("department") or ""
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": str(job.get("id", "")),
            "source_url": job.get("url") or "",
            "observed_at": datetime.now(timezone.utc),
            "published_at": self._published_at(job),
            "title": job.get("title", ""),
            "body_excerpt": full_description[:5000],
            "company_name_raw": company_name,
            "company_domain_raw": self._parse_domain(company.get("website") or ""),
            "location_raw": self._location_text(job),
            "workplace_type": job.get("workplace") or "",
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
