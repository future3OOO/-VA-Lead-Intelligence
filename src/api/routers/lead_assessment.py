from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import LeadAssessment as DBLeadAssessment
from db.session import get_session
from domain.models import LeadAssessment, LeadAssessmentCreate, LeadAssessmentUpdate

router = APIRouter(prefix="/leads", tags=["lead_assessment"])


@router.get("/", response_model=list[LeadAssessment])
async def list_lead_assessment(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[LeadAssessment]:
    result = await session.scalars(select(DBLeadAssessment).where(DBLeadAssessment.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [LeadAssessment.model_validate(r) for r in result.all()]


@router.post("/", response_model=LeadAssessment, status_code=201)
async def create_lead_assessment(
    data: LeadAssessmentCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadAssessment:
    record = DBLeadAssessment(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return LeadAssessment.model_validate(record)


@router.get("/{lead_assessment_id}", response_model=LeadAssessment)
async def get_lead_assessment(
    lead_assessment_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadAssessment:
    record = await session.scalar(select(DBLeadAssessment).where(DBLeadAssessment.id == lead_assessment_id, DBLeadAssessment.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return LeadAssessment.model_validate(record)


@router.patch("/{lead_assessment_id}", response_model=LeadAssessment)
async def update_lead_assessment(
    lead_assessment_id: UUID,
    data: LeadAssessmentUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LeadAssessment:
    record = await session.scalar(select(DBLeadAssessment).where(DBLeadAssessment.id == lead_assessment_id, DBLeadAssessment.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return LeadAssessment.model_validate(record)


@router.delete("/{lead_assessment_id}", status_code=204)
async def delete_lead_assessment(
    lead_assessment_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBLeadAssessment).where(DBLeadAssessment.id == lead_assessment_id, DBLeadAssessment.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
