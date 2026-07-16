"""Source adapter implementations."""

from __future__ import annotations

from services.source_engine.adapters.ashby import AshbyJobsAdapter
from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.company_web import CompanyWebAdapter
from services.source_engine.adapters.greenhouse import GreenhouseJobsAdapter
from services.source_engine.adapters.hunter import HunterDomainAdapter
from services.source_engine.adapters.lever import LeverJobsAdapter
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.adapters.search_discovery import SearchDiscoveryAdapter
from services.source_engine.adapters.smartrecruiters import SmartRecruitersAdapter
from services.source_engine.adapters.workable_jobs import WorkableJobsAdapter

ADAPTER_MAP: dict[str, type[BaseSourceAdapter]] = {
    "job_posting": GreenhouseJobsAdapter,
    "greenhouse_jobs": GreenhouseJobsAdapter,
    "lever_jobs": LeverJobsAdapter,
    "ashby_jobs": AshbyJobsAdapter,
    "smartrecruiters_postings": SmartRecruitersAdapter,
    "company_web": CompanyWebAdapter,
    "search_discovery": SearchDiscoveryAdapter,
    "hunter_domain": HunterDomainAdapter,
    "manual_seed": ManualSeedAdapter,
    "workable_jobs": WorkableJobsAdapter,
}

__all__ = [
    "BaseSourceAdapter",
    "ADAPTER_MAP",
    "AshbyJobsAdapter",
    "CompanyWebAdapter",
    "GreenhouseJobsAdapter",
    "HunterDomainAdapter",
    "LeverJobsAdapter",
    "ManualSeedAdapter",
    "SearchDiscoveryAdapter",
    "SmartRecruitersAdapter",
    "WorkableJobsAdapter",
]
