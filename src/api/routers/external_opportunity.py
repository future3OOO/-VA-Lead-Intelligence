from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import ExternalOpportunity as DBExternalOpportunity
from db.session import get_session
from domain.models import ExternalOpportunity, ExternalOpportunityCreate, ExternalOpportunityUpdate

router = APIRouter(prefix="/external-opportunities", tags=["external_opportunity"])


@router.get("/", response_model=list[ExternalOpportunity])
async def list_external_opportunity(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[ExternalOpportunity]:
    result = await session.scalars(
        select(DBExternalOpportunity)
        .where(DBExternalOpportunity.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [ExternalOpportunity.model_validate(r) for r in result.all()]


@router.post("/", response_model=ExternalOpportunity, status_code=201)
async def create_external_opportunity(
    data: ExternalOpportunityCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExternalOpportunity:
    record = DBExternalOpportunity(
        **data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return ExternalOpportunity.model_validate(record)


@router.get("/{external_opportunity_id}", response_model=ExternalOpportunity)
async def get_external_opportunity(
    external_opportunity_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExternalOpportunity:
    record = await session.scalar(
        select(DBExternalOpportunity).where(
            DBExternalOpportunity.id == external_opportunity_id,
            DBExternalOpportunity.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return ExternalOpportunity.model_validate(record)


@router.patch("/{external_opportunity_id}", response_model=ExternalOpportunity)
async def update_external_opportunity(
    external_opportunity_id: UUID,
    data: ExternalOpportunityUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExternalOpportunity:
    record = await session.scalar(
        select(DBExternalOpportunity).where(
            DBExternalOpportunity.id == external_opportunity_id,
            DBExternalOpportunity.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return ExternalOpportunity.model_validate(record)


@router.delete("/{external_opportunity_id}", status_code=204)
async def delete_external_opportunity(
    external_opportunity_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBExternalOpportunity).where(
            DBExternalOpportunity.id == external_opportunity_id,
            DBExternalOpportunity.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
