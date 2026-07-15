from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_workspace
from db.models import DiscoveryEvent as DBDiscoveryEvent
from db.session import get_session
from domain.models import DiscoveryEvent, DiscoveryEventCreate, DiscoveryEventUpdate

router = APIRouter(prefix="/refresh-requests", tags=["discovery_event"])


@router.get("/", response_model=list[DiscoveryEvent])
async def list_discovery_event(
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> list[DiscoveryEvent]:
    result = await session.scalars(select(DBDiscoveryEvent).where(DBDiscoveryEvent.workspace_id == auth_workspace_id).offset(skip).limit(limit))
    return [DiscoveryEvent.model_validate(r) for r in result.all()]


@router.post("/", response_model=DiscoveryEvent, status_code=201)
async def create_discovery_event(
    data: DiscoveryEventCreate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DiscoveryEvent:
    record = DBDiscoveryEvent(**data.model_dump(exclude_unset=True), workspace_id=auth_workspace_id)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return DiscoveryEvent.model_validate(record)


@router.get("/{discovery_event_id}", response_model=DiscoveryEvent)
async def get_discovery_event(
    discovery_event_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DiscoveryEvent:
    record = await session.scalar(select(DBDiscoveryEvent).where(DBDiscoveryEvent.id == discovery_event_id, DBDiscoveryEvent.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return DiscoveryEvent.model_validate(record)


@router.patch("/{discovery_event_id}", response_model=DiscoveryEvent)
async def update_discovery_event(
    discovery_event_id: UUID,
    data: DiscoveryEventUpdate,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DiscoveryEvent:
    record = await session.scalar(select(DBDiscoveryEvent).where(DBDiscoveryEvent.id == discovery_event_id, DBDiscoveryEvent.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return DiscoveryEvent.model_validate(record)


@router.delete("/{discovery_event_id}", status_code=204)
async def delete_discovery_event(
    discovery_event_id: UUID,
    auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    record = await session.scalar(select(DBDiscoveryEvent).where(DBDiscoveryEvent.id == discovery_event_id, DBDiscoveryEvent.workspace_id == auth_workspace_id))
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(record)
    await session.commit()
