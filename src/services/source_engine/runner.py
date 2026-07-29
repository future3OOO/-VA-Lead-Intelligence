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
from core.policy_engine import evaluate_jurisdiction
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

# Country-name/-code resolution for the jurisdiction policy. Only the codes
# used by core.policy_engine.evaluate_jurisdiction are needed; unknown codes
# fall through to the policy's default_status.
_COUNTRY_NAME_TO_CODE = {
    "australia": "AU",
    "new zealand": "NZ",
    "newzealand": "NZ",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "germany": "DE",
    "canada": "CA",
    "china": "CN",
    "russia": "RU",
    "north korea": "KP",
    "iran": "IR",
}

# Map registry allowed_fields tokens to SourceHit model field names.
_ALLOWED_FIELD_MAP: dict[str, str] = {
    "company_name": "company_name_raw",
    "company_domain": "company_domain_raw",
    "title": "title",
    "body": "body_excerpt",
    "description": "body_excerpt",
    "location": "location_raw",
    "workplace_type": "workplace_type",
    "contact_routes": "contact_routes_raw",
    "source_url": "source_url",
    "source_native_id": "source_native_id",
    "raw_snapshot_uri": "raw_snapshot_uri",
    "access_policy_version": "access_policy_version",
}

# DB columns that must never be stripped by allowed_fields filtering.
_REQUIRED_DB_FIELDS = {
    "id",
    "workspace_id",
    "company_id",
    "source_key",
    "source_native_id",
    "source_url",
    "observed_at",
    "published_at",
    "title",
    "body_excerpt",
    "company_name_raw",
    "company_domain_raw",
    "location_raw",
    "workplace_type",
    "intent_label",
    "contact_routes_raw",
    "raw_snapshot_uri",
    "content_hash",
    "access_policy_version",
}

# Sources whose primary purpose is contact extraction may persist contact routes
# even when the scraped page does not itself qualify as a buyer-intent lead.
_ENRICHMENT_SOURCES = {"team_pages", "company_web"}


def _country_code_from_location(location: str) -> str | None:
    """Infer an ISO-style country code from a free-text location string."""
    if not location:
        return None
    normalized = location.strip().lower()

    # Exact country-name match first.
    if normalized in _COUNTRY_NAME_TO_CODE:
        return _COUNTRY_NAME_TO_CODE[normalized]

    # Look for a 2-letter code at the end of the string (e.g. "Remote, US" or "EU-DE").
    for separator in (",", "-"):
        parts = normalized.rsplit(separator, 1)
        if len(parts) == 2:
            candidate = parts[-1].strip().upper()
            if len(candidate) == 2 and candidate.isalpha():
                return candidate

    # Fall back to any embedded country name.
    for name, code in _COUNTRY_NAME_TO_CODE.items():
        if name in normalized:
            return code

    # Bare 2-letter code (e.g. "CN").
    if len(normalized) == 2 and normalized.isalpha():
        return normalized.upper()
    return None


def _jurisdiction_allowed(location: str | None) -> bool:
    """Evaluate whether a source hit location is allowed by jurisdiction policy."""
    code = _country_code_from_location(location or "")
    if not code:
        # Unknown location: rely on the policy's default_status.
        return bool(evaluate_jurisdiction("").get("allowed", False))
    return bool(evaluate_jurisdiction(code).get("allowed", False))


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
        if not campaign or campaign.workspace_id != workspace_id:
            raise ValueError(f"Campaign {campaign_id} does not belong to workspace {workspace_id}")
        score_threshold = campaign.score_threshold
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
            cfg = self.registry.get(key)
            if not cfg:
                errors += 1
                continue
            ok, reason = self.policy.validate(cfg)
            if not ok:
                print(f"[SourceRunner] policy violation for {key}: {reason}", flush=True)
                errors += 1
                continue
            adapter_cls = ADAPTER_MAP.get(cfg.source_class)
            if not adapter_cls:
                errors += 1
                continue
            adapter = adapter_cls(cfg)
            try:
                query = (query_overrides or {}).get(key, cfg.adapter_config)
                hits = await adapter.run(workspace_id, query)
                hits_total += len(hits)
                for hit in hits:
                    scored = self._process_hit(hit)

                    # Jurisdiction gate: blocked locations are not persisted.
                    if not _jurisdiction_allowed(scored.get("location_raw")):
                        continue

                    content_hash = scored.get("content_hash", "")
                    if content_hash and content_hash in seen_hashes:
                        duplicates += 1
                        continue
                    seen_hashes.add(content_hash)

                    is_qualified = self._is_qualified(scored, score_threshold)
                    if is_qualified:
                        qualified += 1

                    await self._persist_hit(session, scored, cfg, is_qualified)
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

        if not hit.get("content_hash"):
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

    @staticmethod
    def _allowed_model_fields(allowed_fields: list[str]) -> set[str]:
        """Translate registry allowed_fields tokens to SourceHit column names."""
        fields: set[str] = set()
        for token in allowed_fields:
            if token in _ALLOWED_FIELD_MAP:
                fields.add(_ALLOWED_FIELD_MAP[token])
        return fields

    @staticmethod
    def _filter_hit_fields(data: dict[str, Any], cfg: SourceConfig) -> dict[str, Any]:
        """Drop source-hit fields that are not in the source's allowed_fields list."""
        if not cfg.allowed_fields:
            return data
        allowed = SourceRunner._allowed_model_fields(cfg.allowed_fields)
        allowed |= _REQUIRED_DB_FIELDS
        # contact_routes require both the output and the field to be allowed.
        if "contact_route" not in cfg.allowed_outputs or "contact_routes" not in allowed:
            allowed.discard("contact_routes_raw")
        return {k: v for k, v in data.items() if k in allowed}

    async def _persist_hit(
        self,
        session: AsyncSession,
        data: dict[str, Any],
        cfg: SourceConfig,
        is_qualified: bool,
    ) -> DBSourceHit | None:
        """Persist the source hit and, if allowed/qualified, the company and contact routes.

        Uses an atomic PostgreSQL upsert so concurrent runs do not race on
        content_hash idempotency. Contact routes are only enriched when the hit
        is qualified, contact_route is in the source's allowed_outputs, and the
        source policy requires qualification before contact extraction.
        """
        data.pop("source_hit_priority", None)
        data.setdefault("content_hash", "")
        data = self._filter_hit_fields(data, cfg)
        data.setdefault("contact_routes_raw", [])

        workspace_id: UUID = data["workspace_id"]
        content_hash: str = data["content_hash"]

        can_resolve_company = "company_lead" in cfg.allowed_outputs
        can_enrich_contacts = "contact_route" in cfg.allowed_outputs and (
            is_qualified
            or not self.policy.contact_route_after_qualification_only
            or cfg.source_class in _ENRICHMENT_SOURCES
        )

        async def _resolve_and_enrich(company_id: UUID) -> None:
            if can_enrich_contacts:
                routes = data.get("contact_routes_raw", [])
                if routes:
                    await enrich_contact_routes(session, workspace_id, company_id, routes)

        if not content_hash:
            if can_resolve_company:
                company = await resolve_company(session, workspace_id, data)
                if company:
                    data["company_id"] = company.id
                    await _resolve_and_enrich(company.id)
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

        if can_resolve_company:
            company = await resolve_company(session, workspace_id, data)
            if company:
                data["company_id"] = company.id
                await session.execute(
                    update(DBSourceHit)
                    .where(DBSourceHit.id == hit_id)
                    .values(company_id=company.id)
                )
                await _resolve_and_enrich(company.id)
        return await session.get(DBSourceHit, hit_id)
