from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import CostLedger as DBCostLedger
from db.session import get_session
from domain.models import CostLedger, CostLedgerCreate, CostLedgerUpdate

router = APIRouter(prefix="/costs", tags=["cost_ledger"])


@router.get("/", response_model=list[CostLedger])
async def list_cost_ledger(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[CostLedger]:
    result = await session.scalars(select(DBCostLedger).where(DBCostLedger.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [CostLedger.model_validate(r) for r in result.all()]


@router.post("/", response_model=CostLedger, status_code=201)
async def create_cost_ledger(
    data: CostLedgerCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CostLedger:
    record = DBCostLedger(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return CostLedger.model_validate(record)


@router.get("/{cost_ledger_id}", response_model=CostLedger)
async def get_cost_ledger(
    cost_ledger_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CostLedger:
    record = await session.scalar(select(DBCostLedger).where(DBCostLedger.id == cost_ledger_id, DBCostLedger.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return CostLedger.model_validate(record)


@router.patch("/{cost_ledger_id}", response_model=CostLedger)
async def update_cost_ledger(
    cost_ledger_id: UUID,
    data: CostLedgerUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CostLedger:
    record = await session.scalar(select(DBCostLedger).where(DBCostLedger.id == cost_ledger_id, DBCostLedger.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return CostLedger.model_validate(record)


@router.delete("/{cost_ledger_id}", status_code=204)
async def delete_cost_ledger(
    cost_ledger_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBCostLedger).where(DBCostLedger.id == cost_ledger_id, DBCostLedger.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
