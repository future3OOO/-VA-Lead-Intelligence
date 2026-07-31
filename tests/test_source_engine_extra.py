"""Focused regression tests for PR #2 functional fixes."""

from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from bs4 import BeautifulSoup

from services.source_engine.adapters.company_web import CompanyWebAdapter
from services.source_engine.adapters.finance_directory import FinanceDirectoryAdapter
from services.source_engine.adapters.nz_finance_advisers import NzFinanceAdvisersAdapter
from services.source_engine.adapters.openstreetmap import OpenStreetMapAdapter
from services.source_engine.adapters.team_pages import TeamPagesAdapter, _extract_from_soup
from services.source_engine.config import SourceConfig
from services.source_engine.enricher import (
    _name_in_email_local,
    extract_contact_form_url,
    extract_email,
    extract_phone,
    extract_url,
    is_valid_named_contact,
    normalize_route_value,
)
from services.source_engine.runner import SourceRunner

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_export_helpers() -> tuple:
    """Load export script helpers without adding repo root to sys.path."""
    spec = importlib.util.spec_from_file_location(
        "export_leads_csv", REPO_ROOT / "scripts" / "export_leads_csv.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return (
        module._best_contact,
        module._qualification_score,
        module._best_named_contact,
        module._build_explanation,
        module._csv_safe,
    )


(
    _best_contact,
    _qualification_score,
    _best_named_contact,
    _build_explanation,
    _csv_safe,
) = _load_export_helpers()


def _make_source_config(
    allowed_fields: list[str], allowed_outputs: list[str] | None = None
) -> SourceConfig:
    return SourceConfig(
        source_key="manual_seed",
        source_class="manual_seed",
        access_mode="manual_import",
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
        allowed_outputs=allowed_outputs or ["company_lead", "contact_route"],
        allowed_fields=allowed_fields,
    )


def _make_adapter_config(source_key: str, access_mode: str) -> SourceConfig:
    return SourceConfig(
        source_key=source_key,
        source_class=source_key,
        access_mode=access_mode,
        status="enabled",
        owner="test",
        terms_review_status="approved",
        terms_reviewed_at="2026-07-15T00:00:00+00:00",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_type", "worker_name"),
    [
        (TeamPagesAdapter, "_process_domain"),
        (CompanyWebAdapter, "_crawl_domain"),
    ],
)
async def test_web_adapters_bound_domain_concurrency(
    monkeypatch: pytest.MonkeyPatch,
    adapter_type: type[TeamPagesAdapter] | type[CompanyWebAdapter],
    worker_name: str,
) -> None:
    config = _make_adapter_config(adapter_type.__name__.removesuffix("Adapter").lower(), "web")
    config.rate_limit = {"max_total_concurrency": 2}
    adapter = adapter_type(config)
    active = 0
    peak = 0

    async def fake_worker(*_args: object, **_kwargs: object) -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1

    monkeypatch.setattr(adapter, worker_name, fake_worker)
    try:
        await adapter.fetch(
            uuid4(),
            {
                "domains": [f"example-{index}.com" for index in range(10)],
                "paths": ["/team"],
            },
        )
    finally:
        await adapter.aclose()

    assert peak == 2


@pytest.mark.asyncio
async def test_team_pages_compacts_completed_page_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = TeamPagesAdapter(_make_adapter_config("team_pages", "web"))

    async def robots_allowed(_url: str, _user_agent: str = "VALeadBot/1.0") -> bool:
        return True

    async def http_get(url: str, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><title>Acme Team</title><h1>Acme Services</h1>"
                '<a href="mailto:info@acme.example">Email us</a></html>'
            ),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(adapter, "_robots_allowed", robots_allowed)
    monkeypatch.setattr(adapter, "_http_get", http_get)
    try:
        raw = await adapter._process_domain("acme.example", ["/team"], 1, 1)
    finally:
        await adapter.aclose()

    assert raw is not None
    assert "soup" not in raw
    assert raw["title"] == "Acme Team"
    assert raw["company_name"] == "Acme Services"
    assert adapter.normalize(uuid4(), raw)["body_excerpt"] == "Acme Team Acme Services Email us"


