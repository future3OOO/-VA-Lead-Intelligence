"""OpenStreetMap Overpass adapter for ANZ small-business leads.

This adapter queries public OpenStreetMap data via the Overpass API for
small businesses in target sectors (real estate, accounting, legal, insurance,
financial advisory, bookkeeping, construction, and trades) in Australia and
New Zealand.  It creates company-centric source hits from business listings
rather than from active job posts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig

# Hosts that should never be treated as a company's primary domain.
_DISALLOWED_PUBLIC_DOMAINS: frozenset[str] = frozenset(
    {
        # Global free email providers
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "hotmail.co.uk",
        "hotmail.com.au",
        "outlook.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "yahoo.com.au",
        "yahoo.co.nz",
        "yahoo.co.uk",
        "aol.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "mail.com",
        "gmx.com",
        "gmx.net",
        "gmx.at",
        "protonmail.com",
        "zoho.com",
        "yandex.com",
        "yandex.ru",
        "mail.ru",
        "fastmail.com",
        # AU / NZ ISPs / free email
        "bigpond.com",
        "bigpond.com.au",
        "tpg.com.au",
        "optusnet.com.au",
        "iinet.net.au",
        "ozemail.com.au",
        "internode.on.net",
        "netspace.net.au",
        "westnet.com.au",
        "vodafone.co.nz",
        "xtra.co.nz",
        "clear.net.nz",
        "slingshot.co.nz",
        "orcon.net.nz",
        "spark.co.nz",
        # Social / directory / map hosts
        "facebook.com",
        "fb.com",
        "instagram.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "tiktok.com",
        "pinterest.com",
        "google.com",
        "google.com.au",
        "google.co.nz",
        "maps.google.com",
        "yellowpages.com.au",
        "truelocal.com.au",
        "whitepages.com.au",
        "hotfrog.com.au",
        "cylex.com.au",
        "localsearch.com.au",
        "bing.com",
        "yelp.com",
        "yelp.com.au",
    }
)


class OpenStreetMapAdapter(BaseSourceAdapter):
    """Fetch ANZ small-business listings from OpenStreetMap via Overpass."""

    _ENDPOINTS = (
        "https://z.overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    )
    _QUERY_ATTEMPTS = 3
    _SERVER_TIMEOUT_SECONDS = 60
    _REQUEST_TIMEOUT_SECONDS = 70.0
    _QUERY_DEADLINE_SECONDS = 180.0
    _OSM_WEB_URL = "https://www.openstreetmap.org"

    # (key, value) -> (title used for VA-role signal, human-readable category label)
    _TAG_MAP: list[tuple[str, str, str, str]] = [
        (
            "office",
            "estate_agent",
            "Property Manager / Real Estate Office",
            "real estate agency providing property management and property services",
        ),
        (
            "office",
            "property_manager",
            "Property Manager / Real Estate Office",
            "real estate agency providing property management and property services",
        ),
        (
            "office",
            "real_estate",
            "Property Manager / Real Estate Office",
            "real estate agency providing property management and property services",
        ),
        (
            "office",
            "accountant",
            "Accountant / Accounting Practice",
            "accounting and tax services practice",
        ),
        ("office", "lawyer", "Lawyer / Legal Practice", "law firm and legal services practice"),
        (
            "office",
            "insurance",
            "Insurance Broker / Insurance Office",
            "insurance brokerage and financial services",
        ),
        (
            "office",
            "financial_advisor",
            "Financial Planner / Financial Advisory",
            "financial planning and advisory practice",
        ),
        (
            "office",
            "bookkeeper",
            "Bookkeeper / Bookkeeping Practice",
            "bookkeeping and accounting support practice",
        ),
        (
            "office",
            "construction_company",
            "Operations Coordinator / Construction Office",
            "construction and home services business",
        ),
        (
            "office",
            "administrative",
            "Administrative Assistant / Office",
            "administrative and business support services",
        ),
        (
            "craft",
            "plumber",
            "Maintenance Coordinator / Plumbing Services",
            "plumbing and home services trade",
        ),
        (
            "craft",
            "electrician",
            "Maintenance Coordinator / Electrical Services",
            "electrical contractor and home services trade",
        ),
        (
            "craft",
            "carpenter",
            "Maintenance Coordinator / Carpentry Services",
            "carpentry and home services trade",
        ),
        (
            "craft",
            "painter",
            "Maintenance Coordinator / Painting Services",
            "painting and home services trade",
        ),
        (
            "craft",
            "roofer",
            "Maintenance Coordinator / Roofing Services",
            "roofing and home services trade",
        ),
        (
            "craft",
            "hvac",
            "Maintenance Coordinator / HVAC Services",
            "hvac and home services trade",
        ),
    ]

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = self._new_async_client(
            timeout=30.0,
            limits=httpx.Limits(),
            headers={"User-Agent": "VA-LeadIntelligence-OSM/1.0"},
        )

    @property
    def source_key(self) -> str:
        return "openstreetmap"

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace('"', '\\"')

    def _is_disallowed_domain(self, domain: str) -> bool:
        """Reject public email, social, and directory hosts as company domains."""
        if not domain:
            return True
        domain = domain.lower().strip()
        if domain in _DISALLOWED_PUBLIC_DOMAINS:
            return True
        return any(domain.endswith("." + d) for d in _DISALLOWED_PUBLIC_DOMAINS)

    def _coerce_domain(self, raw: str) -> str:
        if not raw:
            return ""
        if "://" not in raw:
            raw = "https://" + raw
        parsed = urlparse(raw)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if "/" in domain or "?" in domain:
            return ""
        if self._is_disallowed_domain(domain):
            return ""
        return domain

    @staticmethod
    def _first(tags: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            value = tags.get(key)
            if value:
                return str(value)
        return ""

    def _build_query(
        self, area: str, key: str, value: str, element_types: list[str] | None = None
    ) -> str:
        element_types = element_types or ["node", "way", "relation"]
        selectors = "\n".join(
            f'  {t}["{self._escape(key)}"="{self._escape(value)}"](area.searchArea);'
            for t in element_types
        )
        return (
            f"[out:json][timeout:{self._SERVER_TIMEOUT_SECONDS}];\n"
            f'area[name="{self._escape(area)}"]->.searchArea;\n'
            f"(\n"
            f"{selectors}\n"
            f");\n"
            f"out center body;"
        )

    async def _execute_query(self, query: str) -> dict[str, Any] | None:
        """Post a query to the configured Overpass endpoints with retries."""
        last_error: Exception | None = None
        client_error = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._QUERY_DEADLINE_SECONDS
        for attempt in range(self._QUERY_ATTEMPTS):
            for endpoint in self._ENDPOINTS:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    response = await self._http_post(
                        endpoint,
                        content=query,
                        headers={"Content-Type": "text/plain"},
                        timeout=min(self._REQUEST_TIMEOUT_SECONDS, remaining),
                    )
                except Exception as exc:
                    last_error = exc
                    continue
                if response.status_code >= 400:
                    last_error = httpx.HTTPStatusError(
                        f"Overpass {endpoint} returned {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    if response.status_code in (429, 503, 504):
                        continue
                    client_error = True
                    break
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        return {str(key): value for key, value in data.items()}
                    last_error = ValueError("Overpass response is not a JSON object")
                except Exception as exc:
                    last_error = exc
            if client_error:
                break
            if attempt < self._QUERY_ATTEMPTS - 1:
                delay = float(2**attempt)
                if deadline - loop.time() <= delay:
                    break
                await asyncio.sleep(delay)
        if last_error:
            self.metrics.record_error("fetch")
        return None

    def _location_text(self, element: dict[str, Any], area: str, tags: dict[str, Any]) -> str:
        parts = []
        for key in ("addr:housenumber", "addr:unit"):
            v = tags.get(key)
            if v:
                parts.append(str(v))
        for key in ("addr:street", "addr:suburb", "addr:city", "addr:state", "addr:postcode"):
            v = tags.get(key)
            if v:
                parts.append(str(v))
        if not parts:
            lat = element.get("lat") or element.get("center", {}).get("lat")
            lon = element.get("lon") or element.get("center", {}).get("lon")
            if lat and lon:
                parts.append(f"{lat},{lon}")
        parts.append(area)
        return ", ".join(str(p) for p in parts)[:255]

    def _company_name(self, tags: dict[str, Any]) -> str:
        name = str(tags.get("name", "")).strip()
        if not name:
            name = str(tags.get("brand", "")).strip()
        branch = str(tags.get("branch", "")).strip()
        suburb = str(tags.get("addr:suburb", "")).strip()
        qualifier = branch or suburb
        if qualifier and qualifier.lower() not in name.lower():
            name = f"{name} - {qualifier}"
        return name[:255]

    def _normalize_element(
        self,
        workspace_id: UUID,
        area: str,
        key: str,
        value: str,
        title: str,
        category: str,
        element: dict[str, Any],
    ) -> dict[str, Any] | None:
        tags = element.get("tags") or {}
        if not tags or not tags.get("name"):
            return None

        company_name = self._company_name(tags)
        if not company_name:
            return None

        element_type = element.get("type", "node")
        element_id = str(element.get("id", ""))

        website = self._first(tags, ["website", "contact:website", "facebook", "contact:facebook"])
        email = self._first(tags, ["email", "contact:email"])
        phone = self._first(tags, ["phone", "contact:phone"])

        routes: list[dict[str, Any]] = []
        if email:
            routes.append({"type": "generic_email", "value": email, "is_verified": False})
        if phone:
            routes.append({"type": "business_phone", "value": phone, "is_verified": False})
        # OSM operator tags are typically a business or brand name, not an
        # individual person, so we do not mint named-contact routes here.

        address_parts = []
        for key in (
            "addr:housenumber",
            "addr:unit",
            "addr:street",
            "addr:suburb",
            "addr:city",
            "addr:state",
            "addr:postcode",
        ):
            v = tags.get(key)
            if v:
                address_parts.append(f"{key.replace('addr:', '').title()}: {v}")
        address = "; ".join(address_parts)

        brand = str(tags.get("brand", "")).strip()
        operator = str(tags.get("operator", "")).strip()
        osm_url = f"{self._OSM_WEB_URL}/{element_type}/{element_id}"

        body = (
            f"OpenStreetMap business listing for {company_name}. {company_name} is a {category}. "
        )
        if address:
            body += f"Address: {address}. "
        if brand:
            body += f"Brand: {brand}. "
        if operator:
            body += f"Operator: {operator}. "
        body += f"Source: {osm_url}."

        domain = self._coerce_domain(website)
        if not domain and email and "@" in email:
            email_domain = email.split("@")[-1].strip().lower()
            domain = self._coerce_domain(email_domain)

        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": f"{element_type}/{element_id}",
            "source_url": website or osm_url,
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": title,
            "body_excerpt": body[:5000],
            "company_name_raw": company_name,
            "company_domain_raw": domain,
            "location_raw": self._location_text(element, area, tags),
            "workplace_type": "inferred_remote_friendly",
            "contact_routes_raw": routes,
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self.config.adapter_config or {}
        areas = cfg.get("areas", ["Australia", "New Zealand"])
        tag_map = cfg.get("tags") or [
            {"key": k, "value": v, "title": t, "category": c} for k, v, t, c in self._TAG_MAP
        ]

        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for area in areas:
            for tag in tag_map:
                key = tag["key"]
                value = tag["value"]
                title = tag.get("title", "")
                category = tag.get("category", "")
                # Use node-only queries by default. Overpass node counts are the
                # largest and most reliable for ANZ business listings; way/relation
                # lookups frequently time out.
                element_sets = tag.get("element_types") or [["node"]]
                if not isinstance(element_sets[0], list):
                    element_sets = [element_sets]

                data: dict[str, Any] | None = None
                for element_types in element_sets:
                    overpass_query = self._build_query(area, key, value, element_types)
                    data = await self._execute_query(overpass_query)
                    if data is not None:
                        break

                if data is None:
                    raise httpx.HTTPError(
                        f"openstreetmap incomplete: query failed for {area} {key}={value}"
                    )

                for element in data.get("elements", []):
                    element_id = f"{element.get('type')}/{element.get('id')}"
                    if element_id in seen_ids:
                        continue
                    seen_ids.add(element_id)
                    normalized = self._normalize_element(
                        workspace_id, area, key, value, title, category, element
                    )
                    if normalized:
                        results.append(normalized)

        return results

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        return raw
