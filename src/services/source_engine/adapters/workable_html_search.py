"""Workable HTML search-page adapter.

The public JSON API at ``jobs.workable.com/api/v1/jobs`` is aggressively
rate-limited.  The public search pages at ``/search/{country}/{category}-jobs``
contain the same initial payload embedded in ``window.jobBoard.initialState``.
This adapter parses that embedded JSON to extract jobs, their ``workplace``
flag, and ``location``/``company`` metadata, then filters for ANZ and
remote/hybrid roles while rejecting any posting that mentions on-site.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, cast
from urllib.parse import urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class WorkableHtmlSearchAdapter(BaseSourceAdapter):
    """Fetch Workable search pages and extract remote/hybrid ANZ job listings."""

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
            base_url="https://jobs.workable.com",
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
        return "workable_html_search"

    @staticmethod
    def _parse_domain(website: str) -> str:
        if not website:
            return ""
        parsed = urlparse(website)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    @staticmethod
    def _clean_html(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text).strip()

    def _is_remote_friendly(self, job: dict[str, Any], full_text: str) -> bool:
        workplace = (job.get("workplace") or "").lower()
        if workplace in {"remote", "hybrid"}:
            return True
        if workplace == "on_site":
            return False
        has_remote = bool(self._REMOTE_KEYWORDS.search(full_text))
        has_onsite = bool(self._ONSITE_KEYWORDS.search(full_text))
        if has_onsite and not has_remote:
            return False
        return has_remote

    def _is_anz(self, location: dict[str, Any] | None) -> bool:
        if not location:
            return False
        country = (location.get("countryName") or "").lower()
        if country in {"australia", "new zealand"}:
            return True
        text = f"{location.get('city', '')} {location.get('subregion', '')} {country}".lower()
        anz_terms = {
            "australia",
            "new zealand",
            "sydney",
            "melbourne",
            "brisbane",
            "perth",
            "adelaide",
            "canberra",
            "darwin",
            "hobart",
            "auckland",
            "wellington",
            "christchurch",
        }
        return any(term in text for term in anz_terms)

    @staticmethod
    def _location_text(location: dict[str, Any] | None) -> str:
        if not location:
            return ""
        parts = [location.get("city"), location.get("subregion"), location.get("countryName")]
        return ", ".join(p for p in parts if p)

    def _published_at(self, job: dict[str, Any]) -> datetime:
        raw = job.get("created")
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    async def _extract_initial_state(self, html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            text = script.string or ""
            if "window.jobBoard" in text:
                idx = text.find("initialState:")
                if idx == -1:
                    continue
                idx += len("initialState:")
                while idx < len(text) and text[idx] != "{":
                    idx += 1
                depth = 0
                end = idx
                for i in range(idx, len(text)):
                    c = text[i]
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
                try:
                    return cast(dict[str, Any], json.loads(text[idx:end]))
                except json.JSONDecodeError:
                    continue
        return None

    async def _search_page_jobs(self, country: str, category: str) -> list[dict[str, Any]]:
        """Fetch a search page and return the embedded jobs list."""
        category_slug = re.sub(r"[^a-z0-9-]+", "-", category.lower()).strip("-")
        path = f"/search/{country}/{category_slug}-jobs"
        await self.rate_limiter.acquire()
        try:
            response = await self.client.get(path)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        initial_state = await self._extract_initial_state(response.text)
        if not initial_state:
            return []
        jobs_data = cast(dict[str, Any], initial_state.get("api/v1/jobs", {}).get("data", {}))
        return cast(list[dict[str, Any]], jobs_data.get("jobs", []))

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self.config.adapter_config or {}
        countries = query.get("countries") or cfg.get("countries") or ["australia", "new-zealand"]
        categories = (
            query.get("categories")
            or cfg.get("categories")
            or [
                "accountant",
                "remote-accountant",
                "hybrid-accountant",
                "bookkeeper",
                "remote-bookkeeper",
                "hybrid-bookkeeper",
                "payroll",
                "remote-payroll",
                "hybrid-payroll",
                "admin",
                "remote-admin",
                "hybrid-admin",
                "office",
                "remote-office",
                "hybrid-office",
                "receptionist",
                "remote-receptionist",
                "hybrid-receptionist",
                "executive-assistant",
                "remote-executive-assistant",
                "virtual-assistant",
                "legal",
                "remote-legal",
                "hybrid-legal",
                "paralegal",
                "property-manager",
                "remote-property-manager",
                "real-estate",
                "mortgage",
                "insurance",
                "remote-insurance",
                "hybrid-insurance",
                "finance",
                "operations",
                "remote-operations",
                "hybrid-operations",
                "coordinator",
                "remote-coordinator",
                "customer-support",
                "remote-customer-support",
                "sales-support",
                "data-entry",
                "remote-data-entry",
            ]
        )

        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for country in countries:
            for category in categories:
                for job in await self._search_page_jobs(country, category):
                    job_id = str(job.get("id", ""))
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    location = cast(dict[str, Any] | None, job.get("location"))
                    if not self._is_anz(location):
                        continue

                    company = cast(dict[str, Any], job.get("company") or {})
                    company_description = self._clean_html(company.get("description") or "")
                    job_description = self._clean_html(job.get("description") or "")
                    full_text = f"{company.get('title', '')} {company_description} {job.get('title', '')} {job_description} {self._location_text(location)}"

                    if not self._is_remote_friendly(job, full_text):
                        continue

                    results.append(
                        {
                            "job": job,
                            "company": company,
                            "company_description": company_description,
                            "full_text": full_text,
                        }
                    )

        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = cast(dict[str, Any], raw["job"])
        company = cast(dict[str, Any], raw["company"])
        company_description = raw["company_description"]
        job_description = self._clean_html(job.get("description") or "")
        full_description = f"{company_description}\n\n{job_description}".strip()
        location = cast(dict[str, Any] | None, job.get("location"))

        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": str(job.get("id", "")),
            "source_url": job.get("url") or job.get("shortlink") or "",
            "observed_at": datetime.now(timezone.utc),
            "published_at": self._published_at(job),
            "title": job.get("title", ""),
            "body_excerpt": full_description[:5000],
            "company_name_raw": company.get("title", ""),
            "company_domain_raw": self._parse_domain(company.get("website", "")),
            "location_raw": self._location_text(location),
            "workplace_type": job.get("workplace", ""),
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
