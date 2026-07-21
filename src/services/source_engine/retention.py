"""Retention policy enforcement for source engine data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.source_hit import SourceHit as DBSourceHit
from services.source_engine.config import SourceConfig


class RetentionPolicy:
    """Enforce raw and normalized retention windows per source config."""

    def __init__(self, source_config: SourceConfig) -> None:
        self.config = source_config

    def stale_raw(self, observed_at: datetime) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.raw_retention_days)
        return observed_at < cutoff

    def stale_normalized(self, observed_at: datetime) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.normalized_retention_days)
        return observed_at < cutoff

    async def apply_to_workspace(self, session: AsyncSession, workspace_id: UUID) -> dict[str, int]:
        """Delete stale source hits for a workspace and source.

        source_hit stores normalized records, so we retain them for the longer of the
        raw and normalized retention windows. Deleting at the shorter window would
        remove normalized data prematurely.
        """
        raw_cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.raw_retention_days)
        normalized_cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.config.normalized_retention_days
        )
        # Keep normalized records for the longest configured retention.
        cutoff = max(raw_cutoff, normalized_cutoff)

        result = await session.execute(
            delete(DBSourceHit)
            .where(
                DBSourceHit.workspace_id == workspace_id,
                DBSourceHit.source_key == self.config.source_key,
                DBSourceHit.observed_at < cutoff,
            )
            .execution_options(synchronize_session=False)
        )

        return {
            "raw_deleted": 0,
            "normalized_deleted": result.rowcount or 0,  # type: ignore[attr-defined]
        }