def test_filter_hit_fields_preserves_classification_and_workplace_data() -> None:
    """Intent and workplace type should survive the allowed_fields filter."""
    cfg = _make_source_config(
        [
            "company_name",
            "company_domain",
            "title",
            "body",
            "location",
            "workplace_type",
            "contact_routes",
            "source_url",
            "source_native_id",
        ]
    )
    data = {
        "company_name_raw": "Acme",
        "company_domain_raw": "acme.example.com",
        "workplace_type": "hybrid",
        "intent_label": "buyer_request",
        "title": "Hiring a VA",
        "body_excerpt": "Need help",
        "source_url": "https://example.com",
        "source_native_id": "1",
        "source_hit_priority": 0.9,
        "disallowed_field": "should_be_removed",
    }
    filtered = SourceRunner._filter_hit_fields(data, cfg)
    assert filtered["workplace_type"] == "hybrid"
    assert filtered["intent_label"] == "buyer_request"
    assert "disallowed_field" not in filtered
    assert "source_hit_priority" not in filtered


def test_filter_hit_fields_strips_contact_routes_when_not_allowed() -> None:
    """contact_routes_raw must be removed when the output or field is not allowed."""
    cfg = _make_source_config(["company_name"], allowed_outputs=["company_lead"])
    data = {
        "company_name_raw": "Acme",
        "contact_routes_raw": [{"type": "generic_email", "value": "info@example.com"}],
    }
    filtered = SourceRunner._filter_hit_fields(data, cfg)
    assert filtered.get("contact_routes_raw") == []


def test_contact_normalization_rejects_malformed_values() -> None:
    """Malformed emails, phones, URLs, and named contacts are rejected at the boundary."""
    assert extract_email("Get In Touch <not-an-email>") is None
    assert extract_email("<script>alert(1)</script> info@example.com") is None
    assert (
        extract_email("Albany Creek <info@auswireelectrical.com>") == "info@auswireelectrical.com"
    )
    assert extract_email("hire@acmeservices.com") == "hire@acmeservices.com"
    assert extract_phone("<span>123</span>") is None
    assert extract_phone("Call 1800 013 937 today") == "1800 013 937"
    assert extract_phone("+61 3 5278 2814") == "+61 3 5278 2814"
    assert extract_phone("Camp Hill <07 3264 2311>") == "07 3264 2311"
    assert extract_url("//example.com") is None
    assert extract_url("https://example.com/contact") == "https://example.com/contact"
    assert extract_contact_form_url("https://example.com") is None
    assert extract_contact_form_url("https://facebook.com/example") is None
    assert (
        extract_contact_form_url("https://example.com/contact-us")
        == "https://example.com/contact-us"
    )

    assert is_valid_named_contact("Get In Touch") is False
    assert is_valid_named_contact("Quick Links") is False


def test_csv_safe_neutralizes_spreadsheet_formula_prefixes() -> None:
    for value in ("=1+1", "+cmd", "-2+3", "@SUM(A1:A2)"):
        assert _csv_safe(value) == f"'{value}"
    assert _csv_safe(" \t=1+1") == "'=1+1"
    assert _csv_safe("Wellington \n  Central") == "Wellington Central"
    assert _csv_safe("Acme Services") == "Acme Services"
    assert _csv_safe(42) == 42
    assert is_valid_named_contact("This Week") is False
    assert is_valid_named_contact("1800 013 937") is False
    assert is_valid_named_contact("Tony Bove") is True
    assert is_valid_named_contact("Tony Bove (Electrician)") is True


