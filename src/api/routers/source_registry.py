from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import SourceRegistry as DBSourceRegistry
from db.session import get_session
from domain.models import SourceRegistry, SourceRegistryCreate, SourceRegistryUpdate

router = APIRouter(prefix="/source-registry", tags=["source_registry"])


@router.get("/", response_model=list[SourceRegistry])
async def list_source_registry(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[SourceRegistry]:
    result = await session.scalars(
        select(DBSourceRegistry)
        .where(DBSourceRegistry.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [SourceRegistry.model_validate(r) for r in result.all()]


@router.post("/", response_model=SourceRegistry, status_code=201)
async def create_source_registry(
    data: SourceRegistryCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRegistry:
    values = data.model_dump(exclude={"workspace_id"})
    record = DBSourceRegistry(**values, workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SourceRegistry.model_validate(record)


@router.get("/{source_registry_id}", response_model=SourceRegistry)
async def get_source_registry(
    source_registry_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRegistry:
    record = await session.scalar(
        select(DBSourceRegistry).where(
            DBSourceRegistry.id == source_registry_id,
            DBSourceRegistry.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return SourceRegistry.model_validate(record)


@router.patch("/{source_registry_id}", response_model=SourceRegistry)
async def update_source_registry(
    source_registry_id: UUID,
    data: SourceRegistryUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceRegistry:
    record = await session.scalar(
        select(DBSourceRegistry).where(
            DBSourceRegistry.id == source_registry_id,
            DBSourceRegistry.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    values = data.model_dump(exclude_unset=True, exclude={"workspace_id"})
    for key, value in values.items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return SourceRegistry.model_validate(record)


@router.delete("/{source_registry_id}", status_code=204)
async def delete_source_registry(
    source_registry_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBSourceRegistry).where(
            DBSourceRegistry.id == source_registry_id,
            DBSourceRegistry.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
