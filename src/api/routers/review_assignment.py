from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import ReviewAssignment as DBReviewAssignment
from db.session import get_session
from domain.models import ReviewAssignment, ReviewAssignmentCreate, ReviewAssignmentUpdate

router = APIRouter(prefix="/reviews", tags=["review_assignment"])


@router.get("/", response_model=list[ReviewAssignment])
async def list_review_assignment(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ReviewAssignment]:
    result = await session.scalars(
        select(DBReviewAssignment)
        .where(DBReviewAssignment.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [ReviewAssignment.model_validate(r) for r in result.all()]


@router.post("/", response_model=ReviewAssignment, status_code=201)
async def create_review_assignment(
    data: ReviewAssignmentCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReviewAssignment:
    values = data.model_dump(exclude={"workspace_id"})
    record = DBReviewAssignment(**values, workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return ReviewAssignment.model_validate(record)


@router.get("/{review_assignment_id}", response_model=ReviewAssignment)
async def get_review_assignment(
    review_assignment_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReviewAssignment:
    record = await session.scalar(
        select(DBReviewAssignment).where(
            DBReviewAssignment.id == review_assignment_id,
            DBReviewAssignment.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return ReviewAssignment.model_validate(record)


@router.patch("/{review_assignment_id}", response_model=ReviewAssignment)
async def update_review_assignment(
    review_assignment_id: UUID,
    data: ReviewAssignmentUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReviewAssignment:
    record = await session.scalar(
        select(DBReviewAssignment).where(
            DBReviewAssignment.id == review_assignment_id,
            DBReviewAssignment.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    values = data.model_dump(exclude_unset=True, exclude={"workspace_id"})
    for key, value in values.items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return ReviewAssignment.model_validate(record)


@router.delete("/{review_assignment_id}", status_code=204)
async def delete_review_assignment(
    review_assignment_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBReviewAssignment).where(
            DBReviewAssignment.id == review_assignment_id,
            DBReviewAssignment.workspace_id == auth_workspace_id,
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
