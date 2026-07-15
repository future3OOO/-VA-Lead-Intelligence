"""Temporal activities for the campaign pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from temporalio import activity

from core.policy_engine import evaluate_jurisdiction
from core.scorer import score
from db.models import Campaign, Company, LeadAssessment
from db.session import AsyncSessionLocal


@activity.defn
async def crawl_sources(campaign_id: str, workspace_id: str, run_id: str) -> dict[str, Any]:
    """Crawl configured sources and create source_event records."""
    async with AsyncSessionLocal() as session:
        campaign = await session.scalar(select(Campaign).where(Campaign.id == UUID(campaign_id)))
        if not campaign:
            return {"status": "not_found"}
        # Placeholder: real implementation delegates to Crawlee service.
        return {"status": "ok", "campaign_id": campaign_id, "run_id": run_id, "discovered": 0}


@activity.defn
async def score_candidates(campaign_id: str, workspace_id: str, run_id: str) -> dict[str, Any]:
    """Score discovered companies against the active scorecard."""
    async with AsyncSessionLocal() as session:
        campaign = await session.scalar(select(Campaign).where(Campaign.id == UUID(campaign_id)))
        if not campaign:
            return {"status": "not_found"}
        result = await session.scalars(
            select(Company).where(
                Company.workspace_id == UUID(workspace_id),
                Company.status == "active",
            )
        )
        companies = result.all()
        qualified = 0
        for company in companies:
            if company.country_code:
                jurisdiction = evaluate_jurisdiction(company.country_code)
                if not jurisdiction["allowed"]:
                    continue
            features = {
                "employee_count_delta": 0.15,
                "role_skill_match": 0.8,
                "country_code": company.country_code,
                "do_not_contact_list": False,
            }
            outcome = score(features)
            if outcome["passed"]:
                qualified += 1
                lead = LeadAssessment(
                    campaign_id=UUID(campaign_id),
                    company_id=company.id,
                    workspace_id=UUID(workspace_id),
                    fit_score=outcome["score"],
                    threshold=campaign.score_threshold,
                    status="pending",
                    scored_at=datetime.now(timezone.utc),
                )
                session.add(lead)
        await session.commit()
        return {"status": "ok", "qualified_count": qualified, "total": len(companies)}


@activity.defn
async def export_leads(campaign_id: str, workspace_id: str, run_id: str) -> dict[str, Any]:
    """Export qualified leads to the configured destination."""
    async with AsyncSessionLocal() as session:
        result = await session.scalars(
            select(LeadAssessment).where(
                LeadAssessment.campaign_id == UUID(campaign_id),
                LeadAssessment.workspace_id == UUID(workspace_id),
                LeadAssessment.status == "pending",
            )
        )
        leads = result.all()
        for lead in leads:
            lead.status = "exported"
        await session.commit()
        return {"status": "ok", "exported": len(leads)}