def test_normalize_route_value_preserves_named_contact_routes() -> None:
    """Display-form named routes keep the person/contact association intact."""
    assert (
        normalize_route_value("named_work_email_approved", "Tony Bove <tony@acmeservices.com>")
        == "Tony Bove <tony@acmeservices.com>"
    )
    assert (
        normalize_route_value("business_phone", "Tony Bove (Director) <+61 3 9000 0000>")
        == "Tony Bove (Director) <+61 3 9000 0000>"
    )
    assert (
        normalize_route_value("sales_form", "https://example.com/contact")
        == "https://example.com/contact"
    )
    assert normalize_route_value("sales_form", "https://example.com") is None
    assert normalize_route_value("named_contact", "Get In Touch") is None


@pytest.mark.parametrize(
    ("routes", "expected_rank"),
    [
        (
            [{"type": "generic_email", "value": "Get In Touch"}],
            "Medium",
        ),
        (
            [{"type": "generic_email", "value": "hire@acmeservices.com"}],
            "High",
        ),
        (
            [{"type": "sales_form", "value": "https://acmeservices.com"}],
            "Medium",
        ),
        (
            [{"type": "sales_form", "value": "https://facebook.com/acmeservices"}],
            "Medium",
        ),
        (
            [{"type": "contact_form", "value": "https://acmeservices.com/contact"}],
            "High",
        ),
    ],
)
def test_high_rank_requires_usable_contact_route(
    routes: list[dict[str, str]], expected_rank: str
) -> None:
    """A High rank is only awarded when a syntactically usable contact route exists."""
    best = _best_contact(routes)
    score, rank, reasons, category = _qualification_score(
        company_name="Acme Property Management",
        title="Property Manager",
        body="We need a remote assistant to manage inbox, tenant enquiries and schedule appointments.",
        location="Sydney, NSW",
        published_at=datetime.now(timezone.utc),
        routes=best,
    )
    assert rank == expected_rank
    if expected_rank == "Medium":
        assert any("contact route missing" in r for r in reasons)
    assert score >= 75
    assert category == "Property/Facilities"


def test_is_valid_named_contact_rejects_page_labels() -> None:
    """Headings, CTAs, policies and calculators must not be treated as people."""
    for label in [
        "Opening Hours",
        "Privacy Policy",
        "Stamp Duty Calculator",
        "Final Thoughts",
        "What We Do",
        "Rental Appraisal",
        "Open Homes",
        "Buyer Enquiry",
        "Get In Touch",
        "Quick Links",
        "This Week",
    ]:
        assert is_valid_named_contact(label) is False


def test_is_valid_named_contact_accepts_names_that_overlap_business_words() -> None:
    assert is_valid_named_contact("Grant Hill") is True
    assert is_valid_named_contact("Brooke Taylor") is True


def test_named_contacts_reject_legal_entities_and_company_names() -> None:
    assert is_valid_named_contact("Absolute Solutions Limited") is False
    assert is_valid_named_contact("Acme Advice Pty Ltd") is False
    assert is_valid_named_contact("Cirrus Legal", "Cirrus Legal") is False
    assert is_valid_named_contact("Mortgage Broker") is False
    assert is_valid_named_contact("Service Email") is False
    assert is_valid_named_contact("Logix Financial") is False
    assert is_valid_named_contact("Terry Monastra Finance Broker") is False
    assert is_valid_named_contact("Scott Joyce Director") is False
    assert is_valid_named_contact("Tanya Hatton Principal") is False
    assert is_valid_named_contact("Rylee Ritchie Sales Agent") is False
    assert is_valid_named_contact("Tony Bove", "Acme Services") is True

    routes = [{"type": "named_contact", "value": "Cirrus Legal"}]
    assert _best_named_contact(routes, "Cirrus Legal") == {}


def test_best_named_contact_only_pairs_explicit_email() -> None:
    """A named person must only receive an email from a route that names them."""
    routes = [
        {"type": "generic_email", "value": "info@acmeservices.com"},
        {"type": "named_contact", "value": "Tony Bove"},
        {"type": "named_work_email_approved", "value": "Tony Bove <tony@acmeservices.com>"},
    ]
    best = _best_named_contact(routes)
    assert best["name"] == "Tony Bove"
    assert best["email"] == "tony@acmeservices.com"


