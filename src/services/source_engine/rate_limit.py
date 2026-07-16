"""Token-bucket rate limiter for source adapters."""

from __future__ import annotations

import asyncio
import time
from typing import Any


class RateLimiter:
    """Async token bucket with per-host concurrency."""

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

    async def acquire(self) -> None:
        async with self._semaphore:
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
