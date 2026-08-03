from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Company as DBCompany
from db.models import SourceHit as DBSourceHit
from db.session import get_session
from domain.models import SourceHit, SourceHitCreate, SourceHitUpdate

router = APIRouter(prefix="/source-hits", tags=["source_hit"])


async def _validate_workspace_references(
    values: dict[str, object],
    auth_workspace_id: UUID,
    session: AsyncSession,
) -> None:
    value = values.get("company_id")
    if value is not None:
        exists = await session.scalar(
            select(DBCompany.id).where(
                DBCompany.id == value,
                DBCompany.workspace_id == auth_workspace_id,
            )
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Company not found")


@router.get("/", response_model=list[SourceHit])
async def list_source_hit(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[SourceHit]:
    result = await session.scalars(
        select(DBSourceHit)
        .where(DBSourceHit.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [SourceHit.model_validate(r) for r in result.all()]


@router.post("/", response_model=SourceHit, status_code=201)
async def create_source_hit(
    data: SourceHitCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceHit:
    values = data.model_dump(exclude={"workspace_id"})
    await _validate_workspace_references(values, auth_workspace_id, session)
    record = DBSourceHit(**values, workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SourceHit.model_validate(record)


@router.get("/{source_hit_id}", response_model=SourceHit)
async def get_source_hit(
    source_hit_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceHit:
    record = await session.scalar(
        select(DBSourceHit).where(
            DBSourceHit.id == source_hit_id, DBSourceHit.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return SourceHit.model_validate(record)


@router.patch("/{source_hit_id}", response_model=SourceHit)
async def update_source_hit(
    source_hit_id: UUID,
    data: SourceHitUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SourceHit:
    record = await session.scalar(
        select(DBSourceHit).where(
            DBSourceHit.id == source_hit_id, DBSourceHit.workspace_id == auth_workspace_id
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
    return SourceHit.model_validate(record)


@router.delete("/{source_hit_id}", status_code=204)
async def delete_source_hit(
    source_hit_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBSourceHit).where(
            DBSourceHit.id == source_hit_id, DBSourceHit.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
