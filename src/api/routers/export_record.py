from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import ExportRecord as DBExportRecord
from db.session import get_session
from domain.models import ExportRecord, ExportRecordCreate, ExportRecordUpdate

router = APIRouter(prefix="/exports", tags=["export_record"])


@router.get("/", response_model=list[ExportRecord])
async def list_export_record(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[ExportRecord]:
    result = await session.scalars(
        select(DBExportRecord)
        .where(DBExportRecord.workspace_id == auth_workspace_id)
        .offset(skip)
        .limit(limit)
    )
    return [ExportRecord.model_validate(r) for r in result.all()]


@router.post("/", response_model=ExportRecord, status_code=201)
async def create_export_record(
    data: ExportRecordCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportRecord:
    values = data.model_dump(exclude={"workspace_id"})
    record = DBExportRecord(**values, workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return ExportRecord.model_validate(record)


@router.get("/{export_record_id}", response_model=ExportRecord)
async def get_export_record(
    export_record_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportRecord:
    record = await session.scalar(
        select(DBExportRecord).where(
            DBExportRecord.id == export_record_id, DBExportRecord.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return ExportRecord.model_validate(record)


@router.patch("/{export_record_id}", response_model=ExportRecord)
async def update_export_record(
    export_record_id: UUID,
    data: ExportRecordUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportRecord:
    record = await session.scalar(
        select(DBExportRecord).where(
            DBExportRecord.id == export_record_id, DBExportRecord.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    values = data.model_dump(exclude_unset=True, exclude={"workspace_id"})
    for key, value in values.items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return ExportRecord.model_validate(record)


@router.delete("/{export_record_id}", status_code=204)
async def delete_export_record(
    export_record_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(
        select(DBExportRecord).where(
            DBExportRecord.id == export_record_id, DBExportRecord.workspace_id == auth_workspace_id
        )
    )
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
