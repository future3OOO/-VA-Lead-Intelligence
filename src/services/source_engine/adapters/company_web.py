"""Bounded company-website crawler for named contacts and public contact routes.

This adapter does a polite, breadth-first crawl of each company domain,
concentrating on pages that are likely to contain people and contact details
(/about, /team, /contact, /people, /leadership, etc.). It reuses the same
extraction heuristics as team_pages but discovers more URLs per domain.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.team_pages import _extract_from_soup
from services.source_engine.config import SourceConfig


class CompanyWebAdapter(BaseSourceAdapter):
    """Crawl company websites for contact routes and named people."""

    source_key = "company_web"

    _PRIORITY_KEYWORDS = {
        "about",
        "team",
        "people",
        "staff",
        "leadership",
        "management",
        "executive",
        "director",
        "board",
        "contact",
        "meet",
        "who",
        "company",
        "profile",
    }

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._counter = 0
        self._counter_lock = asyncio.Lock()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0, read=15.0, write=5.0, pool=5.0),
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )

    async def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url].can_fetch("VALeadBot/1.0", url)
        rp = RobotFileParser(robots_url)
        try:
            parsed = urlparse(robots_url)
            async with self.rate_limiter.acquire(parsed.netloc):
                response = await self.client.get(
                    robots_url,
                    timeout=httpx.Timeout(5.0, connect=5.0, read=5.0, write=5.0, pool=5.0),
                    headers={"User-Agent": "VALeadBot/1.0"},
                )
            rp.parse(response.text.splitlines())
        except Exception:
            pass
        self._robots_cache[robots_url] = rp
        return rp.can_fetch("VALeadBot/1.0", url)

    def _priority_score(self, path: str) -> int:
        lower = path.lower()
        return sum(10 for kw in self._PRIORITY_KEYWORDS if kw in lower)

    def _same_domain(self, url: str, domain: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        target = domain.lower()
        if target.startswith("www."):
            target = target[4:]
        return host == target

    async def _sitemap_urls(self, domain: str) -> list[str]:
        sitemap_url = f"https://{domain}/sitemap.xml"
        if not await self._allowed(sitemap_url):
            return []
        try:
            parsed = urlparse(sitemap_url)
            async with self.rate_limiter.acquire(parsed.netloc):
                response = await self.client.get(sitemap_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "xml" not in content_type:
                return []
            root = ET.fromstring(response.content)
            urls: list[str] = []
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//ns:loc", ns):
                if loc.text:
                    urls.append(loc.text)
            return urls
        except Exception:
            return []

    async def _fetch_page(self, url: str) -> tuple[str, BeautifulSoup] | None:
        if not await self._allowed(url):
            return None
        parsed = urlparse(url)
        try:
            async with self.rate_limiter.acquire(parsed.netloc):
                response = await self.client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "text/html" not in content_type:
                return None
            return str(response.url), BeautifulSoup(response.text, "html.parser")
        except httpx.HTTPError:
            return None
        except Exception:
            return None

    async def _crawl_domain(self, domain: str, total: int) -> dict[str, Any] | None:
        async with self._counter_lock:
            self._counter += 1
            idx = self._counter
        print(f"[company_web] {idx}/{total}: {domain}", flush=True)

        visited: set[str] = set()
        routes: list[dict[str, Any]] = []
        discovered: set[str] = set()

        sitemap_urls = await self._sitemap_urls(domain)
        sitemap_urls = [u for u in sitemap_urls if self._same_domain(u, domain)][:50]

        queue: deque[tuple[str, int]] = deque()
        for u in sitemap_urls:
            if u not in visited:
                queue.append((u, 0))
                visited.add(u)
        queue.append((f"https://{domain}", 0))

        pages_crawled = 0
        max_pages = self.config.adapter_config.get("max_pages_per_domain", 20)
        max_depth = self.config.adapter_config.get("max_depth", 2)

        while queue and pages_crawled < max_pages:
            # Prioritise likely contact/team pages first.
            queue = deque(
                sorted(
                    queue, key=lambda item: (-self._priority_score(urlparse(item[0]).path), item[1])
                )
            )
            url, depth = queue.popleft()
            result = await self._fetch_page(url)
            if not result:
                continue
            final_url, soup = result
            pages_crawled += 1

            page_routes = _extract_from_soup(soup, final_url, domain)
            routes.extend(page_routes)

            if depth >= max_depth:
                continue
            try:
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    absolute = urljoin(final_url, href)
                    parsed = urlparse(absolute)
                    if parsed.scheme not in ("http", "https"):
                        continue
                    if not self._same_domain(absolute, domain):
                        continue
                    # Drop anchors, query params that are not pagination/filters, fragments.
                    clean = absolute.split("#")[0]
                    if clean in visited or clean in discovered:
                        continue
                    if depth > 0 and not any(
                        kw in parsed.path.lower() for kw in self._PRIORITY_KEYWORDS
                    ):
                        continue
                    discovered.add(clean)
                    queue.append((clean, depth + 1))
            except Exception:
                continue

        if not routes:
            return None

        return {
            "domain": domain,
            "url": f"https://{domain}",
            "contact_routes": routes,
        }

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        domains = query.get("domains") or self.config.adapter_config.get("domains")
        if not domains:
            single = query.get("domain") or self.config.adapter_config.get("domain")
            domains = [single] if single else []
        if not domains:
            return []

        self._counter = 0
        tasks = [
            asyncio.create_task(self._crawl_domain(domain, len(domains))) for domain in domains
        ]
        results: list[dict[str, Any]] = []
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                results.append(result)
        print(f"[company_web] extracted routes for {len(results)} domains", flush=True)
        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        domain = raw["domain"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": raw["url"],
            "source_url": raw["url"],
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": f"Company website for {domain}",
            "body_excerpt": f"Crawled contact/team pages on {domain}",
            "company_name_raw": domain,
            "company_domain_raw": domain,
            "location_raw": "",
            "workplace_type": "",
            "contact_routes_raw": raw.get("contact_routes", []),
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
