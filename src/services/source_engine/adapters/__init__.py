"""Source adapter implementations."""

from __future__ import annotations

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.company_web import CompanyWebAdapter
from services.source_engine.adapters.finance_directory import FinanceDirectoryAdapter
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.adapters.nz_finance_advisers import NzFinanceAdvisersAdapter
from services.source_engine.adapters.openstreetmap import OpenStreetMapAdapter
from services.source_engine.adapters.team_pages import TeamPagesAdapter

ADAPTER_MAP: dict[str, type[BaseSourceAdapter]] = {
    "manual_seed": ManualSeedAdapter,
    "openstreetmap": OpenStreetMapAdapter,
    "team_pages": TeamPagesAdapter,
    "company_web": CompanyWebAdapter,
    "finance_directory": FinanceDirectoryAdapter,
    "nz_finance_advisers": NzFinanceAdvisersAdapter,
}

__all__ = [
    "BaseSourceAdapter",
    "ADAPTER_MAP",
    "CompanyWebAdapter",
    "FinanceDirectoryAdapter",
    "ManualSeedAdapter",
    "NzFinanceAdvisersAdapter",
    "OpenStreetMapAdapter",
    "TeamPagesAdapter",
]
