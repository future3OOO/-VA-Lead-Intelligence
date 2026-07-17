"""Source adapter implementations."""

from __future__ import annotations

from services.source_engine.adapters.ashby import AshbyJobsAdapter
from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.adapters.breezy_jobs import BreezyJobsAdapter
from services.source_engine.adapters.company_web import CompanyWebAdapter
from services.source_engine.adapters.greenhouse import GreenhouseJobsAdapter
from services.source_engine.adapters.hunter import HunterDomainAdapter
from services.source_engine.adapters.jobicy import JobicyAdapter
from services.source_engine.adapters.lever import LeverJobsAdapter
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.adapters.search_discovery import SearchDiscoveryAdapter
from services.source_engine.adapters.smartrecruiters import SmartRecruitersAdapter
from services.source_engine.adapters.team_pages import TeamPagesAdapter
from services.source_engine.adapters.workable_company import WorkableCompanyAdapter
from services.source_engine.adapters.workable_html_search import WorkableHtmlSearchAdapter
from services.source_engine.adapters.workable_jobs import WorkableJobsAdapter
from services.source_engine.adapters.workable_search import WorkableSearchAdapter

ADAPTER_MAP: dict[str, type[BaseSourceAdapter]] = {
    "job_posting": GreenhouseJobsAdapter,
    "greenhouse_jobs": GreenhouseJobsAdapter,
    "lever_jobs": LeverJobsAdapter,
    "ashby_jobs": AshbyJobsAdapter,
    "breezy_jobs": BreezyJobsAdapter,
    "smartrecruiters_postings": SmartRecruitersAdapter,
    "company_web": CompanyWebAdapter,
    "search_discovery": SearchDiscoveryAdapter,
    "hunter_domain": HunterDomainAdapter,
    "jobicy": JobicyAdapter,
    "manual_seed": ManualSeedAdapter,
    "team_pages": TeamPagesAdapter,
    "workable_jobs": WorkableJobsAdapter,
    "workable_company": WorkableCompanyAdapter,
    "workable_html_search": WorkableHtmlSearchAdapter,
    "workable_search": WorkableSearchAdapter,
}

__all__ = [
    "BaseSourceAdapter",
    "ADAPTER_MAP",
    "AshbyJobsAdapter",
    "BreezyJobsAdapter",
    "CompanyWebAdapter",
    "GreenhouseJobsAdapter",
    "HunterDomainAdapter",
    "JobicyAdapter",
    "LeverJobsAdapter",
    "ManualSeedAdapter",
    "SearchDiscoveryAdapter",
    "SmartRecruitersAdapter",
    "TeamPagesAdapter",
    "WorkableCompanyAdapter",
    "WorkableHtmlSearchAdapter",
    "WorkableJobsAdapter",
    "WorkableSearchAdapter",
]
