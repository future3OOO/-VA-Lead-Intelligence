"""Manual seed import adapter (CSV/JSON)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from services.source_engine.adapters.base import BaseSourceAdapter


class ManualSeedAdapter(BaseSourceAdapter):
    """Import manually curated seed companies or opportunities."""

    @property
    def source_key(self) -> str:
        return "manual_seed"

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        path = Path(query.get("path", self.config.adapter_config.get("path", "/dev/null")))
        if not path.exists():
            return []
        if path.suffix.lower() == ".json":
            return cast(list[dict[str, Any]], json.loads(path.read_text()))
        if path.suffix.lower() == ".csv":
            with path.open() as fh:
                return cast(list[dict[str, Any]], list(csv.DictReader(fh)))
        return []

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": raw.get("id", ""),
            "source_url": raw.get("url") or "http://localhost",
            "observed_at": datetime.now(timezone.utc),
            "published_at": raw.get("published_at") or datetime.now(timezone.utc),
            "title": raw.get("title", ""),
            "body_excerpt": raw.get("body", ""),
            "company_name_raw": raw.get("company_name", ""),
            "company_domain_raw": raw.get("company_domain", ""),
            "location_raw": raw.get("location", ""),
            "workplace_type": raw.get("workplace_type", ""),
            "contact_routes_raw": raw.get("contact_routes", []),
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
