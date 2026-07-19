"""Source adapter implementations."""

from __future__ import annotations

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.adapters.openstreetmap import OpenStreetMapAdapter
from services.source_engine.adapters.team_pages import TeamPagesAdapter

ADAPTER_MAP: dict[str, type[BaseSourceAdapter]] = {
    "manual_seed": ManualSeedAdapter,
    "openstreetmap": OpenStreetMapAdapter,
    "team_pages": TeamPagesAdapter,
}

__all__ = [
    "BaseSourceAdapter",
    "ADAPTER_MAP",
    "ManualSeedAdapter",
    "OpenStreetMapAdapter",
    "TeamPagesAdapter",
]
