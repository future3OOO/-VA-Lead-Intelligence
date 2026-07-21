"""Token-bucket rate limiter for source adapters."""

from __future__ import annotations

import asyncio
import time
from typing import Any


class RateLimiter:
    """Async token bucket with per-host concurrency.

    Use as an async context manager to hold the concurrency semaphore and consume
    one token for the duration of a single outbound request:

        async with self.rate_limiter:
            response = await self.client.get(url)
    """

    def __init__(
        self,
        requests_per_second: float = 2.0,
        max_concurrency_per_host: int = 1,
    ) -> None:
        self.requests_per_second = float(requests_per_second)
        self.max_concurrency = max(1, max_concurrency_per_host)
        self._tokens = 1.0
        self._last = time.monotonic()
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> RateLimiter:
        cfg = config or {}
        return cls(
            requests_per_second=float(cfg.get("requests_per_second", 2.0)),
            max_concurrency_per_host=int(cfg.get("max_concurrency_per_host", 1)),
        )

    async def __aenter__(self) -> RateLimiter:
        await self._semaphore.acquire()
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(1.0, self._tokens + elapsed * self.requests_per_second)
        self._last = now
        if self._tokens < 1.0:
            wait = (1.0 - self._tokens) / max(self.requests_per_second, 0.001)
            await asyncio.sleep(wait)
            self._tokens = 0.0
        else:
            self._tokens -= 1.0
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._semaphore.release()
