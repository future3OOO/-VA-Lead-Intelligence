#!/usr/bin/env python3
"""Backfill targeted contacts from official company websites in parallel shards."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any
from uuid import UUID

from sqlalchemy import text

from db.session import AsyncSessionLocal
from services.source_engine.runner import SourceRunner


def partition_domains(domains: list[str], shard_count: int) -> list[list[str]]:
    """Return deterministic, disjoint shards over one unique domain snapshot."""
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    snapshot = sorted(set(domains))
    return [snapshot[index::shard_count] for index in range(shard_count)]


async def get_missing_contact_domains(
    workspace_id: UUID, max_domains: int | None = None
) -> list[str]:
    """Return one stable domain snapshot missing any person-specific contact lane."""
    if max_domains is not None and max_domains < 0:
        raise ValueError("max_domains must be zero or greater")
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT DISTINCT c.primary_domain
                    FROM company c
                    WHERE c.workspace_id = :workspace_id
                      AND c.primary_domain != ''
                      AND (
                        NOT EXISTS (
                          SELECT 1 FROM contact_route named
                          WHERE named.company_id = c.id
                            AND named.route_type = 'named_contact'
                        )
                        OR NOT EXISTS (
                          SELECT 1 FROM contact_route email
                          WHERE email.company_id = c.id
                            AND email.route_type = 'named_work_email_approved'
                            AND email.value LIKE '%<%'
                        )
                        OR NOT EXISTS (
                          SELECT 1 FROM contact_route phone
                          WHERE phone.company_id = c.id
                            AND phone.route_type = 'business_phone'
                            AND phone.value LIKE '%<%'
                        )
                        OR NOT EXISTS (
                          SELECT 1 FROM contact_route social
                          WHERE social.company_id = c.id
                            AND social.route_type = 'social_profile_review_only'
                            AND social.value LIKE '%linkedin.com/%'
                        )
                      )
                      AND c.primary_domain NOT LIKE '%example%'
                      AND c.primary_domain NOT LIKE '%facebook.com%'
                      AND c.primary_domain NOT LIKE '%linkedin.com%'
                      AND c.primary_domain NOT LIKE '%twitter.com%'
                      AND c.primary_domain NOT LIKE '%instagram.com%'
                    ORDER BY c.primary_domain
                    """
                ),
                {"workspace_id": workspace_id},
            )
        ).all()
    domains = [str(row[0]) for row in rows]
    return domains if max_domains is None else domains[:max_domains]


async def _run_source_shards(
    workspace_id: UUID,
    campaign_id: UUID,
    source_key: str,
    domains: list[str],
    shard_count: int,
) -> list[dict[str, Any]]:
    async def run_shard(shard_index: int, shard_domains: list[str]) -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            record = await SourceRunner().run(
                session,
                workspace_id,
                campaign_id,
                source_keys=[source_key],
                query_overrides={source_key: {"domains": shard_domains}},
            )
        if record.status != "succeeded":
            raise RuntimeError(
                f"{source_key} shard {shard_index} failed with {record.errors_total} errors"
            )
        return {
            "shard_index": shard_index,
            "source_run_id": str(record.id),
            "domains": len(shard_domains),
            "hits_total": record.hits_total,
            "hits_qualified_total": record.hits_qualified_total,
            "hits_duplicate_total": record.hits_duplicate_total,
            "errors_total": record.errors_total,
        }

    tasks = [
        run_shard(index, shard)
        for index, shard in enumerate(partition_domains(domains, shard_count))
        if shard
    ]
    return list(await asyncio.gather(*tasks))


async def run_targeted_contact_backfill(
    workspace_id: UUID,
    campaign_id: UUID,
    *,
    shard_count: int = 3,
    max_domains: int | None = None,
) -> dict[str, Any]:
    """Run team-page then deeper company-web backfills across concurrent shards."""
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    team_domains = await get_missing_contact_domains(workspace_id, max_domains)
    team_results = await _run_source_shards(
        workspace_id,
        campaign_id,
        "team_pages",
        team_domains,
        shard_count,
    )
    company_domains = await get_missing_contact_domains(workspace_id, max_domains)
    company_results = await _run_source_shards(
        workspace_id,
        campaign_id,
        "company_web",
        company_domains,
        shard_count,
    )
    return {
        "shard_count": shard_count,
        "team_pages": {"domains": len(team_domains), "runs": team_results},
        "company_web": {"domains": len(company_domains), "runs": company_results},
    }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill named contacts from official websites across parallel shards"
    )
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--campaign-id", type=UUID, required=True)
    parser.add_argument("--shards", type=int, default=3)
    parser.add_argument("--max-domains", type=int, default=None)
    args = parser.parse_args()
    if args.shards < 1:
        parser.error("--shards must be at least 1")
    if args.max_domains is not None and args.max_domains < 0:
        parser.error("--max-domains must be zero or greater")
    result = await run_targeted_contact_backfill(
        args.workspace_id,
        args.campaign_id,
        shard_count=args.shards,
        max_domains=args.max_domains,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
