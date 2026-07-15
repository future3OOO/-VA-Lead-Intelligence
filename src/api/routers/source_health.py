from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import SourceHealth as DBSourceHealth
from db.session import get_session
from domain.models import SourceHealth, SourceHealthCreate, SourceHealthUpdate

router = APIRouter(prefix="/sources/health", tags=["source_health"])


@router.get("/", response_model=list[SourceHealth])
async def list_source_health(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[SourceHealth]:
    result = await session.scalars(select(DBSourceHealth).where(DBSourceHealth.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [SourceHealth.model_validate(r) for r in result.all()]


@router.post("/", response_model=SourceHealth, status_code=201)
async def create_source_health(
    data: SourceHealthCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceHealth:
    record = DBSourceHealth(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SourceHealth.model_validate(record)


@router.get("/{source_health_id}", response_model=SourceHealth)
async def get_source_health(
    source_health_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceHealth:
    record = await session.scalar(select(DBSourceHealth).where(DBSourceHealth.id == source_health_id, DBSourceHealth.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return SourceHealth.model_validate(record)


@router.patch("/{source_health_id}", response_model=SourceHealth)
async def update_source_health(
    source_health_id: UUID,
    data: SourceHealthUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceHealth:
    record = await session.scalar(select(DBSourceHealth).where(DBSourceHealth.id == source_health_id, DBSourceHealth.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return SourceHealth.model_validate(record)


@router.delete("/{source_health_id}", status_code=204)
async def delete_source_health(
    source_health_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBSourceHealth).where(DBSourceHealth.id == source_health_id, DBSourceHealth.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
