#!/usr/bin/env python3
"""Standalone script to execute a source engine run."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, "src")

from db.session import AsyncSessionLocal  # noqa: E402
from services.source_engine.runner import SourceRunner  # noqa: E402


async def run(
    workspace_id: UUID,
    campaign_id: UUID,
    source_keys: list[str] | None,
    query_overrides: dict[str, dict[str, str]],
) -> None:
    """Run the source engine portfolio."""
    session: AsyncSession
    async with AsyncSessionLocal() as session:
        runner = SourceRunner()
        record = await runner.run(
            session,
            workspace_id,
            campaign_id,
            source_keys=source_keys,
            query_overrides=query_overrides,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a source engine portfolio")
    parser.add_argument("--workspace-id", required=True, type=UUID)
    parser.add_argument("--campaign-id", required=True, type=UUID)
    parser.add_argument("--source-keys", nargs="+", default=None)
    parser.add_argument("--query-overrides", type=json.loads, default="{}")
    args = parser.parse_args()
    asyncio.run(run(args.workspace_id, args.campaign_id, args.source_keys, args.query_overrides))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
