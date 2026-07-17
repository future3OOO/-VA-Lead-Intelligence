"""Jobicy remote jobs API adapter (public, zero-auth)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class JobicyAdapter(BaseSourceAdapter):
    """Fetch remote job listings from Jobicy's public API and resolve company domains.

    Jobicy is a remote-only job aggregator.  This adapter queries by geo + industry
    and then fetches each company page to extract the company website from the
    "Report this company" Airtable form prefill.  The result is normalized into the
    standard SourceHit contract.
    """

    _REMOTE_KEYWORDS = re.compile(
        r"\b(remote|hybrid|wfh|work from home|work at home|telecommut)\b", re.I
    )
    _ONSITE_KEYWORDS = re.compile(
        r"\b(on[-\s]?site|on site|in[-\s]?office|in office|office[-\s]?based|site[-\s]?based)\b",
        re.I,
    )
    _WEBSITE_RE = re.compile(r'prefill_website=([^"&\s]+)', re.I)

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(
            base_url="https://jobicy.com",
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        self._company_domain_cache: dict[str, str] = {}

    @property
    def source_key(self) -> str:
        return "jobicy"

    def _is_remote_friendly(self, job: dict[str, Any]) -> bool:
        """Reject any posting that explicitly mentions on-site requirements."""
        text = f"{job.get('jobTitle', '')} {job.get('jobDescription', '')}"
        has_remote = bool(self._REMOTE_KEYWORDS.search(text))
        has_onsite = bool(self._ONSITE_KEYWORDS.search(text))
        return not (has_onsite and not has_remote)

    @staticmethod
    def _company_slug(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug[:100]

    async def _resolve_company_domain(self, company_name: str) -> str:
        if company_name in self._company_domain_cache:
            return self._company_domain_cache[company_name]
        slug = self._company_slug(company_name)
        if not slug:
            self._company_domain_cache[company_name] = ""
            return ""
        await self.rate_limiter.acquire()
        try:
            response = await self.client.get(f"/company/{slug}")
            response.raise_for_status()
            match = self._WEBSITE_RE.search(response.text)
            if match:
                website = match.group(1)
                # The parameter may be URL-encoded; httpx will parse it.
                domain = httpx.URL(website).host or ""
                if domain.startswith("www."):
                    domain = domain[4:]
                self._company_domain_cache[company_name] = domain
                return self._company_domain_cache[company_name]
        except httpx.HTTPError:
            pass
        self._company_domain_cache[company_name] = ""
        return ""

    async def _fetch_batch(
        self,
        geo: str,
        extra_params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        count = int(
            self.config.adapter_config.get("count", 100)
            if isinstance(self.config.adapter_config, dict)
            else 100
        )
        await self.rate_limiter.acquire()
        params: dict[str, Any] = {"count": count, "geo": geo}
        params.update(extra_params)
        try:
            response = await self.client.get("/api/v2/remote-jobs", params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return []
        jobs = data.get("jobs", [])
        return [{"job": job, "geo": geo} for job in jobs if self._is_remote_friendly(job)]

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self.config.adapter_config or {}
        geos = query.get("geos") or cfg.get("geos") or ["australia", "new-zealand"]
        industries = query.get("industries") or cfg.get("industries") or []
        tags = query.get("tags") or cfg.get("tags") or []

        results: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        for geo in geos:
            for industry in industries:
                for job in await self._fetch_batch(geo, {"industry": industry}):
                    jid = job["job"].get("id")
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    results.append(job)
            for tag in tags:
                for job in await self._fetch_batch(geo, {"tag": tag}):
                    jid = job["job"].get("id")
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    results.append(job)

        # Resolve company domains in a second pass, one page per unique company.
        unique_companies = {r["job"]["companyName"] for r in results if r["job"].get("companyName")}
        for company_name in unique_companies:
            await self._resolve_company_domain(company_name)

        return results

    def _published_at(self, job: dict[str, Any]) -> datetime:
        raw = job.get("pubDate")
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        job = raw["job"]
        company_name = job.get("companyName", "")
        description = re.sub(r"<[^>]+>", "", job.get("jobDescription") or "").strip()
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": str(job.get("id", "")),
            "source_url": job.get("url") or "",
            "observed_at": datetime.now(timezone.utc),
            "published_at": self._published_at(job),
            "title": job.get("jobTitle", ""),
            "body_excerpt": description[:5000],
            "company_name_raw": company_name,
            "company_domain_raw": self._company_domain_cache.get(company_name, ""),
            "location_raw": job.get("jobGeo") or "",
            "workplace_type": "remote",
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