def test_best_named_contact_does_not_pair_generic_email() -> None:
    """A generic company email should not be assigned to a separate named contact."""
    routes = [
        {"type": "generic_email", "value": "info@acmeservices.com"},
        {"type": "named_contact", "value": "Tony Bove"},
    ]
    best = _best_named_contact(routes)
    assert best["name"] == "Tony Bove"
    assert best["email"] == ""


def test_contact_selection_is_independent_of_database_row_order() -> None:
    """Equivalent route sets produce identical exports regardless of query order."""
    routes = [
        {"type": "generic_email", "value": "info@example.com"},
        {"type": "generic_email", "value": "contact@example.com"},
        {"type": "business_phone", "value": "+61 3 9000 0001"},
        {"type": "business_phone", "value": "+61 3 9000 0000"},
    ]
    assert _best_contact(routes) == _best_contact(list(reversed(routes)))


def test_named_email_is_preferred_over_generic_email() -> None:
    """A person-associated route outranks a generic inbox."""
    routes = [
        {"type": "generic_email", "value": "admin@acmeservices.com"},
        {
            "type": "named_work_email_approved",
            "value": "Tony Bove <tony.bove@acmeservices.com>",
        },
    ]
    assert _best_contact(routes)["best_email"] == "tony.bove@acmeservices.com"


def test_best_named_contact_rejects_partial_token_email_match() -> None:
    """A short name token inside another person's email is not an association."""
    routes = [
        {"type": "named_contact", "value": "Peter Sedy Li (Jayme Lee Director)"},
        {
            "type": "named_work_email_approved",
            "value": "Peter Sedy Li <belinda@blackfoxrealestate.com.au>",
        },
    ]
    assert _name_in_email_local("Peter Sedy Li", "belinda@blackfoxrealestate.com.au") is False
    best = _best_named_contact(routes)
    assert best["name"] == "Peter Sedy Li"
    assert best["email"] == ""


def test_normalize_route_value_preserves_named_email_association() -> None:
    """Named email routes keep their display form so the person/email link survives."""
    assert (
        normalize_route_value("named_work_email_approved", "Tony Bove <tony@acmeservices.com>")
        == "Tony Bove <tony@acmeservices.com>"
    )


def test_process_hit_listing_source_is_not_buyer_intent() -> None:
    """Directory/listing bodies containing positive task phrases must not become buyer_request."""
    hit = {
        "source_key": "finance_directory",
        "title": "Finance Directory listing for Acme",
        "body_excerpt": (
            "Acme is an Australian financial services provider in Sydney. "
            "Remote VA support can help with client onboarding, diary management and CRM updates."
        ),
        "company_name_raw": "Acme Mortgage",
        "company_domain_raw": "acme.example.com",
        "contact_routes_raw": [{"type": "generic_email", "value": "info@acme.example.com"}],
        "published_at": datetime.now(timezone.utc),
    }
    processed = SourceRunner()._process_hit(hit)
    assert processed["intent_label"] == "company_existence_only"


def test_listing_score_and_explanation_do_not_claim_observed_job_intent() -> None:
    """A public business listing is prospect-fit evidence, not a job advertisement."""
    routes = {"best_email": "hello@example.com"}
    score, rank, reasons, category = _qualification_score(
        company_name="Acme Property Management",
        title="Property Manager / Real Estate Office",
        body="OpenStreetMap business listing for Acme Property Management.",
        location="Sydney, NSW",
        published_at=datetime.now(timezone.utc),
        routes=routes,
        workplace_type="inferred_remote_friendly",
        intent_label="company_existence_only",
    )
    explanation = _build_explanation(
        company_name="Acme Property Management",
        title="Property Manager / Real Estate Office",
        location="Sydney, NSW",
        category="Property/Facilities",
        score=score,
        rank=rank,
        routes=routes,
        reasons=reasons,
        source_key="openstreetmap",
        intent_label="company_existence_only",
    )

    assert rank == "High"
    assert category == "Property/Facilities"
    assert not any("role is" in reason or "posted" in reason for reason in reasons)
    assert "business listing" in explanation
    assert "is advertising" not in explanation
    assert "role is remote/hybrid" not in explanation


