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

# OpenStreetMap business listings and manual seed imports are signal collections
# about real employers; even an UNRESOLVED intent hit should resolve to a
# company record so we can persist a best contact route.
ALWAYS_RESOLVE_SOURCES = {
    "manual_seed",
    "openstreetmap",
    "team_pages",
}


async def resolve_company(
    session: AsyncSession,
    workspace_id: UUID,
    source_hit: dict[str, Any],
) -> DBCompany | None:
    """Resolve a source hit to an existing or new company record.

    Franchise branches are kept distinct by domain. A hit with a domain is only
    ever merged into a company with the exact same domain; canonical-name
    matches are ignored when domains differ so that separate branches keep
    their own contacts and locations.
    """
    intent = source_hit.get("intent_label")
    source_key = source_hit.get("source_key", "")
    can_resolve_unresolved = source_key in ALWAYS_RESOLVE_SOURCES
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
        # A new domain always creates a new company record, even if the brand
        # name matches an existing branch with a different domain.
        company = DBCompany(
            id=uuid4(),
            workspace_id=workspace_id,
            canonical_name=name or domain,
            primary_domain=domain,
            country_code="",
            industry="",
            employee_count=0,
            status="active",
        )
        session.add(company)
        await session.flush()
        return company

    if name:
        # Name-only matches are only safe against other name-only records.
        result = await session.scalar(
            select(DBCompany).where(
                DBCompany.workspace_id == workspace_id,
                DBCompany.canonical_name.ilike(name),
                DBCompany.primary_domain == "",
            )
        )
        if result:
            return cast(DBCompany | None, result)

    if not name:
        return None

    company = DBCompany(
        id=uuid4(),
        workspace_id=workspace_id,
        canonical_name=name,
        primary_domain="",
        country_code="",
        industry="",
        employee_count=0,
        status="active",
    )
    session.add(company)
    await session.flush()
    return company
