"""Base source adapter with operational controls."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from services.source_engine.checkpoint import CheckpointStore
from services.source_engine.config import SourceConfig
from services.source_engine.metrics import SourceMetrics
from services.source_engine.rate_limit import RateLimiter


class BaseSourceAdapter(ABC):
    """Abstract base for a compliant source adapter."""

    def __init__(self, source_config: SourceConfig) -> None:
        self.config = source_config
        self.rate_limiter = RateLimiter.from_config(source_config.rate_limit)
        self.checkpoint = CheckpointStore(source_config.source_key)
        self.metrics = SourceMetrics(source_config.source_key)
        self.client: httpx.AsyncClient | None = None

    @property
    @abstractmethod
    def source_key(self) -> str:
        """Stable source identifier matching the registry."""
        ...

    @property
    def enabled(self) -> bool:
        return self.config.status == "enabled"

    def kill_switched(self) -> bool:
        """Check the runtime kill switch from environment variables.

        The kill switch string is a dotted path like ``sources.greenhouse.enabled``.
        It is mapped to an upper-case, underscore-separated environment variable
        (``SOURCES_GREENHOUSE_ENABLED``). A value of ``false``/``0``/``no`` disables
        the source; any other explicit value keeps it enabled. Missing variables mean
        the source is not switched off.
        """
        kill = self.config.kill_switch
        if not kill:
            return False
        env_name = kill.replace(".", "_").upper()
        value = os.environ.get(env_name, "")
        if not value:
            return False
        return value.lower() in ("false", "0", "no", "disabled")

    @abstractmethod
    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch raw records from the source."""
        ...

    @abstractmethod
    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw record into a SourceHit dict."""
        ...

    _STRING_FIELDS: dict[str, int] = {
        "source_url": 2048,
        "title": 255,
        "body_excerpt": 5000,
        "company_name_raw": 255,
        "company_domain_raw": 255,
        "location_raw": 255,
        "workplace_type": 255,
        "source_native_id": 255,
        "content_hash": 255,
        "raw_snapshot_uri": 255,
        "access_policy_version": 255,
    }

    def _coerce_strings(self, hit: dict[str, Any]) -> None:
        """Ensure non-nullable string fields are never None and fit column limits."""
        for field, limit in self._STRING_FIELDS.items():
            value = hit.get(field)
            if value is None:
                value = ""
            if isinstance(value, str) and len(value) > limit:
                value = value[:limit]
            hit[field] = value
        if hit.get("contact_routes_raw") is None:
            hit["contact_routes_raw"] = []
        # source_url is stored as a string but must not be empty; use a placeholder
        # when the upstream record provides no URL so downstream reads never crash.
        if not hit.get("source_url"):
            hit["source_url"] = "http://localhost"

    @staticmethod
    def _is_safe_domain(domain: str) -> bool:
        """Reject internal, local, and IP-like hosts to prevent SSRF."""
        if not domain:
            return False
        host = domain.split(":")[0].lower().strip()
        if not host or "." not in host:
            return False
        if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
            return False
        if any(
            host.endswith(suffix)
            for suffix in {".local", ".internal", ".localhost", ".svc", ".cluster.local"}
        ):
            return False
        if host in {"metadata.google.internal", "169.254.169.254", "metadata.aws.internal"}:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return re.match(r"^[a-z0-9][-a-z0-9]*(?:\.[-a-z0-9]+)+$", host) is not None

    async def _is_safe_host(self, host: str) -> bool:
        """Resolve a hostname and reject any non-public IP addresses."""
        try:
            infos = await asyncio.to_thread(
                socket.getaddrinfo, host, None, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
        except socket.gaierror:
            return False
        if not infos:
            return False
        for _family, _socktype, _proto, _canonname, sockaddr in infos:
            try:
                ip = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                continue
            if not ip.is_global:
                return False
        return True

    async def _is_safe_url(self, url: str) -> bool:
        """Validate scheme, host syntax, and DNS resolution for an HTTP(S) URL."""
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        if not self._is_safe_domain(host):
            return False
        return await self._is_safe_host(host)

    def _safe_domain(self, raw: str) -> str | None:
        """Return a sanitized public domain or None."""
        parsed = urlparse(raw)
        host = (parsed.netloc or raw).split(":")[0].lower().strip()
        if not self._is_safe_domain(host):
            return None
        return host

    async def _http_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make an HTTP request with per-host rate limiting and manual redirect validation."""
        if self.client is None:
            raise RuntimeError(f"{self.source_key} adapter has no HTTP client")
        kwargs.pop("follow_redirects", None)
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30.0
        if not await self._is_safe_url(url):
            raise httpx.HTTPError(f"Unsafe URL requested: {url}")
        parsed = urlparse(url)
        host = parsed.hostname or parsed.netloc
        client = self.client
        async with self.rate_limiter.acquire(host):
            for _ in range(10):
                response = await client.request(method, url, follow_redirects=False, **kwargs)
                if response.status_code not in {301, 302, 303, 307, 308}:
                    return response
                location = response.headers.get("location")
                if not location:
                    return response
                next_url = str(response.url.join(location))
                if not await self._is_safe_url(next_url):
                    raise httpx.HTTPError(f"Unsafe redirect to {next_url}")
                url = next_url
                if response.status_code in {301, 302, 303}:
                    method = "GET"
            raise httpx.TooManyRedirects("Maximum redirect count exceeded")

    async def _http_get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._http_request("GET", url, **kwargs)

    async def _http_post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._http_request("POST", url, **kwargs)

    async def aclose(self) -> None:
        """Close the adapter's HTTP client and release resources."""
        client = getattr(self, "client", None)
        if client is not None:
            await client.aclose()

    async def run(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch and normalize records with rate limiting and metrics."""
        if not self.enabled or self.kill_switched():
            return []
        raw_records = await self.fetch(workspace_id, query)
        self.metrics.record_hits(len(raw_records))
        normalized: list[dict[str, Any]] = []
        for raw in raw_records:
            try:
                hit = self.normalize(workspace_id, raw)
                self._coerce_strings(hit)
                normalized.append(hit)
            except Exception:
                self.metrics.record_error("normalize")
        self.checkpoint.save(workspace_id, {"observed_at": datetime.now(timezone.utc).isoformat()})
        return normalized
