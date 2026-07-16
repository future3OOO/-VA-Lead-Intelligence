"""Contact route enricher for resolved companies."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import ContactRouteType
from db.models.contact_route import ContactRoute as DBContactRoute


def _resolve_route_type(raw_type: str) -> ContactRouteType:
    try:
        return ContactRouteType(raw_type.lower())
    except ValueError:
        return ContactRouteType.GENERIC_EMAIL


async def enrich_contact_routes(
    session: AsyncSession,
    workspace_id: UUID,
    company_id: UUID,
    routes_raw: list[dict[str, Any]],
) -> list[DBContactRoute]:
    """Persist verified contact routes for a resolved company."""
    created: list[DBContactRoute] = []
    for route in routes_raw:
        if not isinstance(route, dict):
            continue
        value = str(route.get("value", "")).strip()
        if not value:
            continue
        record = DBContactRoute(
            id=uuid4(),
            workspace_id=workspace_id,
            company_id=company_id,
            route_type=_resolve_route_type(route.get("type", "generic_email")).value,
            value=value,
            is_verified=bool(route.get("is_verified", False)),
        )
        session.add(record)
        created.append(record)
    await session.flush()
    return created
