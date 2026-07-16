#!/usr/bin/env python3
"""Run bounded team-page extraction against target company domains."""

from __future__ import annotations

import asyncio
import json
import sys
from uuid import UUID

from sqlalchemy import text

sys.path.insert(0, "src")

from db.session import AsyncSessionLocal  # noqa: E402
from services.source_engine.runner import SourceRunner  # noqa: E402

WORKSPACE_ID = UUID("f72ae1f9-f45e-45dc-a0d9-1a9e5e0b2a24")
CAMPAIGN_ID = UUID("f2ec5156-d497-442c-a664-111ce7fabfa2")


async def get_target_domains() -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT DISTINCT primary_domain
                    FROM company
                    WHERE workspace_id = :ws
                      AND primary_domain != ''
                      AND primary_domain NOT LIKE '%example%'
                    ORDER BY primary_domain
                    """
                ),
                {"ws": WORKSPACE_ID},
            )
        ).all()
        return [r[0] for r in rows]


async def main() -> None:
    domains = await get_target_domains()
    print(f"Running team_pages against {len(domains)} target domains")
    async with AsyncSessionLocal() as session:
        runner = SourceRunner()
        record = await runner.run(
            session,
            WORKSPACE_ID,
            CAMPAIGN_ID,
            source_keys=["team_pages"],
            query_overrides={"team_pages": {"domains": domains}},
        )
        print(
            json.dumps(
                {
                    "source_run_id": str(record.id),
                    "status": record.status,
                    "hits_total": record.hits_total,
                    "hits_qualified_total": record.hits_qualified_total,
                    "hits_duplicate_total": record.hits_duplicate_total,
                    "errors_total": record.errors_total,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
