"""Bounded first-party company website verifier/extractor."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if self.skip == 0:
            self.text.append(data)

    def get_text(self) -> str:
        return " ".join(self.text)


class CompanyWebAdapter(BaseSourceAdapter):
    """Fetch up to eight high-signal company pages and extract evidence."""

    DEFAULT_PATHS = ["/", "/careers", "/contact", "/support", "/services", "/locations"]

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    @property
    def source_key(self) -> str:
        return "company_web"

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser(robots_url)
        try:
            rp.read()
            return rp.can_fetch("VALeadBot/1.0", url)
        except Exception:
            return True

    def _extract_jsonld(self, html: str) -> dict[str, Any]:
        for match in re.finditer(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.S | re.I,
        ):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and data.get("@type") in (
                    "Organization",
                    "LocalBusiness",
                ):
                    return data
            except json.JSONDecodeError:
                continue
        return {}

    def _extract_contact_routes(self, text: str, html: str) -> list[dict[str, str]]:
        routes: list[dict[str, str]] = []
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        for email in set(emails):
            if "example.com" not in email and "test.com" not in email:
                routes.append({"type": "generic_email", "value": email})
        phones = re.findall(r"\+?[\d\s().-]{7,20}", text)
        for phone in set(phones):
            routes.append({"type": "business_phone", "value": phone})
        for match in re.finditer(
            r'href=["\'](https?://[^"\']+(?:contact|demo|book|quote|sales)[^"\']*)["\']',
            html,
            re.I,
        ):
            routes.append({"type": "sales_form", "value": match.group(1)})
        return routes

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        domain = query.get("domain") or self.config.adapter_config.get("domain")
        if not domain:
            return []
        scheme = "https"
        base_url = f"{scheme}://{domain}"
        paths = query.get("paths", self.config.adapter_config.get("paths", self.DEFAULT_PATHS))
        results: list[dict[str, Any]] = []
        for path in paths[:8]:
            url = urljoin(base_url, path)
            if not self._allowed(url):
                continue
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                html = response.text
                extractor = _TextExtractor()
                extractor.feed(html)
                visible = extractor.get_text()
                jsonld = self._extract_jsonld(html)
                contact_routes = self._extract_contact_routes(visible, html)
                results.append(
                    {
                        "domain": domain,
                        "url": str(response.url),
                        "text": visible,
                        "jsonld": jsonld,
                        "contact_routes": contact_routes,
                    }
                )
            except httpx.HTTPError:
                continue
        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        jsonld = raw.get("jsonld", {})
        name = jsonld.get("name") or raw["domain"]
        text = raw.get("text", "")
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": raw["url"],
            "source_url": raw["url"],
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": name,
            "body_excerpt": text[:2000],
            "company_name_raw": name,
            "company_domain_raw": raw["domain"],
            "location_raw": jsonld.get("address", {}).get("addressLocality", ""),
            "workplace_type": "",
            "contact_routes_raw": raw.get("contact_routes", []),
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