def test_technology_vendor_score_and_export_category_agree() -> None:
    score, rank, reasons, category = _qualification_score(
        company_name="Acme Property Management Software",
        title="Property Manager",
        body="Cloud software platform for property management agencies.",
        location="Sydney, NSW",
        published_at=datetime.now(timezone.utc),
        routes={"best_email": "sales@example.org"},
        workplace_type="inferred_remote_friendly",
        intent_label="company_existence_only",
    )

    assert category == "Other"
    assert score < 55
    assert rank == "Low"
    assert any("technology/software vendor" in reason for reason in reasons)


def test_is_valid_named_contact_rejects_location_and_label_text() -> None:
    """Headings, locations, CTAs and boilerplate labels extracted as names are rejected."""
    for label in [
        "Belimba Park",
        "Cavill Ave",
        "Recently Leased",
        "Wellness Officers",
        "Bookings My Account Sign",
        "Land Size",
        "Eligible Entrants",
        "Aml Compliance",
        "Foreshore Promenade",
        "Kimberley. Address",
        "Asset Registers",
        "Request Measurement",
    ]:
        assert is_valid_named_contact(label) is False


def test_normalize_route_value_rejects_false_named_contacts() -> None:
    """Navigation labels passed as named_contact routes are dropped."""
    assert normalize_route_value("named_contact", "Belimba Park") is None
    assert normalize_route_value("named_contact", "Recently Leased") is None
    assert normalize_route_value("named_contact", "Wellness Officers") is None
    assert normalize_route_value("named_contact", "Tony Bove") is not None


@pytest.mark.parametrize(
    "heading",
    [
        "Solar Vents",
        "Routine Inspections",
        "Entry Requirements",
        "Broome WA",
        "Thailand PDPA",
    ],
)
def test_team_page_headings_without_person_evidence_are_not_contacts(heading: str) -> None:
    """A title-like heading alone must not create a named person."""
    soup = BeautifulSoup(
        f'<div class="team-card"><h2>{heading}</h2><p>Director</p></div>',
        "html.parser",
    )
    routes = _extract_from_soup(soup, "https://example.org/team", "example.org")
    assert not any(route["type"] == "named_contact" for route in routes)


def test_team_page_email_must_identify_the_named_person() -> None:
    """A nearby but unrelated email remains a company-level route."""
    soup = BeautifulSoup(
        """
        <div class="team-card">
          <h2>Peter Sedy Li</h2>
          <p>Jayme Lee Director</p>
          <a href="mailto:belinda@blackfoxrealestate.com.au">Email</a>
        </div>
        """,
        "html.parser",
    )
    routes = _extract_from_soup(
        soup,
        "https://blackfoxrealestate.com.au/team",
        "blackfoxrealestate.com.au",
    )
    assert {(route["type"], route["value"]) for route in routes} == {
        ("generic_email", "belinda@blackfoxrealestate.com.au")
    }


def test_team_page_mailbox_without_person_evidence_stays_generic() -> None:
    """A branch/location mailbox must not invent a named person."""
    soup = BeautifulSoup(
        '<div class="contact"><a href="mailto:berwick.vic@raywhite.com">Email us</a></div>',
        "html.parser",
    )
    routes = _extract_from_soup(
        soup,
        "https://raywhiteberwick.com.au/contact",
        "raywhiteberwick.com.au",
    )
    assert {(route["type"], route["value"]) for route in routes} == {
        ("generic_email", "berwick.vic@raywhite.com")
    }


