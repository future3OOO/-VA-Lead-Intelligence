"""Company resolver for source hits."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import IntentLabel
from db.models.company import Company as DBCompany
from db.models.company_identifier import CompanyIdentifier

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

ENRICHMENT_SOURCES = {"company_web", "team_pages"}
BRANCH_LISTING_SOURCES = {"openstreetmap"}


async def _identified_company(
    session: AsyncSession,
    workspace_id: UUID,
    source: str,
    external_id: str,
) -> DBCompany | None:
    company: DBCompany | None = await session.scalar(
        select(DBCompany)
        .join(CompanyIdentifier, CompanyIdentifier.company_id == DBCompany.id)
        .where(
            CompanyIdentifier.workspace_id == workspace_id,
            CompanyIdentifier.source == source,
            CompanyIdentifier.external_id == external_id,
        )
    )
    return company


async def resolve_company(
    session: AsyncSession,
    workspace_id: UUID,
    source_hit: dict[str, Any],
) -> DBCompany | None:
    """Resolve a source hit without merging distinct source listings."""
    intent = source_hit.get("intent_label")
    source_key = source_hit.get("source_key", "")
    can_resolve_unresolved = source_key in ALWAYS_RESOLVE_SOURCES
    if intent in EXCLUDED_INTENTS and not can_resolve_unresolved:
        return None

    domain = source_hit.get("company_domain_raw", "").lower().strip()
    name = source_hit.get("company_name_raw", "").strip()
    source_native_id = str(source_hit.get("source_native_id", "")).strip()

    if source_key and source_native_id:
        result = await _identified_company(session, workspace_id, source_key, source_native_id)
        if result:
            return result

    if not name and not domain:
        return None

    company: DBCompany | None = None
    candidates = select(DBCompany).where(
        DBCompany.workspace_id == workspace_id,
        DBCompany.primary_domain == domain,
    )
    if source_key in ENRICHMENT_SOURCES and domain:
        matches = list((await session.scalars(candidates.limit(2))).all())
        if len(matches) > 1:
            return None
        if matches:
            company = matches[0]
    elif name and source_key and source_key not in BRANCH_LISTING_SOURCES:
        matches = list(
            (
                await session.scalars(
                    candidates.where(func.lower(DBCompany.canonical_name) == name.lower()).limit(2)
                )
            ).all()
        )
        if len(matches) == 1:
            company = matches[0]
    elif domain and name:
        # A new branch listing may only reuse a company not already claimed by
        # another listing from the same branch-aware source.
        statement = (
            candidates.outerjoin(
                CompanyIdentifier,
                and_(
                    CompanyIdentifier.company_id == DBCompany.id,
                    CompanyIdentifier.workspace_id == workspace_id,
                    CompanyIdentifier.source == source_key,
                ),
            )
            .where(
                DBCompany.workspace_id == workspace_id,
                DBCompany.primary_domain == domain,
                func.lower(DBCompany.canonical_name) == name.lower(),
                CompanyIdentifier.id.is_(None),
            )
            .limit(2)
        )
        matches = list((await session.scalars(statement)).all())
        if len(matches) == 1:
            company = matches[0]

    created = company is None
    if created:
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

    assert company is not None
    if not source_key or not source_native_id:
        return company

    identifier = CompanyIdentifier(
        workspace_id=workspace_id,
        company_id=company.id,
        source=source_key,
        external_id=source_native_id,
    )
    try:
        async with session.begin_nested():
            session.add(identifier)
            await session.flush()
    except IntegrityError:
        if created:
            await session.delete(company)
            await session.flush()
        winner = await _identified_company(session, workspace_id, source_key, source_native_id)
        if winner is None:
            raise
        return winner
    return company
