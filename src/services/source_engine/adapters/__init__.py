"""Source adapter implementations."""

from __future__ import annotations

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.adapters.openstreetmap import OpenStreetMapAdapter

ADAPTER_MAP: dict[str, type[BaseSourceAdapter]] = {
    "manual_seed": ManualSeedAdapter,
    "openstreetmap": OpenStreetMapAdapter,
}

__all__ = [
    "BaseSourceAdapter",
    "ADAPTER_MAP",
    "ManualSeedAdapter",
    "OpenStreetMapAdapter",
]
