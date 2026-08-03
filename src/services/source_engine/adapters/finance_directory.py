"""Bounded public-directory adapter for Australian finance professionals."""

from __future__ import annotations

import asyncio
import json
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig

_INSTITUTION_RE = re.compile(
    r"\b(?:"
    r"bank|credit\s+union|building\s+society|insurance\s+company|reserve\s+bank|"
    r"commonwealth|westpac|nab|cba|anz|macquarie|suncorp|ing|citigroup|"
    r"arab\s+bank|bankwest|bendigo|bank\s+of\s+queensland|beyond\s+bank|"
    r"plc|llp|lp|holdings|trust|fund|funds|association|union"
    r")\b",
    re.I,
)


class FinanceDirectoryAdapter(BaseSourceAdapter):
    """Fetch profile pages from a public finance-professionals directory."""

    source_key = "finance_directory"

    _SITEMAP_URL = (
        "https://www.financedirectory.net.au/filedata/cache/xml-sitemaps/profile-filename-1.xml"
    )

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = self._new_async_client(
            httpx.Timeout(15.0, connect=5.0, read=15.0, write=5.0, pool=5.0),
            httpx.Limits(max_connections=50, max_keepalive_connections=20),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )

    def _looks_like_small_business(self, name: str, description: str) -> bool:
        text = f"{name} {description}"
        if _INSTITUTION_RE.search(text):
            return False
        lower = text.lower()
        return any(
            kw in lower
            for kw in (
                "mortgage",
                "insurance",
                "accounting",
                "accountant",
                "bookkeeping",
                "bookkeeper",
                "financial advice",
                "financial planning",
                "finance broker",
                "mortgage broker",
                "insurance broker",
                "home loan",
                "investment loan",
                "refinancing",
                "tax",
                "bas",
                "smsf",
                "lending",
                "broker",
                "adviser",
                "advisor",
            )
        )

    def _extract_jsonld(self, soup: BeautifulSoup) -> dict[str, Any]:
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            items: list[dict[str, Any]] = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if "@graph" in data:
                    graph = data["@graph"]
                    items = graph if isinstance(graph, list) else [graph]
                else:
                    items = [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if str(item.get("@type", "")).lower() == "localbusiness":
                    return item
        return {}

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

    def _coerce_domain(self, url: str) -> str:
        if not url:
            return ""
        if "//" not in url and ":" not in url:
            url = "https://" + url
        parsed = urlparse(url)
        host = re.sub(r"^www\.", "", parsed.netloc.lower())
        if not host:
            return ""
        directory_host = re.sub(r"^www\.", "", urlparse(self._SITEMAP_URL).netloc.lower())
        if host == directory_host or host.endswith("." + directory_host):
            return ""
        if host in self._DISALLOWED_HOSTS or any(
            host.endswith("." + d) for d in self._DISALLOWED_HOSTS
        ):
            return ""
        return host

    def _best_website(self, data: dict[str, Any]) -> str:
        """Prefer a real business website over social/directory URLs."""
        candidates: list[str] = []
        url = str(data.get("url", "")).strip()
        if url:
            candidates.append(url)
        same_as = data.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        for link in same_as:
            if isinstance(link, str):
                candidates.append(link)

        directory_host = re.sub(r"^www\.", "", urlparse(self._SITEMAP_URL).netloc.lower())
        for link in candidates:
            if not link:
                continue
            if not link.startswith(("http://", "https://")):
                link = "https://" + link
            parsed = urlparse(link)
            host = re.sub(r"^www\.", "", parsed.netloc.lower())
            if not host:
                continue
            if host == directory_host or host.endswith("." + directory_host):
                continue
            if host in self._DISALLOWED_HOSTS or any(
                host.endswith("." + d) for d in self._DISALLOWED_HOSTS
            ):
                continue
            return link
        return ""

    async def _fetch_profile(self, url: str) -> dict[str, Any] | None:
        if not await self._robots_allowed(url):
            return None
        try:
            response = await self._http_get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError:
            # 4xx/5xx on an individual profile page is a stale URL, not a source failure.
            return None
        except httpx.HTTPError:
            self.metrics.record_error("fetch")
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        data = self._extract_jsonld(soup)
        if not data:
            return None
        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()
        if not name:
            return None
        if not self._looks_like_small_business(name, description):
            return None
        telephone = str(data.get("telephone", "")).strip()
        website = self._best_website(data)
        address = data.get("address", {})
        location = ""
        if isinstance(address, dict):
            parts = [
                address.get("streetAddress", ""),
                address.get("addressLocality", ""),
                address.get("addressRegion", ""),
                address.get("postalCode", ""),
            ]
            location = ", ".join(p for p in parts if p)
        contact_routes: list[dict[str, Any]] = []
        if telephone:
            contact_routes.append(
                {"type": "business_phone", "value": telephone, "is_verified": False}
            )
        return {
            "url": url,
            "name": name,
            "description": description,
            "telephone": telephone,
            "website": website,
            "location": location,
            "contact_routes": contact_routes,
        }

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        max_profiles = int(
            query.get("max_profile_pages")
            or self.config.adapter_config.get("max_profile_pages", 1200)
        )
        if not await self._robots_allowed(self._SITEMAP_URL):
            self.metrics.record_error("fetch")
            raise httpx.HTTPError("finance_directory robots.txt disallows the sitemap")
        try:
            sitemap_response = await self._http_get(self._SITEMAP_URL, timeout=30.0)
            sitemap_response.raise_for_status()
        except httpx.HTTPError as exc:
            self.metrics.record_error("fetch")
            raise httpx.HTTPError(f"finance_directory could not fetch sitemap: {exc}") from exc
        root = ET.fromstring(sitemap_response.content)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls: list[str] = []
        for loc in root.findall(".//ns:loc", ns):
            if loc.text and "/finance/" in loc.text and loc.text != self._SITEMAP_URL:
                urls.append(loc.text)
        # Shuffle to spread across categories, then cap.
        random.shuffle(urls)
        urls = urls[:max_profiles]

        results: list[dict[str, Any]] = []
        counter = 0
        for chunk_start in range(0, len(urls), 5):
            chunk = urls[chunk_start : chunk_start + 5]
            tasks = [asyncio.create_task(self._fetch_profile(u)) for u in chunk]
            for task in asyncio.as_completed(tasks):
                result = await task
                counter += 1
                if counter % 100 == 0:
                    print(f"[finance_directory] {counter}/{len(urls)} profiles fetched", flush=True)
                if result:
                    results.append(result)
        print(f"[finance_directory] extracted {len(results)} profile pages", flush=True)
        await self.aclose()
        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        company_name = raw["name"]
        description = raw["description"]
        location = raw["location"]
        body = (
            f"{description} "
            f"{company_name} is an Australian financial services provider in {location or 'Australia'}."
        )
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": raw["url"],
            "source_url": raw["url"],
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": f"Finance Directory listing for {company_name}",
            "body_excerpt": body[:5000],
            "company_name_raw": company_name,
            "company_domain_raw": self._coerce_domain(raw["website"]),
            "location_raw": location,
            "workplace_type": "inferred_remote_friendly",
            "contact_routes_raw": raw.get("contact_routes", []),
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
