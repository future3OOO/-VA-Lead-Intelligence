"""Workable per-account widget API adapter.

Fetches jobs from individual Workable career pages via the public widget endpoint
``https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true``.  This
is useful when the cross-customer search API is rate-limited, because it works
one account at a time and returns full company descriptions and all open roles.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class WorkableCompanyAdapter(BaseSourceAdapter):
    """Fetch jobs from Workable-hosted career pages for a configured slug list."""

    _REMOTE_KEYWORDS = re.compile(
        r"\b(remote|hybrid|wfh|work from home|work at home|telecommut|virtual)\b", re.I
    )
    _ONSITE_KEYWORDS = re.compile(
        r"\b(on[-\s]?site|on site|in[-\s]?office|in office|office[-\s]?based|site[-\s]?based)\b",
        re.I,
    )

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
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
        return "workable_company"

    def _is_remote_friendly(self, job: dict[str, Any], description_text: str) -> bool:
        telecommuting = bool(job.get("telecommuting"))
        country = (job.get("country") or "").lower()
        text = f"{job.get('title', '')} {description_text} {country}"
        has_remote = bool(self._REMOTE_KEYWORDS.search(text))
        has_onsite = bool(self._ONSITE_KEYWORDS.search(text))
        if has_onsite and not has_remote:
            return False
        if telecommuting:
            return True
        if country in {"australia", "new zealand"}:
            return has_remote
        return has_remote

    @staticmethod
    def _location_text(job: dict[str, Any]) -> str:
        parts = [job.get("city"), job.get("state"), job.get("country")]
        return ", ".join(p for p in parts if p)

    def _published_at(self, job: dict[str, Any]) -> datetime:
        raw = job.get("published_on") or job.get("created_at")
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        slugs = query.get("slugs") or self.config.adapter_config.get("slugs") or []
        if not slugs:
            return []

        results: list[dict[str, Any]] = []
        for slug in slugs:
            slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
            if not slug:
                continue
            try:
                response = await self._request(
                    "GET",
                    f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
                    params={"details": "true"},
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError:
                continue

            company_name = data.get("name", "")
            company_description = re.sub(r"<[^>]+>", "", data.get("description") or "").strip()
            jobs = data.get("jobs", [])
            for job in jobs:
                job_description = re.sub(r"<[^>]+>", "", job.get("description") or "").strip()
                full_description = f"{company_description}\n\n{job_description}".strip()
                if not self._is_remote_friendly(job, job_description):
                    continue
                results.append(
                    {
                        "job": job,
                        "company_name": company_name,
                        "company_description": company_description,
                        "slug": slug,
                        "full_description": full_description,
                    }
                )

        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = raw["job"]
        company_name = raw["company_name"]
        full_description = raw["full_description"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": str(job.get("shortcode", "")),
            "source_url": job.get("url") or job.get("shortlink") or "",
            "observed_at": datetime.now(timezone.utc),
            "published_at": self._published_at(job),
            "title": job.get("title", ""),
            "body_excerpt": full_description[:5000],
            "company_name_raw": company_name,
            "company_domain_raw": "",
            "location_raw": self._location_text(job),
            "workplace_type": "remote" if job.get("telecommuting") else "",
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
