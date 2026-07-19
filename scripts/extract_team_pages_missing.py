#!/usr/bin/env python3
"""Run bounded team-page extraction only on companies missing a named contact."""

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


async def get_missing_domains(workspace_id: UUID, max_domains: int | None = None) -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT c.primary_domain
                    FROM company c
                    LEFT JOIN contact_route cr
                      ON cr.company_id = c.id
                      AND cr.route_type = 'named_contact'
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
    parser = argparse.ArgumentParser(description="Run team-page extraction on missing contacts")
    parser.add_argument(
        "--workspace-id", type=UUID, default=UUID("985cfd3b-a3af-4217-8b10-8c46b0915b92")
    )
    parser.add_argument(
        "--campaign-id", type=UUID, default=UUID("2ddbdd5f-3e7e-4667-a3ca-4ee2dfb3bdfc")
    )
    parser.add_argument("--max-domains", type=int, default=None)
    args = parser.parse_args()

    domains = await get_missing_domains(args.workspace_id, args.max_domains)
    print(f"Running team_pages against {len(domains)} domains missing named contact")
    async with AsyncSessionLocal() as session:
        runner = SourceRunner()
        record = await runner.run(
            session,
            args.workspace_id,
            args.campaign_id,
            source_keys=["team_pages"],
            query_overrides={
                "team_pages": {
                    "domains": domains,
                    "paths": [
                        "/team",
                        "/about/team",
                        "/about/people",
                        "/about-us",
                        "/about",
                        "/leadership",
                        "/leadership-team",
                        "/people",
                        "/our-team",
                        "/our-people",
                        "/meet-the-team",
                        "/team-members",
                        "/executive-team",
                        "/executives",
                        "/management",
                        "/directors",
                        "/board",
                        "/staff",
                        "/our-staff",
                        "/who-we-are",
                        "/company",
                        "/company/team",
                        "/company/people",
                        "/about-us/team",
                        "/about-us/our-team",
                        "/agents",
                        "/our-agents",
                        "/meet-our-team",
                        "/contact",
                        "/contact-us",
                    ],
                }
            },
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
