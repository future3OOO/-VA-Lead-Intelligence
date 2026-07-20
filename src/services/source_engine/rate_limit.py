"""Token-bucket rate limiter for source adapters with per-host concurrency."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


class RateLimiter:
    """Async token bucket with per-host concurrency and a global cap.

    Use as an async context manager:

        async with rate_limiter.acquire(host="example.com"):
            response = await client.get(url)
    """

    def __init__(
        self,
        requests_per_second: float = 2.0,
        max_concurrency_per_host: int = 1,
        max_total_concurrency: int = 20,
    ) -> None:
        self.requests_per_second = float(requests_per_second)
        self.max_concurrency_per_host = max(1, max_concurrency_per_host)
        self.max_total_concurrency = max(1, max_total_concurrency)
        self._global_sem = asyncio.Semaphore(self.max_total_concurrency)
        self._host_sem: dict[str, asyncio.Semaphore] = {}
        self._host_tokens: dict[str, float] = {}
        self._host_last: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> RateLimiter:
        cfg = config or {}
        return cls(
            requests_per_second=float(cfg.get("requests_per_second", 2.0)),
            max_concurrency_per_host=int(cfg.get("max_concurrency_per_host", 1)),
            max_total_concurrency=int(cfg.get("max_total_concurrency", 20)),
        )

    def _host_state(self, host: str | None) -> tuple[asyncio.Semaphore, str]:
        key = host or "default"
        if key not in self._host_sem:
            self._host_sem[key] = asyncio.Semaphore(self.max_concurrency_per_host)
        return self._host_sem[key], key

    @asynccontextmanager
    async def acquire(self, host: str | None = None) -> AsyncGenerator[None, None]:
        """Acquire a rate-limited slot for *host* and yield it."""
        host_sem, key = self._host_state(host)
        async with host_sem:
            async with self._host_locks[key]:
                now = time.monotonic()
                last = self._host_last.get(key, now)
                elapsed = now - last
                tokens = min(
                    1.0,
                    self._host_tokens.get(key, 1.0) + elapsed * self.requests_per_second,
                )
                if tokens < 1.0:
                    wait = (1.0 - tokens) / max(self.requests_per_second, 0.001)
                    await asyncio.sleep(wait)
                    tokens = 0.0
                else:
                    tokens -= 1.0
                self._host_tokens[key] = tokens
                self._host_last[key] = time.monotonic()
            async with self._global_sem:
                yield
