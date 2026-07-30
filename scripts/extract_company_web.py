#!/usr/bin/env python3
"""Run bounded company-website crawl against target company domains."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from uuid import UUID

from sqlalchemy import text

sys.path.insert(0, "src")

from db.session import AsyncSessionLocal  # noqa: E402
from services.source_engine.runner import SourceRunner  # noqa: E402


async def get_target_domains(
    workspace_id: UUID, max_domains: int | None = None, offset: int = 0
) -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT c.primary_domain, COUNT(sh.id) AS hit_count
                    FROM company c
                    LEFT JOIN source_hit sh ON sh.company_id = c.id
                    WHERE c.workspace_id = :ws
                      AND c.primary_domain != ''
                      AND c.primary_domain NOT LIKE '%example%'
                      AND c.primary_domain NOT LIKE '%facebook.com%'
                      AND c.primary_domain NOT LIKE '%linkedin.com%'
                      AND c.primary_domain NOT LIKE '%twitter.com%'
                      AND c.primary_domain NOT LIKE '%instagram.com%'
                    GROUP BY c.primary_domain
                    ORDER BY hit_count DESC, c.primary_domain
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {
                    "ws": workspace_id,
                    "limit": 10000 if max_domains is None else max_domains,
                    "offset": offset,
                },
            )
        ).all()
        return [r[0] for r in rows]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded company-website crawl")
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--campaign-id", type=UUID, required=True)
    parser.add_argument("--max-domains", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    if args.max_domains is not None and args.max_domains < 0:
        parser.error("--max-domains must be zero or greater")

    workspace_id = args.workspace_id
    campaign_id = args.campaign_id
    domains = await get_target_domains(workspace_id, args.max_domains, args.offset)
    print(f"Running company_web against {len(domains)} target domains")
    async with AsyncSessionLocal() as session:
        runner = SourceRunner()
        record = await runner.run(
            session,
            workspace_id,
            campaign_id,
            source_keys=["company_web"],
            query_overrides={"company_web": {"domains": domains}},
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
