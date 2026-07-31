"""Source engine unit and integration tests."""

from __future__ import annotations

import importlib.util
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
from services.source_engine.adapters.finance_directory import FinanceDirectoryAdapter
from services.source_engine.adapters.manual_seed import ManualSeedAdapter
from services.source_engine.adapters.nz_finance_advisers import NzFinanceAdvisersAdapter
from services.source_engine.adapters.openstreetmap import OpenStreetMapAdapter
from services.source_engine.classifier import classify_intent, score_intent
from services.source_engine.config import SourceConfig, SourceRegistryLoader
from services.source_engine.enricher import enrich_contact_routes
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
        allowed_outputs=["company_lead"],
        allowed_fields=["company_name", "company_domain", "title", "body"],
    )


def test_source_registry_loads() -> None:
    registry = SourceRegistryLoader().load()
    assert "manual_seed" in registry
    assert "openstreetmap" in registry


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script_name", "function_name"),
    [
        ("extract_team_pages_missing", "get_missing_domains"),
        ("extract_company_web_missing", "get_missing_contact_domains"),
    ],
)
async def test_missing_contact_backfills_deduplicate_domains(
    script_name: str,
    function_name: str,
) -> None:
    spec = importlib.util.spec_from_file_location(
        script_name,
        Path(__file__).resolve().parent.parent / "scripts" / f"{script_name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    async with AsyncSessionLocal() as session:
        workspace = Workspace(
            name=f"Test {script_name}",
            slug=f"test-{uuid4().hex}",
            billing_email="test@example.org",
        )
        session.add(workspace)
        await session.flush()
        session.add_all(
            [
                DBCompany(
                    workspace_id=workspace.id,
                    canonical_name="Shared Domain Branch A",
                    primary_domain="shared-domain.test",
                    country_code="NZ",
                    industry="Finance",
                    employee_count=5,
                ),
                DBCompany(
                    workspace_id=workspace.id,
                    canonical_name="Shared Domain Branch B",
                    primary_domain="shared-domain.test",
                    country_code="NZ",
                    industry="Finance",
                    employee_count=5,
                ),
            ]
        )
        await session.commit()
        workspace_id = workspace.id

    domains = await getattr(module, function_name)(workspace_id)
    assert domains == ["shared-domain.test"]


def test_openstreetmap_rejects_public_email_and_social_domains() -> None:
    config = SourceConfig(
        source_key="openstreetmap",
        source_class="openstreetmap",
        access_mode="public",
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
    )
    adapter = OpenStreetMapAdapter(config)
    assert adapter._coerce_domain("https://gmail.com") == ""
    assert adapter._coerce_domain("https://facebook.com/business") == ""
    assert adapter._coerce_domain("https://bigpond.com.au") == ""
    assert adapter._coerce_domain("https://acme.example.com") == "acme.example.com"


def test_finance_directory_rejects_directory_and_public_domains() -> None:
    config = SourceConfig(
        source_key="finance_directory",
        source_class="finance_directory",
        access_mode="scoped_public_web_crawl",
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
    )
    adapter = FinanceDirectoryAdapter(config)
    assert adapter._coerce_domain("https://financedirectory.net.au/profile") == ""
    assert adapter._coerce_domain("https://www.financedirectory.net.au/profile") == ""
    assert adapter._coerce_domain("https://facebook.com/page") == ""
    assert adapter._coerce_domain("https://gmail.com") == ""
    assert adapter._coerce_domain("https://acme.example.com") == "acme.example.com"


def test_nz_finance_advisers_rejects_directory_and_public_domains() -> None:
    config = SourceConfig(
        source_key="nz_finance_advisers",
        source_class="nz_finance_advisers",
        access_mode="scoped_public_web_crawl",
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
    )
    adapter = NzFinanceAdvisersAdapter(config)
    assert adapter._coerce_domain("https://financeadvisers.co.nz/adviser") == ""
    assert adapter._coerce_domain("https://www.financeadvisers.co.nz/adviser") == ""
    assert adapter._coerce_domain("https://facebook.com/page") == ""
    assert adapter._coerce_domain("https://gmail.com") == ""
    assert adapter._coerce_domain("https://acme.example.com") == "acme.example.com"


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


@pytest.mark.asyncio
async def test_resolve_company_keeps_franchise_branches_distinct() -> None:
    """Different domains for the same brand must create separate company records."""
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()

        # First branch is resolved from a domain-less listing.
        first = await resolve_company(
            session,
            workspace.id,
            {
                "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
                "company_name_raw": "Ray White",
                "company_domain_raw": "",
            },
        )
        assert first is not None
        assert first.primary_domain == ""

        # A second branch with a different domain must not merge into the first.
        second = await resolve_company(
            session,
            workspace.id,
            {
                "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
                "company_name_raw": "Ray White",
                "company_domain_raw": "raywhite-coorparoo.com.au",
            },
        )
        assert second is not None
        assert second.id != first.id
        assert second.primary_domain == "raywhite-coorparoo.com.au"

        # The unkeyed fallback requires the exact same name and domain.
        third = await resolve_company(
            session,
            workspace.id,
            {
                "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
                "company_name_raw": "Ray White",
                "company_domain_raw": "raywhite-coorparoo.com.au",
            },
        )
        assert third is not None
        assert third.id == second.id


@pytest.mark.asyncio
async def test_resolve_company_name_only_keeps_branches_distinct() -> None:
    """Name-only hits do not merge, even with the same brand, so franchise branches keep distinct records."""
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()

        domain_record = await resolve_company(
            session,
            workspace.id,
            {
                "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
                "company_name_raw": "LJ Hooker",
                "company_domain_raw": "ljhooker-euroa.com.au",
            },
        )
        assert domain_record is not None
        assert domain_record.primary_domain == "ljhooker-euroa.com.au"

        branch_a = await resolve_company(
            session,
            workspace.id,
            {
                "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
                "company_name_raw": "LJ Hooker",
                "company_domain_raw": "",
                "location_raw": "Euroa, VIC",
            },
        )
        assert branch_a is not None
        assert branch_a.primary_domain == ""
        assert branch_a.id != domain_record.id

        branch_b = await resolve_company(
            session,
            workspace.id,
            {
                "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
                "company_name_raw": "LJ Hooker",
                "company_domain_raw": "",
                "location_raw": "Seymour, VIC",
            },
        )
        assert branch_b is not None
        assert branch_b.primary_domain == ""
        assert branch_b.id != branch_a.id


@pytest.mark.asyncio
async def test_resolve_company_uses_source_identity_for_shared_domains() -> None:
    """Distinct listings on one corporate domain stay separate and replay stably."""
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()

        coorparoo = {
            "source_key": "openstreetmap",
            "source_native_id": "node/1",
            "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
            "company_name_raw": "Belle Property Coorparoo",
            "company_domain_raw": "belleproperty.com",
            "location_raw": "Coorparoo, QLD",
        }
        leura = {
            **coorparoo,
            "source_native_id": "node/2",
            "company_name_raw": "Belle Property Leura",
            "location_raw": "Leura, NSW",
        }

        first = await resolve_company(session, workspace.id, coorparoo)
        second = await resolve_company(session, workspace.id, leura)
        replay = await resolve_company(session, workspace.id, coorparoo)

        assert first is not None
        assert second is not None
        assert replay is not None
        assert second.id != first.id
        assert replay.id == first.id

        ambiguous_enrichment = {
            "source_key": "team_pages",
            "source_native_id": "https://belleproperty.com/team",
            "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
            "company_name_raw": "belleproperty.com",
            "company_domain_raw": "belleproperty.com",
            "location_raw": "",
        }
        assert (await resolve_company(session, workspace.id, ambiguous_enrichment)) is None


@pytest.mark.asyncio
async def test_resolve_company_groups_profiles_for_the_same_legal_company() -> None:
    """Person-profile IDs may converge on one exact legal company."""
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()

        first_profile = {
            "source_key": "nz_finance_advisers",
            "source_native_id": "profile/1",
            "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
            "company_name_raw": "Castle Trust Financial Planning Limited",
            "company_domain_raw": "",
            "location_raw": "Richmond, NZ",
        }
        second_profile = {
            **first_profile,
            "source_native_id": "profile/2",
            "location_raw": "Nelson, NZ",
        }

        first = await resolve_company(session, workspace.id, first_profile)
        second = await resolve_company(session, workspace.id, second_profile)

        assert first is not None
        assert second is not None
        assert second.id == first.id


@pytest.mark.asyncio
async def test_enrich_contact_routes_reclassifies_unmatched_named_emails() -> None:
    """A named-work-email route whose local part does not match the person becomes generic."""
    async with AsyncSessionLocal() as session:
        workspace = Workspace(name="Test", slug="test", billing_email="test@example.com")
        session.add(workspace)
        await session.flush()
        company = DBCompany(
            workspace_id=workspace.id,
            canonical_name="Acme",
            primary_domain="acme.example.com",
            country_code="AU",
            industry="",
            employee_count=0,
            status="active",
        )
        session.add(company)
        await session.flush()

        routes = [
            {
                "type": "named_work_email_approved",
                "value": "Yve Whitehead <kimberley.fairless@acme.example.com>",
            },
            {
                "type": "named_work_email_approved",
                "value": "Tony Bove <tony.bove@acme.example.com>",
            },
        ]
        created = await enrich_contact_routes(session, workspace.id, company.id, routes)
        await session.commit()

        values_by_type = {(r.route_type, r.value) for r in created}
        assert ("generic_email", "kimberley.fairless@acme.example.com") in values_by_type
        assert any(
            rt == "named_work_email_approved" and "tony.bove@acme.example.com" in val
            for rt, val in values_by_type
        )
