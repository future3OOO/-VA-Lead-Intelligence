"""Source engine runner: portfolio execution and pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import IntentLabel, RunStatus
from db.models.campaign import Campaign
from db.models.source_hit import SourceHit as DBSourceHit
from db.models.source_run import SourceRun as DBSourceRun
from services.source_engine.adapters import ADAPTER_MAP
from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.classifier import classify_intent
from services.source_engine.config import SourceConfig, SourcePolicy, SourceRegistryLoader
from services.source_engine.enricher import enrich_contact_routes
from services.source_engine.resolver import resolve_company
from services.source_engine.scorer import _to_intent_label, score_source_hit


class SourceRunner:
    """Run a configured source portfolio against a campaign."""

    def __init__(self, registry: dict[str, SourceConfig] | None = None) -> None:
        self.registry = registry or SourceRegistryLoader().load()
        self.policy = SourcePolicy.load()

    def get_adapter(self, source_key: str) -> BaseSourceAdapter | None:
        cfg = self.registry.get(source_key)
        if not cfg:
            return None
        ok, reason = self.policy.validate(cfg)
        if not ok:
            print(f"[SourceRunner] policy violation for {source_key}: {reason}", flush=True)
            return None
        adapter_cls = ADAPTER_MAP.get(cfg.source_class)
        if not adapter_cls:
            return None
        return adapter_cls(cfg)

    async def run(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        campaign_id: UUID,
        source_keys: list[str] | None = None,
        query_overrides: dict[str, Any] | None = None,
    ) -> DBSourceRun:
        """Execute the configured portfolio and persist results."""
        campaign = await session.get(Campaign, campaign_id)
        score_threshold = campaign.score_threshold if campaign else 0.5
        started_at = datetime.now(timezone.utc)
        source_run = DBSourceRun(
            id=uuid4(),
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            source_key=",".join(source_keys or []),
            status=RunStatus.RUNNING.value,
            started_at=started_at,
            completed_at=started_at,
            hits_total=0,
            hits_qualified_total=0,
            hits_duplicate_total=0,
            errors_total=0,
            checkpoint={},
        )
        session.add(source_run)

        seen_hashes: set[str] = set()
        hits_total = 0
        qualified = 0
        duplicates = 0
        errors = 0

        keys = source_keys or list(self.registry.keys())
        for key in keys:
            adapter = self.get_adapter(key)
            if not adapter:
                errors += 1
                continue
            try:
                query = (query_overrides or {}).get(key, adapter.config.adapter_config)
                hits = await adapter.run(workspace_id, query)
                hits_total += len(hits)
                for hit in hits:
                    scored = self._process_hit(hit)
                    content_hash = scored.get("content_hash", "")
                    if content_hash and content_hash in seen_hashes:
                        duplicates += 1
                        continue
                    seen_hashes.add(content_hash)
                    if self._is_qualified(scored, score_threshold):
                        qualified += 1
                    await self._persist_hit(session, scored)
            except Exception:
                errors += 1
            finally:
                await adapter.aclose()

        source_run.status = RunStatus.FAILED.value if errors else RunStatus.SUCCEEDED.value
        source_run.completed_at = datetime.now(timezone.utc)
        source_run.hits_total = hits_total
        source_run.hits_qualified_total = qualified
        source_run.hits_duplicate_total = duplicates
        source_run.errors_total = errors
        await session.commit()
        return source_run

    def _is_qualified(self, hit: dict[str, Any], threshold: float) -> bool:
        """A hit is qualified if it scores above threshold and has buyer-side intent."""
        if hit.get("source_hit_priority", 0) < threshold:
            return False
        label = _to_intent_label(hit.get("intent_label"))
        return label in {
            IntentLabel.BUYER_REQUEST,
            IntentLabel.COMPANY_HIRING,
            IntentLabel.OPERATIONAL_PAIN,
            IntentLabel.GROWTH_TRIGGER,
        }

    def _process_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        """Classify, score, and resolve a source hit."""
        label = classify_intent(hit.get("title", ""), hit.get("body_excerpt", ""))
        hit["intent_label"] = label.value
        published_at = hit.get("published_at")
        if isinstance(published_at, str):
            published_at = published_at.replace("Z", "+00:00")
            try:
                published_at = datetime.fromisoformat(published_at)
            except ValueError:
                published_at = datetime.now(timezone.utc)
        if isinstance(published_at, datetime):
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)
        hit["published_at"] = published_at
        hit["source_hit_priority"] = score_source_hit(hit)
        hash_input = json.dumps(
            {
                "title": str(hit.get("title", "")).strip().lower(),
                "body": str(hit.get("body_excerpt", "")).strip().lower(),
                "company": str(hit.get("company_name_raw", "")).strip().lower(),
                "domain": str(hit.get("company_domain_raw", "")).strip().lower(),
            },
            sort_keys=True,
        )
        hit["content_hash"] = hashlib.sha256(hash_input.encode()).hexdigest()
        return hit

    async def _persist_hit(self, session: AsyncSession, data: dict[str, Any]) -> DBSourceHit | None:
        """Persist the source hit and, if resolvable, the company and contact routes.

        Uses an atomic PostgreSQL upsert so concurrent runs do not race on
        content_hash idempotency.
        """
        data.pop("source_hit_priority", None)
        data.setdefault("content_hash", "")
        workspace_id: UUID = data["workspace_id"]
        content_hash: str = data["content_hash"]

        if not content_hash:
            company = await resolve_company(session, workspace_id, data)
            if company:
                data["company_id"] = company.id
                routes = data.get("contact_routes_raw", [])
                if routes:
                    await enrich_contact_routes(session, company.workspace_id, company.id, routes)
            record = DBSourceHit(**data)
            session.add(record)
            await session.flush()
            return record

        data.setdefault("id", uuid4())
        stmt = (
            pg_insert(DBSourceHit)
            .values(data)
            .on_conflict_do_nothing(index_elements=["workspace_id", "source_key", "content_hash"])
            .returning(DBSourceHit.id)
        )
        result = await session.execute(stmt)
        hit_id = result.scalar_one_or_none()
        if not hit_id:
            return None

        company = await resolve_company(session, workspace_id, data)
        if company:
            data["company_id"] = company.id
            await session.execute(
                update(DBSourceHit).where(DBSourceHit.id == hit_id).values(company_id=company.id)
            )
            routes = data.get("contact_routes_raw", [])
            if routes:
                await enrich_contact_routes(session, company.workspace_id, company.id, routes)
        return await session.get(DBSourceHit, hit_id)
