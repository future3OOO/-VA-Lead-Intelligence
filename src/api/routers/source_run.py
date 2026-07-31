from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Campaign as DBCampaign
from db.models import SourceRun as DBSourceRun
from db.session import get_session
from domain.models import SourceRun, SourceRunCreate, SourceRunUpdate

router = APIRouter(prefix="/source-runs", tags=["source_run"])


async def _validate_workspace_references(
    values: dict[str, object],
    auth_workspace_id: UUID,
    session: AsyncSession,
) -> None:
    value = values.get("campaign_id")
    if value is not None:
        exists = await session.scalar(
            select(DBCampaign.id).where(
                DBCampaign.id == value,
                DBCampaign.workspace_id == auth_workspace_id,
            )
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Campaign not found")


@router.get("/", response_model=list[SourceRun])
async def list_source_run(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
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
    values = data.model_dump(exclude={"workspace_id"})
    await _validate_workspace_references(values, auth_workspace_id, session)
    record = DBSourceRun(**values, workspace_id=auth_workspace_id)
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
    values = data.model_dump(exclude_unset=True, exclude={"workspace_id"})
    await _validate_workspace_references(values, auth_workspace_id, session)
    for key, value in values.items():
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
