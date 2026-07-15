from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import CampaignRun as DBCampaignRun
from db.session import get_session
from domain.models import CampaignRun, CampaignRunCreate, CampaignRunUpdate

router = APIRouter(prefix="/campaign-runs", tags=["campaign_run"])


@router.get("/", response_model=list[CampaignRun])
async def list_campaign_run(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[CampaignRun]:
    result = await session.scalars(select(DBCampaignRun).where(DBCampaignRun.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [CampaignRun.model_validate(r) for r in result.all()]


@router.post("/", response_model=CampaignRun, status_code=201)
async def create_campaign_run(
    data: CampaignRunCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignRun:
    record = DBCampaignRun(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return CampaignRun.model_validate(record)


@router.get("/{campaign_run_id}", response_model=CampaignRun)
async def get_campaign_run(
    campaign_run_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignRun:
    record = await session.scalar(select(DBCampaignRun).where(DBCampaignRun.id == campaign_run_id, DBCampaignRun.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return CampaignRun.model_validate(record)


@router.patch("/{campaign_run_id}", response_model=CampaignRun)
async def update_campaign_run(
    campaign_run_id: UUID,
    data: CampaignRunUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CampaignRun:
    record = await session.scalar(select(DBCampaignRun).where(DBCampaignRun.id == campaign_run_id, DBCampaignRun.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return CampaignRun.model_validate(record)


@router.delete("/{campaign_run_id}", status_code=204)
async def delete_campaign_run(
    campaign_run_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBCampaignRun).where(DBCampaignRun.id == campaign_run_id, DBCampaignRun.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
