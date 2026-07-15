from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Suppression as DBSuppression
from db.session import get_session
from domain.models import Suppression, SuppressionCreate, SuppressionUpdate

router = APIRouter(prefix="/suppressions", tags=["suppression"])


@router.get("/", response_model=list[Suppression])
async def list_suppression(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[Suppression]:
    result = await session.scalars(select(DBSuppression).where(DBSuppression.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [Suppression.model_validate(r) for r in result.all()]


@router.post("/", response_model=Suppression, status_code=201)
async def create_suppression(
    data: SuppressionCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Suppression:
    record = DBSuppression(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return Suppression.model_validate(record)


@router.get("/{suppression_id}", response_model=Suppression)
async def get_suppression(
    suppression_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Suppression:
    record = await session.scalar(select(DBSuppression).where(DBSuppression.id == suppression_id, DBSuppression.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return Suppression.model_validate(record)


@router.patch("/{suppression_id}", response_model=Suppression)
async def update_suppression(
    suppression_id: UUID,
    data: SuppressionUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Suppression:
    record = await session.scalar(select(DBSuppression).where(DBSuppression.id == suppression_id, DBSuppression.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return Suppression.model_validate(record)


@router.delete("/{suppression_id}", status_code=204)
async def delete_suppression(
    suppression_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBSuppression).where(DBSuppression.id == suppression_id, DBSuppression.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
