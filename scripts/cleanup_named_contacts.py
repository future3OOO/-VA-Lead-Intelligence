#!/usr/bin/env python3
"""Remove named_contact routes that do not look like real person names."""

from __future__ import annotations

import asyncio
import re
import sys
from uuid import UUID

sys.path.insert(0, "src")

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import ContactRouteType
from db.models.contact_route import ContactRoute as DBContactRoute
from db.models.source_hit import SourceHit as DBSourceHit
from db.session import AsyncSessionLocal
from services.source_engine.adapters.team_pages import _is_plausible_person_name

WORKSPACE_ID = UUID("985cfd3b-a3af-4217-8b10-8c46b0915b92")


def _name_part(value: str) -> str:
    """Extract the display name from a contact route value."""
    value = value.split("<")[0].split("(")[0].strip()
    return re.sub(r"\s+", " ", value)


async def main() -> int:
    session: AsyncSession
    async with AsyncSessionLocal() as session:
        result = await session.scalars(
            select(DBContactRoute).where(
                DBContactRoute.workspace_id == WORKSPACE_ID,
                DBContactRoute.route_type == ContactRouteType.NAMED_CONTACT.value,
            )
        )
        routes = result.all()
        bad_ids = [r.id for r in routes if not _is_plausible_person_name(_name_part(r.value))]
        print(f"Found {len(bad_ids)} implausible named_contact routes out of {len(routes)}")
        if bad_ids:
            await session.execute(delete(DBContactRoute).where(DBContactRoute.id.in_(bad_ids)))
            await session.commit()
            print(f"Deleted {len(bad_ids)} bad named_contact routes")

        # Also drop stale finance_directory source hits so they can be re-fetched.
        await session.scalar(
            select(DBSourceHit).where(
                DBSourceHit.workspace_id == WORKSPACE_ID,
                DBSourceHit.source_key == "finance_directory",
            )
        )
        await session.execute(
            delete(DBSourceHit).where(
                DBSourceHit.workspace_id == WORKSPACE_ID,
                DBSourceHit.source_key == "finance_directory",
            )
        )
        await session.commit()
        print("Deleted finance_directory source_hits")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
