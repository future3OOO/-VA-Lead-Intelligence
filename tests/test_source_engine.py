"""Source engine unit and integration tests."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import select

from config.enums import IntentLabel
from db.models.campaign import Campaign
from db.models.company import Company as DBCompany
from db.models.contact_route import ContactRoute as DBContactRoute
from db.models.source_hit import SourceHit as DBSourceHit
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
async def test_export_writes_relational_leads_primary_contacts_and_people(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(
        "export_leads_csv",
        Path(__file__).resolve().parent.parent / "scripts" / "export_leads_csv.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    async with AsyncSessionLocal() as session:
        workspace = Workspace(
            name="Named contact export",
            slug=f"named-contact-export-{uuid4().hex}",
            billing_email="test@example.org",
        )
        session.add(workspace)
        await session.flush()
        first = DBCompany(
            workspace_id=workspace.id,
            canonical_name="Alpha Realty",
            primary_domain="alpha.example.org",
            country_code="NZ",
            industry="Real Estate",
            employee_count=5,
        )
        second = DBCompany(
            workspace_id=workspace.id,
            canonical_name="Beta Realty",
            primary_domain="beta.example.org",
            country_code="NZ",
            industry="Real Estate",
            employee_count=5,
        )
        third = DBCompany(
            workspace_id=workspace.id,
            canonical_name="Gamma Realty",
            primary_domain="gamma.example.org",
            country_code="NZ",
            industry="Real Estate",
            employee_count=5,
        )
        session.add_all([first, second, third])
        await session.flush()
        first_email = "Alice Morgan (Property Manager) <alice@alpha.example.org>"
        first_hit = DBSourceHit(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            workspace_id=workspace.id,
            company_id=first.id,
            source_key="openstreetmap",
            source_native_id=f"test-{uuid4().hex}",
            source_url="https://www.openstreetmap.org/node/1",
            observed_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
            title="Property Management Administration Support",
            body_excerpt="Remote-friendly property administration and tenant support.",
            company_name_raw="Alpha Realty",
            company_domain_raw="alpha.example.org",
            location_raw="Auckland, New Zealand",
            workplace_type="inferred_remote_friendly",
            intent_label="company_existence_only",
            contact_routes_raw=[
                {
                    "type": "business_phone",
                    "value": "Alice Morgan (Property Manager) <+64 21 555 0199>",
                }
            ],
            content_hash=uuid4().hex,
            access_policy_version="source-policy-v1",
        )
        displaced_hit = DBSourceHit(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            workspace_id=workspace.id,
            company_id=first.id,
            source_key="openstreetmap",
            source_native_id=f"test-{uuid4().hex}",
            source_url="https://www.openstreetmap.org/node/displaced",
            observed_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            title="Property Management Administration Support",
            body_excerpt="Remote-friendly property administration and tenant support.",
            company_name_raw="Alpha Realty",
            company_domain_raw="alpha.example.org",
            location_raw="Auckland, New Zealand",
            workplace_type="inferred_remote_friendly",
            intent_label="company_existence_only",
            contact_routes_raw=[
                {
                    "type": "business_phone",
                    "value": "Carol Evans (Property Manager) <+64 21 555 0188>",
                },
                {"type": "named_contact", "value": "Nina Cole (Assistant)"},
            ],
            content_hash=uuid4().hex,
            access_policy_version="source-policy-v1",
        )
        enrichment_hit = DBSourceHit(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            workspace_id=workspace.id,
            company_id=first.id,
            source_key="company_web",
            source_native_id=f"test-{uuid4().hex}",
            source_url="https://alpha.example.org/team",
            observed_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
            title="Company contact enrichment",
            body_excerpt="Official company website contact.",
            company_name_raw="Alpha Realty",
            company_domain_raw="alpha.example.org",
            location_raw="Auckland, New Zealand",
            workplace_type="inferred_remote_friendly",
            intent_label="company_existence_only",
            contact_routes_raw=[
                {
                    "type": "business_phone",
                    "value": "Dana Ruiz (Administration Manager) <+64 21 555 0177>",
                }
            ],
            content_hash=uuid4().hex,
            access_policy_version="source-policy-v1",
        )
        unresolved_hit = DBSourceHit(
            workspace_id=workspace.id,
            company_id=None,
            source_key="openstreetmap",
            source_native_id=f"test-{uuid4().hex}",
            source_url="https://www.openstreetmap.org/node/unresolved",
            observed_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
            title="Property Management Administration Support",
            body_excerpt="Remote-friendly property administration and tenant support.",
            company_name_raw="Unresolved Services",
            company_domain_raw="",
            location_raw="Auckland, New Zealand",
            workplace_type="inferred_remote_friendly",
            intent_label="company_existence_only",
            contact_routes_raw=[],
            content_hash=uuid4().hex,
            access_policy_version="source-policy-v1",
        )
        third_hit = DBSourceHit(
            workspace_id=workspace.id,
            company_id=third.id,
            source_key="openstreetmap",
            source_native_id=f"test-{uuid4().hex}",
            source_url="https://www.openstreetmap.org/node/2",
            observed_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
            title="Property Management Administration Support",
            body_excerpt="Remote-friendly property administration and tenant support.",
            company_name_raw="Gamma Realty",
            company_domain_raw="gamma.example.org",
            location_raw="Auckland, New Zealand",
            workplace_type="inferred_remote_friendly",
            intent_label="company_existence_only",
            contact_routes_raw=[],
            content_hash=uuid4().hex,
            access_policy_version="source-policy-v1",
        )
        session.add_all(
            [
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="named_work_email_approved",
                    value="Alice Morgan (Property Manager) <a.morgan@alpha.example.org>",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="named_work_email_approved",
                    value=first_email,
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="named_work_email_approved",
                    value=first_email,
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="social_profile_review_only",
                    value=(
                        "Alice Morgan (Property Manager) - https://www.linkedin.com/in/alice-morgan"
                    ),
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="business_phone",
                    value="Bob Taylor (Director) <+64 21 555 0102>",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="named_contact",
                    value="Dana Ruiz",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="named_contact",
                    value="Name Only (Property Manager)",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="generic_email",
                    value="office@alpha.example.org",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=first.id,
                    route_type="social_profile_review_only",
                    value="https://www.linkedin.com/in/unassigned-person",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace.id,
                    company_id=second.id,
                    route_type="social_profile_review_only",
                    value=(
                        "Alice Morgan (Principal) - https://www.linkedin.com/in/alice-morgan-beta"
                    ),
                    is_verified=False,
                ),
                displaced_hit,
                first_hit,
                enrichment_hit,
                third_hit,
                unresolved_hit,
            ]
        )
        await session.commit()
        workspace_id = workspace.id
        first_id = first.id
        second_id = second.id
        first_hit_id = first_hit.id

    leads_path = tmp_path / "leads.csv"
    companies_path = tmp_path / "companies.csv"
    primary_contacts_path = tmp_path / "primary_contacts.csv"
    contacts_path = tmp_path / "contacts.csv"
    leads_alias_path = tmp_path / "targeted_leads.csv"
    companies_alias_path = tmp_path / "targeted_companies.csv"
    base_argv = [
        "export_leads_csv.py",
        "--workspace-id",
        str(workspace_id),
        "--leads-path",
        str(leads_path),
        "--companies-path",
        str(companies_path),
    ]
    monkeypatch.setattr(sys, "argv", base_argv)
    await module.main()
    leads_without_contact_exports = leads_path.read_bytes()
    companies_without_contact_exports = companies_path.read_bytes()

    monkeypatch.setattr(
        sys,
        "argv",
        base_argv
        + [
            "--primary-contacts-path",
            str(primary_contacts_path),
            "--contacts-path",
            str(contacts_path),
            "--leads-alias-path",
            str(leads_alias_path),
            "--companies-alias-path",
            str(companies_alias_path),
        ],
    )
    await module.main()

    assert leads_path.read_bytes() == leads_without_contact_exports
    assert companies_path.read_bytes() == companies_without_contact_exports
    assert leads_alias_path.read_bytes() == leads_path.read_bytes()
    assert companies_alias_path.read_bytes() == companies_path.read_bytes()
    assert b"\r\n" in leads_path.read_bytes()
    assert b"\n" not in leads_path.read_bytes().replace(b"\r\n", b"")
    with leads_path.open(newline="", encoding="utf-8") as handle:
        lead_rows = list(csv.DictReader(handle))
    assert len(lead_rows) == 3
    assert lead_rows[0]["company_name"] == "Alpha Realty"
    assert lead_rows[0]["lead_id"] == str(first_hit_id)
    assert lead_rows[0]["company_id"] == str(first_id)
    assert lead_rows[0]["primary_contact_id"]
    with primary_contacts_path.open(newline="", encoding="utf-8") as handle:
        primary_rows = list(csv.DictReader(handle))
    assert len(primary_rows) == len(lead_rows)
    assert primary_rows[0]["lead_id"] == lead_rows[0]["lead_id"]
    assert primary_rows[0]["company_id"] == lead_rows[0]["company_id"]
    assert primary_rows[0]["primary_contact_id"] == lead_rows[0]["primary_contact_id"]
    assert primary_rows[0]["primary_contact_status"] == "available"
    assert primary_rows[0]["primary_contact_name"] == "Alice Morgan"
    assert primary_rows[1]["company_name"] == "Gamma Realty"
    assert primary_rows[1]["primary_contact_status"] == "unavailable"
    assert primary_rows[1]["primary_contact_id"] == ""
    assert primary_rows[1]["primary_contact_name"] == ""
    unresolved_lead = next(row for row in lead_rows if row["company_name"] == "Unresolved Services")
    unresolved_primary = next(
        row for row in primary_rows if row["company_name"] == "Unresolved Services"
    )
    assert unresolved_lead["company_id"] == unresolved_lead["primary_contact_id"] == ""
    assert unresolved_primary["company_id"] == unresolved_primary["primary_contact_id"] == ""
    assert unresolved_primary["primary_contact_status"] == "unavailable"
    assert [row["lead_id"] for row in primary_rows] == [row["lead_id"] for row in lead_rows]
    assert [row["company_id"] for row in primary_rows] == [row["company_id"] for row in lead_rows]
    with contacts_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [{key: value for key, value in row.items() if key != "contact_id"} for row in rows] == [
        {
            "company_id": str(first_id),
            "company_name": "Alpha Realty",
            "primary_domain": "alpha.example.org",
            "contact_name": "Alice Morgan",
            "contact_title": "Property Manager",
            "contact_emails": "a.morgan@alpha.example.org; alice@alpha.example.org",
            "contact_phones": "+64 21 555 0199",
            "contact_linkedin_urls": "https://www.linkedin.com/in/alice-morgan",
        },
        {
            "company_id": str(first_id),
            "company_name": "Alpha Realty",
            "primary_domain": "alpha.example.org",
            "contact_name": "Bob Taylor",
            "contact_title": "Director",
            "contact_emails": "",
            "contact_phones": "+64 21 555 0102",
            "contact_linkedin_urls": "",
        },
        {
            "company_id": str(first_id),
            "company_name": "Alpha Realty",
            "primary_domain": "alpha.example.org",
            "contact_name": "Carol Evans",
            "contact_title": "Property Manager",
            "contact_emails": "",
            "contact_phones": "+64 21 555 0188",
            "contact_linkedin_urls": "",
        },
        {
            "company_id": str(first_id),
            "company_name": "Alpha Realty",
            "primary_domain": "alpha.example.org",
            "contact_name": "Dana Ruiz",
            "contact_title": "Administration Manager",
            "contact_emails": "",
            "contact_phones": "+64 21 555 0177",
            "contact_linkedin_urls": "",
        },
        {
            "company_id": str(first_id),
            "company_name": "Alpha Realty",
            "primary_domain": "alpha.example.org",
            "contact_name": "Name Only",
            "contact_title": "Property Manager",
            "contact_emails": "",
            "contact_phones": "",
            "contact_linkedin_urls": "",
        },
        {
            "company_id": str(first_id),
            "company_name": "Alpha Realty",
            "primary_domain": "alpha.example.org",
            "contact_name": "Nina Cole",
            "contact_title": "Assistant",
            "contact_emails": "",
            "contact_phones": "",
            "contact_linkedin_urls": "",
        },
        {
            "company_id": str(second_id),
            "company_name": "Beta Realty",
            "primary_domain": "beta.example.org",
            "contact_name": "Alice Morgan",
            "contact_title": "Principal",
            "contact_emails": "",
            "contact_phones": "",
            "contact_linkedin_urls": "https://www.linkedin.com/in/alice-morgan-beta",
        },
    ]
    contact_ids = {row["contact_id"] for row in rows}
    assert len(contact_ids) == len(rows)
    expected_contact_id = str(
        uuid5(
            UUID("02779786-bdba-4c41-9c01-b1a0fa0685d2"),
            f"{first_id}:alice morgan",
        )
    )
    assert lead_rows[0]["primary_contact_id"] == expected_contact_id
    assert expected_contact_id in contact_ids
    with companies_path.open(newline="", encoding="utf-8") as handle:
        company_rows = list(csv.DictReader(handle))
    company_ids = {row["company_id"] for row in company_rows}
    assert {row["company_id"] for row in lead_rows if row["company_id"]} <= company_ids
    assert {row["company_id"] for row in primary_rows if row["company_id"]} <= company_ids
    assert {row["company_id"] for row in rows} <= company_ids
    for row in rows:
        assert row["contact_name"]
        assert "<" not in "".join(row.values())

    first_export = {
        path: path.read_bytes()
        for path in (leads_path, primary_contacts_path, contacts_path, companies_path)
    }
    await module.main()
    assert first_export == {
        path: path.read_bytes()
        for path in (leads_path, primary_contacts_path, contacts_path, companies_path)
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script_name", "function_name"),
    [
        ("extract_targeted_contacts", "get_missing_contact_domains"),
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
    assert await getattr(module, function_name)(workspace_id, 0) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script_name", "function_name"),
    [
        ("extract_targeted_contacts", "get_missing_contact_domains"),
    ],
)
async def test_contact_backfills_include_named_people_missing_direct_details(
    script_name: str,
    function_name: str,
) -> None:
    """A name alone must not prevent a later crawl for that person's email/phone."""
    spec = importlib.util.spec_from_file_location(
        script_name,
        Path(__file__).resolve().parent.parent / "scripts" / f"{script_name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    async with AsyncSessionLocal() as session:
        workspace = Workspace(
            name=f"Incomplete contact {script_name}",
            slug=f"incomplete-{uuid4().hex}",
            billing_email="test@example.org",
        )
        session.add(workspace)
        await session.flush()
        company = DBCompany(
            workspace_id=workspace.id,
            canonical_name="Named Adviser Ltd",
            primary_domain="named-adviser.test",
            country_code="NZ",
            industry="Finance",
            employee_count=5,
        )
        session.add(company)
        await session.flush()
        session.add(
            DBContactRoute(
                workspace_id=workspace.id,
                company_id=company.id,
                route_type="named_contact",
                value="Aimee Trott (Financial Adviser)",
                is_verified=False,
            )
        )
        company_id = company.id
        await session.commit()
        workspace_id = workspace.id

    domains = await getattr(module, function_name)(workspace_id)
    assert domains == ["named-adviser.test"]

    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                DBContactRoute(
                    workspace_id=workspace_id,
                    company_id=company_id,
                    route_type="named_work_email_approved",
                    value="Aimee Trott (Financial Adviser) <aimee.trott@named-adviser.test>",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace_id,
                    company_id=company_id,
                    route_type="business_phone",
                    value="Aimee Trott (Financial Adviser) <+64 21 555 0101>",
                    is_verified=False,
                ),
                DBContactRoute(
                    workspace_id=workspace_id,
                    company_id=company_id,
                    route_type="social_profile_review_only",
                    value=(
                        "Aimee Trott (Financial Adviser) - https://www.linkedin.com/in/aimee-trott"
                    ),
                    is_verified=False,
                ),
            ]
        )
        await session.commit()

    assert await getattr(module, function_name)(workspace_id) == []


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
async def test_duplicate_hit_enriches_newly_discovered_contact_routes() -> None:
    """A repeated crawl may add contacts even when the source hit already exists."""
    config = SourceConfig(
        source_key="manual_seed",
        source_class="manual_seed",
        access_mode="manual_import",
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
        allowed_outputs=["company_lead", "contact_route"],
        allowed_fields=[
            "company_name",
            "company_domain",
            "title",
            "body",
            "location",
            "workplace_type",
            "contact_routes",
            "source_url",
            "source_native_id",
        ],
    )
    async with AsyncSessionLocal() as session:
        workspace = Workspace(
            name="Repeat contact crawl",
            slug=f"repeat-contact-{uuid4().hex}",
            billing_email="test@example.org",
        )
        session.add(workspace)
        await session.flush()
        now = datetime.now(timezone.utc)
        base = {
            "workspace_id": workspace.id,
            "source_key": "manual_seed",
            "source_native_id": "same-record",
            "source_url": "https://acme.example.org/adviser/one",
            "observed_at": now,
            "published_at": now,
            "title": "Adviser One — Financial Adviser at Acme Advice",
            "body_excerpt": "Financial adviser profile",
            "company_name_raw": "Acme Advice",
            "company_domain_raw": "acme.example.org",
            "location_raw": "Auckland, NZ",
            "workplace_type": "inferred_remote_friendly",
            "intent_label": IntentLabel.COMPANY_EXISTENCE_ONLY.value,
            "raw_snapshot_uri": "",
            "content_hash": "repeat-contact-hash",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
        runner = SourceRunner(registry={"manual_seed": config})
        await runner._persist_hit(
            session,
            {
                **base,
                "contact_routes_raw": [
                    {"type": "generic_email", "value": "office@acme.example.org"}
                ],
            },
            config,
            True,
        )
        await runner._persist_hit(
            session,
            {
                **base,
                "contact_routes_raw": [
                    {
                        "type": "business_phone",
                        "value": "Adviser One (Financial Adviser) <+64 21 555 0101>",
                    }
                ],
            },
            config,
            True,
        )

        routes = (
            await session.scalars(
                select(DBContactRoute).where(DBContactRoute.workspace_id == workspace.id)
            )
        ).all()
        assert {(route.route_type, route.value) for route in routes} == {
            ("generic_email", "office@acme.example.org"),
            (
                "business_phone",
                "Adviser One (Financial Adviser) <+64 21 555 0101>",
            ),
        }


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
                "type": "named_contact",
                "value": "Acme",
            },
            {
                "type": "named_work_email_approved",
                "value": "Yve Whitehead <kimberley.fairless@acme.example.com>",
            },
            {
                "type": "named_work_email_approved",
                "value": "Tony Bove <tony.bove@acme.example.com>",
            },
        ]
        created = await enrich_contact_routes(
            session,
            workspace.id,
            company.id,
            company.canonical_name,
            routes,
        )
        await session.commit()

        values_by_type = {(r.route_type, r.value) for r in created}
        assert not any(route_type == "named_contact" for route_type, _ in values_by_type)
        assert ("generic_email", "kimberley.fairless@acme.example.com") in values_by_type
        assert any(
            rt == "named_work_email_approved" and "tony.bove@acme.example.com" in val
            for rt, val in values_by_type
        )
