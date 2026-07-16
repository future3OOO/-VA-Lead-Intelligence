from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import SourceRun as DBSourceRun
from db.session import get_session
from domain.models import SourceRun, SourceRunCreate, SourceRunUpdate

router = APIRouter(prefix="/source-runs", tags=["source_run"])


@router.get("/", response_model=list[SourceRun])
async def list_source_run(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[SourceRun]:
    result = await session.scalars(
        select(DBSourceRun)
        .where(DBSourceRun.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [SourceRun.model_validate(r) for r in result.all()]


@router.post("/", response_model=SourceRun, status_code=201)
async def create_source_run(
    data: SourceRunCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRun:
    record = DBSourceRun(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SourceRun.model_validate(record)


@router.get("/{source_run_id}", response_model=SourceRun)
async def get_source_run(
    source_run_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRun:
    record = await session.scalar(
        select(DBSourceRun).where(
            DBSourceRun.id == source_run_id, DBSourceRun.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return SourceRun.model_validate(record)


@router.patch("/{source_run_id}", response_model=SourceRun)
async def update_source_run(
    source_run_id: UUID,
    data: SourceRunUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRun:
    record = await session.scalar(
        select(DBSourceRun).where(
            DBSourceRun.id == source_run_id, DBSourceRun.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return SourceRun.model_validate(record)


@router.delete("/{source_run_id}", status_code=204)
async def delete_source_run(
    source_run_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBSourceRun).where(
            DBSourceRun.id == source_run_id, DBSourceRun.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
