#!/usr/bin/env python3
"""Run company_web crawl only on companies that have no named contact route."""

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


async def get_missing_contact_domains(
    workspace_id: UUID, max_domains: int | None = None
) -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT c.primary_domain
                    FROM company c
                    LEFT JOIN contact_route cr
                      ON cr.company_id = c.id
                      AND (
                          cr.route_type = 'named_contact'
                          OR (cr.route_type = 'named_work_email_approved' AND cr.value LIKE '%<%')
                      )
                    WHERE c.workspace_id = :ws
                      AND c.primary_domain != ''
                      AND cr.id IS NULL
                      AND c.primary_domain NOT LIKE '%example%'
                      AND c.primary_domain NOT LIKE '%facebook.com%'
                      AND c.primary_domain NOT LIKE '%linkedin.com%'
                      AND c.primary_domain NOT LIKE '%twitter.com%'
                      AND c.primary_domain NOT LIKE '%instagram.com%'
                    ORDER BY c.primary_domain
                    LIMIT :limit
                    """
                ),
                {"ws": workspace_id, "limit": max_domains or 10000},
            )
        ).all()
        return [r[0] for r in rows]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace-id", type=UUID, default=UUID("985cfd3b-a3af-4217-8b10-8c46b0915b92")
    )
    parser.add_argument(
        "--campaign-id", type=UUID, default=UUID("2ddbdd5f-3e7e-4667-a3ca-4ee2dfb3bdfc")
    )
    parser.add_argument("--max-domains", type=int, default=None)
    args = parser.parse_args()

    domains = await get_missing_contact_domains(args.workspace_id, args.max_domains)
    print(f"Running company_web against {len(domains)} domains with no named contact")
    async with AsyncSessionLocal() as session:
        runner = SourceRunner()
        record = await runner.run(
            session,
            args.workspace_id,
            args.campaign_id,
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
