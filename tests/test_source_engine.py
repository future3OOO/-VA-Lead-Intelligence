"""Source engine unit and integration tests."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from config.enums import IntentLabel
from db.models.campaign import Campaign
from db.models.company import Company as DBCompany
from db.models.workspace import Workspace
from db.session import AsyncSessionLocal
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.classifier import classify_intent, score_intent
from services.source_engine.config import SourceConfig, SourceRegistryLoader
from services.source_engine.resolver import resolve_company
from services.source_engine.runner import SourceRunner
from services.source_engine.scorer import score_source_hit


@pytest.fixture(autouse=True)
async def _dispose_engine() -> None:
    yield
    from db.session import engine

    await engine.dispose()


@pytest.fixture
def manual_seed_config() -> SourceConfig:
    return SourceConfig(
        source_key="manual_seed",
        source_class="manual_seed",
        access_mode="manual_import",
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
    )


def test_source_registry_loads() -> None:
    registry = SourceRegistryLoader().load()
    assert "manual_seed" in registry
    assert "openstreetmap" in registry


def test_intent_classifier_buyer_request() -> None:
    label = classify_intent(
        "Hiring a Virtual Assistant",
        "We need a remote assistant to manage inbox, schedule appointments and update CRM.",
    )
    assert label == IntentLabel.BUYER_REQUEST


def test_intent_classifier_job_seeker() -> None:
    label = classify_intent(
        "Become a Virtual Assistant",
        "Join our course and learn how to become a virtual assistant.",
    )
    assert label in (IntentLabel.JOB_SEEKER, IntentLabel.SELLER_PROMOTION)


def test_score_intent_values() -> None:
    assert score_intent(IntentLabel.BUYER_REQUEST) == 1.0
    assert score_intent(IntentLabel.UNRESOLVED) == 0.0


def test_score_source_hit_buyer_with_contact() -> None:
    hit = {
        "intent_label": IntentLabel.BUYER_REQUEST.value,
        "company_domain_raw": "acme.example.com",
        "published_at": datetime.now(timezone.utc),
        "body_excerpt": "Virtual assistant needed for inbox and scheduling.",
        "contact_routes_raw": [{"type": "generic_email", "value": "hire@example.com"}],
    }
    assert score_source_hit(hit) >= 0.3


@pytest.mark.asyncio
async def test_manual_seed_adapter(manual_seed_config: SourceConfig) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "seed.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "id": "1",
                        "title": "VA Role",
                        "body": "Need a virtual assistant.",
                        "company_name": "Acme",
                        "company_domain": "acme.example.com",
                        "contact_routes": [
                            {"type": "generic_email", "value": "hire@acme.example.com"}
                        ],
                    }
                ]
            )
        )
        adapter = ManualSeedAdapter(manual_seed_config)
        hits = await adapter.run(
            workspace_id=uuid4(),
            query={"path": str(path)},
        )
    assert len(hits) == 1
    assert hits[0]["source_key"] == "manual_seed"
    assert hits[0]["company_name_raw"] == "Acme"


@pytest.mark.asyncio
async def test_resolve_company_creates_for_buyer() -> None:
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()
        hit = {
            "intent_label": IntentLabel.BUYER_REQUEST.value,
            "company_domain_raw": "acme.example.com",
            "company_name_raw": "Acme",
        }
        company = await resolve_company(session, workspace.id, hit)
        assert company is not None
        assert company.canonical_name == "Acme"
        assert company.primary_domain == "acme.example.com"


@pytest.mark.asyncio
async def test_resolve_company_skips_seller() -> None:
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()
        hit = {
            "intent_label": IntentLabel.SELLER_PROMOTION.value,
            "company_domain_raw": "acme.example.com",
        }
        company = await resolve_company(session, workspace.id, hit)
        assert company is None


@pytest.mark.asyncio
async def test_runner_manual_seed(manual_seed_config: SourceConfig) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "seed.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "title": "Hiring a Virtual Assistant",
                        "body": "Remote VA to manage inbox and schedule appointments.",
                        "company_name": "Acme Services",
                        "company_domain": "acme-services.example.com",
                        "contact_routes": [
                            {"type": "generic_email", "value": "hire@acme-services.example.com"}
                        ],
                    }
                ]
            )
        )
        async with AsyncSessionLocal() as session:
            workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
            session.add(workspace)
            await session.flush()
            campaign = Campaign(
                workspace_id=workspace.id,
                name="Test Campaign",
                status="active",
                capability_filter=["virtual_assistant"],
                score_threshold=0.5,
            )
            session.add(campaign)
            await session.flush()

            registry = {"manual_seed": manual_seed_config}
            runner = SourceRunner(registry=registry)
            record = await runner.run(
                session,
                workspace_id=workspace.id,
                campaign_id=campaign.id,
                source_keys=["manual_seed"],
                query_overrides={"manual_seed": {"path": str(path)}},
            )
            company = await session.scalar(
                select(DBCompany).where(DBCompany.workspace_id == workspace.id)
            )
            assert company is not None
        assert record.hits_total == 1
        assert record.hits_qualified_total == 1
        assert record.errors_total == 0
