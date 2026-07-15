from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Outcome as DBOutcome
from db.session import get_session
from domain.models import Outcome, OutcomeCreate, OutcomeUpdate

router = APIRouter(prefix="/outcomes", tags=["outcome"])


@router.get("/", response_model=list[Outcome])
async def list_outcome(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[Outcome]:
    result = await session.scalars(
        select(DBOutcome)
        .where(DBOutcome.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [Outcome.model_validate(r) for r in result.all()]


@router.post("/", response_model=Outcome, status_code=201)
async def create_outcome(
    data: OutcomeCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Outcome:
    record = DBOutcome(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return Outcome.model_validate(record)


@router.get("/{outcome_id}", response_model=Outcome)
async def get_outcome(
    outcome_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Outcome:
    record = await session.scalar(
        select(DBOutcome).where(
            DBOutcome.id == outcome_id, DBOutcome.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return Outcome.model_validate(record)


@router.patch("/{outcome_id}", response_model=Outcome)
async def update_outcome(
    outcome_id: UUID,
    data: OutcomeUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Outcome:
    record = await session.scalar(
        select(DBOutcome).where(
            DBOutcome.id == outcome_id, DBOutcome.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return Outcome.model_validate(record)


@router.delete("/{outcome_id}", status_code=204)
async def delete_outcome(
    outcome_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBOutcome).where(
            DBOutcome.id == outcome_id, DBOutcome.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
