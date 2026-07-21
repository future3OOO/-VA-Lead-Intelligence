"""Search API adapter for discovering company pages and ATS footprints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig


class SearchDiscoveryAdapter(BaseSourceAdapter):
    """Use a licensed search API to discover URLs for later verification."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self.client = httpx.AsyncClient(timeout=30.0)

    @property
    def source_key(self) -> str:
        return "search_discovery"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        api_key = query.get("api_key") or self.config.adapter_config.get("api_key")
        cx = query.get("cx") or self.config.adapter_config.get("cx")
        provider = self.config.adapter_config.get("provider", "google_custom_search")
        q = query.get("q", "")
        if not api_key or not q:
            return []
        if provider == "serpapi":
            url = "https://serpapi.com/search"
            params = {"api_key": api_key, "engine": "google", "q": q, "num": 10}
        else:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": api_key, "cx": cx, "q": q, "num": 10}
        response = await self._request("GET", url, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", []) if "items" in data else data.get("organic_results", [])
        return [{"provider": provider, "item": item} for item in items]

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        item = raw["item"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": item.get("link", ""),
            "source_url": item.get("link") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": item.get("title", ""),
            "body_excerpt": item.get("snippet", "")[:2000],
            "company_name_raw": "",
            "company_domain_raw": "",
            "location_raw": "",
            "workplace_type": "",
            "contact_routes_raw": [],
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