def test_team_page_explicit_person_card_keeps_named_email() -> None:
    """A same-card person name and matching email remain a named contact."""
    soup = BeautifulSoup(
        """
        <div class="team-card">
          <h2>Jane Smith</h2>
          <p>Director</p>
          <a href="mailto:jane.smith@example.org">Email Jane</a>
        </div>
        """,
        "html.parser",
    )
    routes = _extract_from_soup(soup, "https://example.org/team", "example.org")
    values = {(route["type"], route["value"]) for route in routes}
    assert (
        "named_work_email_approved",
        "Jane Smith (Director) <jane.smith@example.org>",
    ) in values
    assert ("named_contact", "Jane Smith (Director)") in values


def test_team_page_last_name_only_email_match_stays_generic() -> None:
    """Sharing only a surname is not enough to associate an email with a person."""
    soup = BeautifulSoup(
        """
        <div class="team-card">
          <h2>Filter Sam Towns</h2>
          <a href="mailto:jake.towns@petrusma.com.au">Email</a>
        </div>
        """,
        "html.parser",
    )
    routes = _extract_from_soup(
        soup,
        "https://www.petrusma.com.au/team",
        "petrusma.com.au",
    )
    assert {(route["type"], route["value"]) for route in routes} == {
        ("generic_email", "jake.towns@petrusma.com.au")
    }


def test_team_page_emits_only_actionable_contact_forms() -> None:
    """An actual form on a contact page is usable; a homepage form is not."""
    html = """
    <form method="post">
      <input name="email" type="email">
      <textarea name="message"></textarea>
    </form>
    """
    contact_routes = _extract_from_soup(
        BeautifulSoup(html, "html.parser"),
        "https://example.org/contact-us",
        "example.org",
    )
    homepage_routes = _extract_from_soup(
        BeautifulSoup(html, "html.parser"),
        "https://example.org",
        "example.org",
    )

    assert {
        "type": "contact_form",
        "value": "https://example.org/contact-us",
        "is_verified": False,
    } in contact_routes
    assert not any(route["type"] == "contact_form" for route in homepage_routes)


