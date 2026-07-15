"""Temporal workflow definitions for campaign execution."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities import crawl_sources, export_leads, score_candidates


@workflow.defn
class CampaignRunWorkflow:
    """Orchestrate a campaign run from crawl through export."""

    @workflow.run
    async def run(self, campaign_id: str, workspace_id: str) -> dict[str, Any]:
        run_id = str(workflow.info().run_id)
        await workflow.execute_activity(
            crawl_sources,
            args=(campaign_id, workspace_id, run_id),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        scored = await workflow.execute_activity(
            score_candidates,
            args=(campaign_id, workspace_id, run_id),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        if scored.get("qualified_count", 0) > 0:
            await workflow.execute_activity(
                export_leads,
                args=(campaign_id, workspace_id, run_id),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        return {"campaign_id": campaign_id, "run_id": run_id, **scored}


@workflow.defn
class CrawlWorkflow:
    """Crawl a single source and store source events."""

    @workflow.run
    async def run(self, source_id: str, workspace_id: str) -> dict[str, Any]:
        return await workflow.execute_activity(
            crawl_sources,
            args=(source_id, workspace_id, str(workflow.info().run_id)),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
