"""Client for delegating crawl jobs to the Crawlee service."""
from __future__ import annotations

import os
from typing import Any, cast

import httpx


class CrawlerClient:
    """HTTP client for the internal Crawlee crawling service."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url or os.environ.get("CRAWLER_BASE_URL", "http://localhost:3000")
        self.timeout = timeout

    async def submit_job(self, workspace_id: str, source_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Submit a crawl job and return the accepted job metadata."""
        payload = {
            "workspace_id": workspace_id,
            "source_id": source_id,
            "config": config,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/crawl", json=payload)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def health(self) -> dict[str, Any]:
        """Check crawler health."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
