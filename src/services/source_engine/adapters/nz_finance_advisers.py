"""Bounded adapter for the NZ Finance Advisers public directory.

Parses paginated adviser listings from financeadvisers.co.nz, fetches each
adviser profile to obtain the adviser name and their employing FAP, then
fetches the provider page for the FAP's website and phone.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.team_pages import _is_plausible_person_name
from services.source_engine.config import SourceConfig

_NZ_BANK_NAMES = {
    "anz",
    "asb",
    "bank",
    "bank of new zealand",
    "bnz",
    "craigs",
    "fisher funds",
    "kiwibank",
    "milford",
    "nzx",
    "sbs bank",
    "sbs",
    "simplicity",
    "tsb",
    "westpac",
    "aarhus",
    "nationwide",
}


def _is_large_institution(name: str) -> bool:
    lower = name.lower()
    words = {w for w in re.split(r"[^a-zA-Z0-9&]+", lower) if w}
    return bool(any(w in _NZ_BANK_NAMES for w in words))


class NzFinanceAdvisersAdapter(BaseSourceAdapter):
    """Fetch named NZ financial advisers from a public directory."""

    source_key = "nz_finance_advisers"

    _BASE_URL = "https://financeadvisers.co.nz"

    _DISALLOWED_HOSTS = {
        "facebook.com",
        "fb.com",
        "linkedin.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "youtube.com",
        "youtu.be",
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "yahoo.com",
        "bigpond.com",
        "bigpond.com.au",
        "aol.com",
        "yandex.com",
        "protonmail.com",
    }

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self._provider_cache: dict[str, dict[str, Any]] = {}
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0, read=15.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )

    def _coerce_domain(self, url: str) -> str:
        if not url or not url.startswith(("http://", "https://")):
            return ""
        parsed = urlparse(url)
        host = re.sub(r"^www\.", "", parsed.netloc.lower())
        if not host:
            return ""
        directory_host = re.sub(r"^www\.", "", urlparse(self._BASE_URL).netloc.lower())
        if host == directory_host or host.endswith("." + directory_host):
            return ""
        if host in self._DISALLOWED_HOSTS or any(
            host.endswith("." + d) for d in self._DISALLOWED_HOSTS
        ):
            return ""
        return host

    async def _get(self, url: str) -> str:
        response = await self._http_get(url)
        response.raise_for_status()
        return response.text

    def _extract_jsonld_by_type(self, html: str, type_name: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == type_name:
                return data
            if isinstance(data, dict) and "@graph" in data:
                for item in data["@graph"]:
                    if isinstance(item, dict) and item.get("@type") == type_name:
                        return item
        return None

    async def _discover_profile_urls(self, max_pages: int) -> list[str]:
        urls: list[str] = []
        for page in range(1, max_pages + 1):
            list_url = f"{self._BASE_URL}/advisers?page={page}"
            try:
                html = await self._get(list_url)
            except httpx.HTTPError:
                continue
            seen_hrefs: set[str] = set()
            item_list = self._extract_jsonld_by_type(html, "ItemList")
            if item_list:
                for element in item_list.get("itemListElement", []):
                    item = element.get("item") if isinstance(element, dict) else None
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") != "Person":
                        continue
                    name = str(item.get("name", "")).strip()
                    if not _is_plausible_person_name(name):
                        continue
                    href = str(element.get("url", "")).strip() or str(item.get("url", "")).strip()
                    if href and href.startswith("http") and href not in seen_hrefs:
                        seen_hrefs.add(href)
                        urls.append(href)
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=re.compile(r"/adviser/[^/]+")):
                href = str(a.get("href", "")).strip()
                if not href or href in seen_hrefs:
                    continue
                name = a.get_text(strip=True)
                if not _is_plausible_person_name(name):
                    continue
                if not href.startswith("http"):
                    href = urljoin(self._BASE_URL, href)
                seen_hrefs.add(href)
                urls.append(href)
        return urls

    async def _fetch_provider(self, provider_url: str) -> dict[str, Any]:
        if provider_url in self._provider_cache:
            return self._provider_cache[provider_url]
        try:
            html = await self._get(provider_url)
        except httpx.HTTPError:
            return {}
        data = self._extract_jsonld_by_type(
            html, "FinancialService"
        ) or self._extract_jsonld_by_type(html, "Organization")
        if not isinstance(data, dict):
            return {}
        result = {
            "name": str(data.get("name", "")).strip(),
            "website": str(data.get("url", "")).strip(),
            "phone": str(data.get("telephone", "")).strip(),
            "address": data.get("address", {}),
        }
        self._provider_cache[provider_url] = result
        return result

    async def _fetch_profile(self, profile_url: str) -> dict[str, Any] | None:
        try:
            html = await self._get(profile_url)
        except httpx.HTTPError:
            return None
        person = self._extract_jsonld_by_type(html, "Person")
        if not person:
            return None
        name = str(person.get("name", "")).strip()
        if not _is_plausible_person_name(name):
            return None
        works_for = person.get("worksFor") or {}
        if not isinstance(works_for, dict):
            return None
        company_name = str(works_for.get("name", "")).strip()
        if _is_large_institution(company_name):
            return None
        provider_url = str(works_for.get("url", "")).strip()
        if provider_url and not provider_url.startswith("http"):
            provider_url = urljoin(self._BASE_URL, provider_url)
        provider: dict[str, Any] = {}
        if provider_url and provider_url.startswith(self._BASE_URL + "/provider/"):
            provider = await self._fetch_provider(provider_url)
        final_company = provider.get("name") or company_name
        if not final_company or _is_large_institution(final_company):
            return None
        website = provider.get("website") or ""
        phone = provider.get("phone") or ""
        address = provider.get("address") or works_for.get("address") or person.get("address") or {}
        if isinstance(address, dict):
            location = ", ".join(
                v
                for v in [
                    address.get("addressLocality", ""),
                    address.get("addressRegion", ""),
                    address.get("addressCountry", ""),
                ]
                if v
            )
        else:
            location = ""
        description = str(person.get("description", "")).strip()
        if not description:
            description = f"{name} is an FSPR-registered {person.get('jobTitle', 'financial adviser')} in {location or 'New Zealand'}."
        return {
            "profile_url": profile_url,
            "name": name,
            "job_title": str(person.get("jobTitle", "Financial Adviser")).strip(),
            "company_name": final_company,
            "website": website,
            "phone": phone,
            "location": location,
            "description": description,
        }

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        max_pages = int(
            query.get("max_list_pages") or self.config.adapter_config.get("max_list_pages", 30)
        )
        profile_urls = await self._discover_profile_urls(max_pages)
        print(
            f"[nz_finance_advisers] discovered {len(profile_urls)} plausible adviser profiles",
            flush=True,
        )
        results: list[dict[str, Any]] = []
        for i, url in enumerate(profile_urls, 1):
            result = await self._fetch_profile(url)
            if i % 100 == 0:
                print(
                    f"[nz_finance_advisers] {i}/{len(profile_urls)} profiles fetched",
                    flush=True,
                )
            if result:
                results.append(result)
        await self.aclose()
        print(
            f"[nz_finance_advisers] extracted {len(results)} adviser records",
            flush=True,
        )
        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        company_name = raw["company_name"]
        description = raw["description"]
        location = raw["location"]
        body = (
            f"{description} "
            f"{company_name} is a New Zealand financial advice provider in {location or 'New Zealand'}. "
            f"Remote/hybrid VA support can help with client onboarding, diary management, CRM updates, "
            f"email triage, compliance documentation and general administrative support."
        )
        domain = self._coerce_domain(raw["website"])
        contact_routes: list[dict[str, Any]] = [
            {
                "type": "named_contact",
                "value": f"{raw['name']} ({raw['job_title']})",
                "is_verified": False,
            }
        ]
        if domain:
            contact_routes.append(
                {"type": "sales_form", "value": raw["website"], "is_verified": False}
            )
        if raw["phone"]:
            contact_routes.append(
                {"type": "business_phone", "value": raw["phone"], "is_verified": False}
            )
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": raw["profile_url"],
            "source_url": raw["profile_url"],
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": f"{raw['name']} — {raw['job_title']} at {company_name}",
            "body_excerpt": body[:5000],
            "company_name_raw": company_name,
            "company_domain_raw": domain,
            "location_raw": location,
            "workplace_type": "hybrid",
            "contact_routes_raw": contact_routes,
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
