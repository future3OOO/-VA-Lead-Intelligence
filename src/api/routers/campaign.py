from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Campaign as DBCampaign
from db.session import get_session
from domain.models import Campaign, CampaignCreate, CampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["campaign"])


@router.get("/", response_model=list[Campaign])
async def list_campaign(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[Campaign]:
    result = await session.scalars(select(DBCampaign).where(DBCampaign.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [Campaign.model_validate(r) for r in result.all()]


@router.post("/", response_model=Campaign, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Campaign:
    record = DBCampaign(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return Campaign.model_validate(record)


@router.get("/{campaign_id}", response_model=Campaign)
async def get_campaign(
    campaign_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Campaign:
    record = await session.scalar(select(DBCampaign).where(DBCampaign.id == campaign_id, DBCampaign.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return Campaign.model_validate(record)


@router.patch("/{campaign_id}", response_model=Campaign)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Campaign:
    record = await session.scalar(select(DBCampaign).where(DBCampaign.id == campaign_id, DBCampaign.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return Campaign.model_validate(record)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBCampaign).where(DBCampaign.id == campaign_id, DBCampaign.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
