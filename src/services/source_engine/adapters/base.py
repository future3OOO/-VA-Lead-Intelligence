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
from urllib.robotparser import RobotFileParser
from uuid import UUID

import httpx

from services.source_engine.checkpoint import CheckpointStore
from services.source_engine.config import SourceConfig
from services.source_engine.metrics import SourceMetrics
from services.source_engine.rate_limit import RateLimiter


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


async def _resolve_public_ips(host: str) -> list[str]:
    """Resolve a hostname and return only public IP addresses.

    Raises httpx.HTTPError if the host cannot be resolved or has no public IP.
    """
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise httpx.HTTPError(f"DNS resolution failed for {host}: {exc}") from exc
    if not infos:
        raise httpx.HTTPError(f"No DNS records for {host}")

    ips: list[str] = []
    for _family, _socktype, _proto, _canonname, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if not ip.is_global:
            raise httpx.HTTPError(f"Non-public IP resolved for {host}: {ip}")
        ips.append(str(ip))
    if not ips:
        raise httpx.HTTPError(f"No public IP for {host}")
    return ips


async def _is_safe_host(host: str) -> bool:
    """Return True if the hostname resolves to at least one public IP."""
    try:
        await _resolve_public_ips(host)
    except httpx.HTTPError:
        return False
    return True


class _SafeAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """httpx transport that pins each connection to a validated public IP.

    DNS resolution is performed immediately before the TCP connect, the Host
    header and TLS SNI are preserved from the original hostname, and the
    connection is made directly to the validated IP. This closes the DNS
    rebinding window where a hostname resolves to a public address at validation
    time and a private address at connect time.
    """

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        original_url = request.url
        host = original_url.host

        if not _is_safe_domain(host):
            raise httpx.HTTPError(f"Unsafe host requested: {host}")

        # Resolve and validate public IP(s) immediately before connecting.
        ips = await _resolve_public_ips(host)
        ip = ips[0]
        if isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address):
            ip = f"[{ip}]"

        # Build an origin pointing to the validated IP while keeping the Host
        # header and TLS SNI on the original domain.
        new_url = original_url.copy_with(host=ip)
        headers = httpx.Headers(request.headers)
        headers["host"] = host
        extensions = dict(request.extensions)
        extensions.setdefault("sni_hostname", host)

        new_request = httpx.Request(
            method=request.method,
            url=new_url,
            headers=headers,
            content=request.content,
            extensions=extensions,
        )
        return await super().handle_async_request(new_request)


class BaseSourceAdapter(ABC):
    """Abstract base for a compliant source adapter."""

    def __init__(self, source_config: SourceConfig) -> None:
        self.config = source_config
        self.rate_limiter = RateLimiter.from_config(source_config.rate_limit)
        self.checkpoint = CheckpointStore(source_config.source_key)
        self.metrics = SourceMetrics(source_config.source_key)
        self.client: httpx.AsyncClient | None = None
        self._robots_cache: dict[str, RobotFileParser] = {}

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
        return _is_safe_domain(domain)

    async def _is_safe_host(self, host: str) -> bool:
        """Resolve a hostname and reject any non-public IP addresses."""
        return await _is_safe_host(host)

    async def _is_safe_url(self, url: str) -> bool:
        """Validate scheme and host syntax for an HTTP(S) URL.

        The _SafeAsyncHTTPTransport performs the actual DNS resolution and IP
        validation at connect time, so DNS rebinding cannot bypass this gate.
        """
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        return _is_safe_domain(host)

    def _safe_domain(self, raw: str) -> str | None:
        """Return a sanitized public domain or None."""
        parsed = urlparse(raw)
        host = (parsed.netloc or raw).split(":")[0].lower().strip()
        if not _is_safe_domain(host):
            return None
        return host

    async def _robots_allowed(self, url: str, user_agent: str = "VALeadBot/1.0") -> bool:
        """Respect robots.txt for any public HTTP URL. Unknown/failed robots.txt is allowed."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url].can_fetch(user_agent, url)
        rp = RobotFileParser(robots_url)
        try:
            response = await self._http_get(
                robots_url,
                timeout=5.0,
                headers={"User-Agent": user_agent},
            )
            rp.parse(response.text.splitlines())
        except Exception:
            pass
        self._robots_cache[robots_url] = rp
        return rp.can_fetch(user_agent, url)

    def _new_async_client(
        self,
        timeout: httpx.Timeout | float,
        limits: httpx.Limits,
        headers: dict[str, str],
        retries: int = 0,
    ) -> httpx.AsyncClient:
        """Create an httpx client whose transport pins DNS to a public IP.

        Keep-alive is disabled so connections are never reused across different
        original hostnames that happen to resolve to the same IP, closing the
        SNI/connection-pooling host-isolation gap.
        """
        safe_limits = httpx.Limits(
            max_connections=limits.max_connections,
            max_keepalive_connections=0,
            keepalive_expiry=0.0,
        )
        transport = _SafeAsyncHTTPTransport(limits=safe_limits, retries=retries)
        httpx_timeout = timeout if isinstance(timeout, httpx.Timeout) else httpx.Timeout(timeout)
        return httpx.AsyncClient(timeout=httpx_timeout, transport=transport, headers=headers)

    async def _http_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make an HTTP request with per-host rate limiting and manual redirect validation."""
        if self.client is None:
            raise RuntimeError(f"{self.source_key} adapter has no HTTP client")
        kwargs.pop("follow_redirects", None)
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30.0
        client = self.client
        for _ in range(10):
            if not await self._is_safe_url(url):
                raise httpx.HTTPError(f"Unsafe URL requested: {url}")
            parsed = urlparse(url)
            host = parsed.hostname or parsed.netloc
            async with self.rate_limiter.acquire(host):
                response = await client.request(method, url, follow_redirects=False, **kwargs)
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            url = str(response.url.join(location))
            if response.status_code in {301, 302, 303}:
                method = "GET"
        raise httpx.TooManyRedirects("Maximum redirect count exceeded")

    async def _http_get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._http_request("GET", url, **kwargs)

    async def _http_post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._http_request("POST", url, **kwargs)

    async def aclose(self) -> None:
        """Close the adapter's HTTP client and release resources."""
        client = self.client
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
        if not normalized and self.metrics.errors:
            raise httpx.HTTPError(
                f"{self.source_key} produced no usable records ({dict(self.metrics.errors)} errors)"
            )
        self.checkpoint.save(workspace_id, {"observed_at": datetime.now(timezone.utc).isoformat()})
        return normalized
