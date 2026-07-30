"""Focused regression tests for PR #2 functional fixes."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.source_engine.config import SourceConfig
from services.source_engine.enricher import (
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
    return module._best_contact, module._qualification_score, module._best_named_contact


_best_contact, _qualification_score, _best_named_contact = _load_export_helpers()


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

    assert is_valid_named_contact("Get In Touch") is False
    assert is_valid_named_contact("Quick Links") is False
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
    ],
)
def test_high_rank_requires_usable_contact_route(
    routes: list[dict[str, str]], expected_rank: str
) -> None:
    """A High rank is only awarded when a syntactically usable contact route exists."""
    best = _best_contact(routes)
    score, rank, reasons = _qualification_score(
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
