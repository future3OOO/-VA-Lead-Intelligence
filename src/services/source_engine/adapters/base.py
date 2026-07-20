"""Base source adapter with operational controls."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

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

    @property
    @abstractmethod
    def source_key(self) -> str:
        """Stable source identifier matching the registry."""
        ...

    @property
    def enabled(self) -> bool:
        return self.config.status == "enabled"

    def kill_switched(self) -> bool:
        """Check the runtime kill switch."""
        from config.settings import Settings

        kill = self.config.kill_switch
        if not kill:
            return False
        setting = Settings().model_extra or {}
        for part in kill.split("."):
            if not isinstance(setting, dict):
                return False
            setting = setting.get(part, "")
        return str(setting).lower() in ("true", "1", "yes")

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
