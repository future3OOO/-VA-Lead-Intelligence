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


class _TitleExtractor(HTMLParser):
    """Extract the page <title>."""

    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)

    def get_title(self) -> str:
        return "".join(self.title).strip()


class CompanyWebAdapter(BaseSourceAdapter):
    """Fetch up to eight high-signal company pages and extract evidence."""

    DEFAULT_PATHS = [
        "/",
        "/careers",
        "/contact",
        "/contact-us",
        "/about",
        "/support",
        "/services",
        "/locations",
    ]

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

    _PHONE_RE = re.compile(r"\+?[\d][\d\s().\-]{6,19}[\d]", re.UNICODE)
    _DATE_RE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")
    _IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3,}$")
    _TRAILING_ZIP_RE = re.compile(r"^(.*)\s+\d{5}$")
    _ASSET_EXTS = {".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".woff", ".woff2"}

    def _clean_value(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned or set(cleaned) <= {" ", "\t", "\n", "\r"}:
            return None
        if any(c.isdigit() for c in cleaned):
            digits = sum(c.isdigit() for c in cleaned)
            if digits < 7 or digits > 15:
                return None
            compact = re.sub(r"[^0-9./-]", "", cleaned)
            if self._DATE_RE.match(compact) or self._IP_RE.match(compact):
                return None
            # Strip a trailing 5-digit zip that got attached to a phone number.
            match = self._TRAILING_ZIP_RE.match(cleaned)
            if match:
                prefix_digits = sum(c.isdigit() for c in match.group(1))
                if prefix_digits >= 10:
                    cleaned = match.group(1).strip()
                    digits = prefix_digits
            # Reject bare digit strings that don't look like formatted phone numbers.
            if all((c.isdigit() or c.isspace()) for c in cleaned) and digits not in (10, 11):
                return None
        return cleaned

    def _extract_contact_routes(self, text: str, html: str) -> list[dict[str, str]]:
        routes: list[dict[str, str]] = []
        seen: set[str] = set()
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        for email in set(emails):
            email = email.strip().lower()
            if "example.com" in email or "test.com" in email or email in seen:
                continue
            seen.add(email)
            routes.append({"type": "generic_email", "value": email})
        for match in self._PHONE_RE.finditer(text):
            phone = self._clean_value(match.group(0))
            if phone and phone not in seen:
                seen.add(phone)
                routes.append({"type": "business_phone", "value": phone})
        for match in re.finditer(
            r'href=["\'](https?://[^"\']+(?:contact|demo|book|quote|sales)[^"\']*)["\']',
            html,
            re.I,
        ):
            url = match.group(1)
            if any(url.lower().endswith(ext) for ext in self._ASSET_EXTS):
                continue
            if "facebook" in url.lower() or "wp-json" in url.lower() or "oembed" in url.lower():
                continue
            if url not in seen:
                seen.add(url)
                routes.append({"type": "sales_form", "value": url})
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
                title_extractor = _TitleExtractor()
                title_extractor.feed(html)
                jsonld = self._extract_jsonld(html)
                contact_routes = self._extract_contact_routes(visible, html)
                results.append(
                    {
                        "domain": domain,
                        "url": str(response.url),
                        "text": visible,
                        "title": title_extractor.get_title(),
                        "jsonld": jsonld,
                        "contact_routes": contact_routes,
                    }
                )
            except httpx.HTTPError:
                continue
        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        jsonld = raw.get("jsonld", {})
        name = jsonld.get("name") or raw.get("title") or raw["domain"]
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
