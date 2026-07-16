from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import QueryFamily as DBQueryFamily
from db.session import get_session
from domain.models import QueryFamily, QueryFamilyCreate, QueryFamilyUpdate

router = APIRouter(prefix="/query-families", tags=["query_family"])


@router.get("/", response_model=list[QueryFamily])
async def list_query_family(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[QueryFamily]:
    result = await session.scalars(
        select(DBQueryFamily)
        .where(DBQueryFamily.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [QueryFamily.model_validate(r) for r in result.all()]


@router.post("/", response_model=QueryFamily, status_code=201)
async def create_query_family(
    data: QueryFamilyCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QueryFamily:
    record = DBQueryFamily(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return QueryFamily.model_validate(record)


@router.get("/{query_family_id}", response_model=QueryFamily)
async def get_query_family(
    query_family_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QueryFamily:
    record = await session.scalar(
        select(DBQueryFamily).where(
            DBQueryFamily.id == query_family_id, DBQueryFamily.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return QueryFamily.model_validate(record)


@router.patch("/{query_family_id}", response_model=QueryFamily)
async def update_query_family(
    query_family_id: UUID,
    data: QueryFamilyUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QueryFamily:
    record = await session.scalar(
        select(DBQueryFamily).where(
            DBQueryFamily.id == query_family_id, DBQueryFamily.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return QueryFamily.model_validate(record)


@router.delete("/{query_family_id}", status_code=204)
async def delete_query_family(
    query_family_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBQueryFamily).where(
            DBQueryFamily.id == query_family_id, DBQueryFamily.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
