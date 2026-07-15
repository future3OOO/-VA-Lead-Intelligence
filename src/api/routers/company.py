from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import Company as DBCompany
from db.session import get_session
from domain.models import Company, CompanyCreate, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["company"])


@router.get("/", response_model=list[Company])
async def list_company(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[Company]:
    result = await session.scalars(select(DBCompany).where(DBCompany.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [Company.model_validate(r) for r in result.all()]


@router.post("/", response_model=Company, status_code=201)
async def create_company(
    data: CompanyCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Company:
    record = DBCompany(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return Company.model_validate(record)


@router.get("/{company_id}", response_model=Company)
async def get_company(
    company_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Company:
    record = await session.scalar(select(DBCompany).where(DBCompany.id == company_id, DBCompany.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return Company.model_validate(record)


@router.patch("/{company_id}", response_model=Company)
async def update_company(
    company_id: UUID,
    data: CompanyUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Company:
    record = await session.scalar(select(DBCompany).where(DBCompany.id == company_id, DBCompany.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return Company.model_validate(record)


@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBCompany).where(DBCompany.id == company_id, DBCompany.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
