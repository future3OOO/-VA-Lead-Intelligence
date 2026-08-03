from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Workspace as DBWorkspace
from db.session import get_session
from domain.models import Workspace, WorkspaceCreate, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspace"])


@router.get("/", response_model=list[Workspace])
async def list_workspace(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[Workspace]:
    result = await session.scalars(select(DBWorkspace).offset(skip).limit(limit))
    return [Workspace.model_validate(r) for r in result.all()]


@router.post("/", response_model=Workspace, status_code=201)
async def create_workspace(
    data: WorkspaceCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Workspace:
    values = data.model_dump(exclude_unset=True)
    record = DBWorkspace(**values)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return Workspace.model_validate(record)


@router.get("/{workspace_id}", response_model=Workspace)
async def get_workspace(
    workspace_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Workspace:
    record = await session.scalar(
        select(DBWorkspace).where(
            DBWorkspace.id == workspace_id, DBWorkspace.id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return Workspace.model_validate(record)


@router.patch("/{workspace_id}", response_model=Workspace)
async def update_workspace(
    workspace_id: UUID,
    data: WorkspaceUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Workspace:
    record = await session.scalar(
        select(DBWorkspace).where(
            DBWorkspace.id == workspace_id, DBWorkspace.id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return Workspace.model_validate(record)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBWorkspace).where(
            DBWorkspace.id == workspace_id, DBWorkspace.id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
