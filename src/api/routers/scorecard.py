from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Scorecard as DBScorecard
from db.session import get_session
from domain.models import Scorecard, ScorecardCreate, ScorecardUpdate

router = APIRouter(prefix="/scorecards", tags=["scorecard"])


@router.get("/", response_model=list[Scorecard])
async def list_scorecard(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[Scorecard]:
    result = await session.scalars(
        select(DBScorecard)
        .where(DBScorecard.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [Scorecard.model_validate(r) for r in result.all()]


@router.post("/", response_model=Scorecard, status_code=201)
async def create_scorecard(
    data: ScorecardCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Scorecard:
    values = data.model_dump(exclude={"workspace_id"})
    record = DBScorecard(**values, workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return Scorecard.model_validate(record)


@router.get("/{scorecard_id}", response_model=Scorecard)
async def get_scorecard(
    scorecard_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Scorecard:
    record = await session.scalar(
        select(DBScorecard).where(
            DBScorecard.id == scorecard_id, DBScorecard.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return Scorecard.model_validate(record)


@router.patch("/{scorecard_id}", response_model=Scorecard)
async def update_scorecard(
    scorecard_id: UUID,
    data: ScorecardUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Scorecard:
    record = await session.scalar(
        select(DBScorecard).where(
            DBScorecard.id == scorecard_id, DBScorecard.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    values = data.model_dump(exclude_unset=True, exclude={"workspace_id"})
    for key, value in values.items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return Scorecard.model_validate(record)


@router.delete("/{scorecard_id}", status_code=204)
async def delete_scorecard(
    scorecard_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBScorecard).where(
            DBScorecard.id == scorecard_id, DBScorecard.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
