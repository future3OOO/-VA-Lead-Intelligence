"""Company resolver for source hits."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import IntentLabel
from db.models.company import Company as DBCompany

EXCLUDED_INTENTS = {
    IntentLabel.SELLER_PROMOTION.value,
    IntentLabel.JOB_SEEKER.value,
    IntentLabel.GENERAL_DISCUSSION.value,
}

# Job-board sources are signal collections about real employers; even an UNRESOLVED
# intent hit should resolve to a company record so that we can enrich/domain it.
ALWAYS_RESOLVE_SOURCES = {
    "workable_jobs",
    "workable_search",
    "workable_company",
    "workable_html_search",
    "greenhouse_jobs",
    "lever_jobs",
    "ashby_jobs",
    "smartrecruiters_postings",
    "breezy_jobs",
    "jobicy",
    "team_pages",
    "openstreetmap",
}


async def resolve_company(
    session: AsyncSession,
    workspace_id: UUID,
    source_hit: dict[str, Any],
) -> DBCompany | None:
    """Resolve a source hit to an existing or new company record."""
    intent = source_hit.get("intent_label")
    source_key = source_hit.get("source_key", "")
    can_resolve_unresolved = source_key in ALWAYS_RESOLVE_SOURCES or source_key == "company_web"
    if intent in EXCLUDED_INTENTS and not can_resolve_unresolved:
        return None

    domain = source_hit.get("company_domain_raw", "").lower().strip()
    name = source_hit.get("company_name_raw", "").strip()

    if domain:
        result: DBCompany | None = await session.scalar(
            select(DBCompany).where(
                DBCompany.workspace_id == workspace_id,
                DBCompany.primary_domain == domain,
            )
        )
        if result:
            return result

    if name:
        result = await session.scalar(
            select(DBCompany).where(
                DBCompany.workspace_id == workspace_id,
                DBCompany.canonical_name.ilike(name),
            )
        )
        if result:
            if domain and not result.primary_domain:
                result.primary_domain = domain
            return cast(DBCompany | None, result)

    if not domain and not name:
        return None

    company = DBCompany(
        id=uuid4(),
        workspace_id=workspace_id,
        canonical_name=name or domain,
        primary_domain=domain or "",
        country_code="",
        industry="",
        employee_count=0,
        status="active",
    )
    session.add(company)
    await session.flush()
    return company