@pytest.mark.asyncio
async def test_finance_directory_description_does_not_mint_people(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic directory prose is not structured person evidence."""
    adapter = FinanceDirectoryAdapter(
        _make_adapter_config("finance_directory", "scoped_public_web_crawl")
    )
    url = "https://www.financedirectory.net.au/victoria/melbourne/finance/capital-arena"
    html = """
    <script type="application/ld+json">
    {
      "@type": "LocalBusiness",
      "name": "Capital Arena",
      "description": "Capital Arena is a mortgage broker led by Investor Relations and Pitch Preparation.",
      "telephone": "03 9000 0000",
      "url": "https://capitalarena.example.org",
      "address": {"addressLocality": "Melbourne", "addressRegion": "VIC"}
    }
    </script>
    """

    async def robots_allowed(_url: str) -> bool:
        return True

    async def http_get(_url: str) -> httpx.Response:
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(adapter, "_robots_allowed", robots_allowed)
    monkeypatch.setattr(adapter, "_http_get", http_get)
    try:
        result = await adapter._fetch_profile(url)
    finally:
        await adapter.aclose()

    assert result is not None
    assert not any(route["type"] == "named_contact" for route in result["contact_routes"])
    assert not any(route["type"] == "sales_form" for route in result["contact_routes"])


def test_directory_website_metadata_is_not_a_contact_form() -> None:
    """Listing websites remain company metadata unless a form is actually found."""
    osm = OpenStreetMapAdapter(_make_adapter_config("openstreetmap", "public_api"))
    osm_hit = osm._normalize_element(
        uuid4(),
        "Sydney, Australia",
        "office",
        "financial",
        "Finance practice",
        "Finance",
        {
            "type": "node",
            "id": 123,
            "tags": {
                "name": "Acme Mortgage Brokers",
                "website": "https://acme.example.org",
                "phone": "02 9000 0000",
            },
        },
    )
    assert osm_hit is not None
    assert not any(route["type"] == "sales_form" for route in osm_hit["contact_routes_raw"])

    nz = NzFinanceAdvisersAdapter(
        _make_adapter_config("nz_finance_advisers", "scoped_public_web_crawl")
    )
    nz_hit = nz.normalize(
        uuid4(),
        {
            "company_name": "Acme Advice",
            "description": "Financial advice",
            "location": "Auckland, New Zealand",
            "website": "https://acme.example.org",
            "name": "Jane Smith",
            "job_title": "Adviser",
            "phone": "09 9000 0000",
            "profile_url": "https://financeadvisers.co.nz/jane-smith",
        },
    )
    assert not any(route["type"] == "sales_form" for route in nz_hit["contact_routes_raw"])


@pytest.mark.asyncio
async def test_http_request_rejects_redirect_outside_expected_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch crawls must not follow redirects into a shared corporate site."""
    adapter = FinanceDirectoryAdapter(
        _make_adapter_config("finance_directory", "scoped_public_web_crawl")
    )
    requested_hosts: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        return httpx.Response(
            302,
            headers={"location": "https://www.corporate.example.org/team"},
            request=request,
        )

    async def safe_url(_url: str) -> bool:
        return True

    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(adapter, "_is_safe_url", safe_url)
    try:
        with pytest.raises(httpx.HTTPError, match="outside expected host"):
            await adapter._http_get(
                "https://branch.example.org/team",
                expected_host="branch.example.org",
            )
    finally:
        await adapter.aclose()

    assert requested_hosts == ["branch.example.org"]


@pytest.mark.asyncio
async def test_http_request_allows_www_redirect_for_expected_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in host boundary should treat www as the same site."""
    adapter = FinanceDirectoryAdapter(
        _make_adapter_config("finance_directory", "scoped_public_web_crawl")
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.org":
            return httpx.Response(
                302,
                headers={"location": "https://www.example.org/team"},
                request=request,
            )
        return httpx.Response(200, text="ok", request=request)

    async def safe_url(_url: str) -> bool:
        return True

    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(adapter, "_is_safe_url", safe_url)
    try:
        response = await adapter._http_get(
            "https://example.org/team",
            expected_host="example.org",
        )
    finally:
        await adapter.aclose()

    assert response.status_code == 200
    assert response.url.host == "www.example.org"


@pytest.mark.asyncio
async def test_http_request_allows_subdomain_redirect_for_expected_apex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = FinanceDirectoryAdapter(
        _make_adapter_config("finance_directory", "scoped_public_web_crawl")
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.org":
            return httpx.Response(
                302,
                headers={"location": "https://nz.example.org/team"},
                request=request,
            )
        return httpx.Response(200, text="ok", request=request)

    async def safe_url(_url: str) -> bool:
        return True

    await adapter.client.aclose()
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(adapter, "_is_safe_url", safe_url)
    try:
        response = await adapter._http_get(
            "https://example.org/team",
            expected_host="example.org",
        )
    finally:
        await adapter.aclose()

    assert response.status_code == 200
    assert response.url.host == "nz.example.org"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script_name", "function_name"),
    [
        ("extract_team_pages", "get_target_domains"),
        ("extract_team_pages_missing", "get_missing_domains"),
        ("extract_company_web", "get_target_domains"),
        ("extract_company_web_missing", "get_missing_contact_domains"),
    ],
)
async def test_extraction_zero_limit_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
    function_name: str,
) -> None:
    """All bounded extraction queries pass LIMIT 0 through unchanged."""
    spec = importlib.util.spec_from_file_location(
        script_name, REPO_ROOT / "scripts" / f"{script_name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    captured: dict[str, object] = {}

    class _Result:
        def all(self) -> list[object]:
            return []

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def execute(self, _statement: object, params: dict[str, object]) -> _Result:
            captured.update(params)
            return _Result()

    monkeypatch.setattr(module, "AsyncSessionLocal", _Session)
    await getattr(module, function_name)(uuid4(), 0)
    assert captured["limit"] == 0
