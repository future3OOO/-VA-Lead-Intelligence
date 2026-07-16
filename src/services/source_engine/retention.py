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
        """Delete stale source hits for a workspace and source."""
        raw_cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.raw_retention_days)
        normalized_cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.config.normalized_retention_days
        )

        raw_result = await session.execute(
            delete(DBSourceHit)
            .where(
                DBSourceHit.workspace_id == workspace_id,
                DBSourceHit.source_key == self.config.source_key,
                DBSourceHit.observed_at < raw_cutoff,
            )
            .execution_options(synchronize_session=False)
        )
        normalized_result = await session.execute(
            delete(DBSourceHit)
            .where(
                DBSourceHit.workspace_id == workspace_id,
                DBSourceHit.source_key == self.config.source_key,
                DBSourceHit.observed_at < normalized_cutoff,
            )
            .execution_options(synchronize_session=False)
        )

        return {
            "raw_deleted": raw_result.rowcount or 0,  # type: ignore[attr-defined]
            "normalized_deleted": normalized_result.rowcount or 0,  # type: ignore[attr-defined]
        }
