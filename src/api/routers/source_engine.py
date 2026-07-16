"""Source engine execution endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, require_workspace
from db.models.campaign import Campaign as DBCampaign
from db.models.source_run import SourceRun as DBSourceRun
from domain.models import SourceRun
from services.source_engine.runner import SourceRunner

router = APIRouter(prefix="/campaigns", tags=["source_engine"])


@router.post("/{campaign_id}/source-runs", response_model=SourceRun, status_code=201)
async def execute_source_run(
    campaign_id: UUID,
    body: dict[str, Any],
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRun:
    """Run a configured source portfolio for a campaign."""
    campaign = await session.scalar(
        select(DBCampaign).where(
            DBCampaign.id == campaign_id,
            DBCampaign.workspace_id == auth_workspace_id,
        )
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    runner = SourceRunner()
    record = await runner.run(
        session,
        auth_workspace_id,
        campaign_id,
        source_keys=body.get("source_keys"),
        query_overrides=body.get("query_overrides"),
    )
    return SourceRun.model_validate(record)


@router.get("/{campaign_id}/source-runs", response_model=list[SourceRun])
async def list_source_runs_for_campaign(
    campaign_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[SourceRun]:
    """List source runs for a campaign."""
    result = await session.scalars(
        select(DBSourceRun)
        .where(
            DBSourceRun.campaign_id == campaign_id,
            DBSourceRun.workspace_id == auth_workspace_id,
        )
        .offset(skip)
        .limit(limit)
    )
    return [SourceRun.model_validate(r) for r in result.all()]
