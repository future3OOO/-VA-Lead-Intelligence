"""Contact route enricher for resolved companies."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import ContactRouteType
from db.models.contact_route import ContactRoute as DBContactRoute

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"[+\d][\d\s().-]{5,}\d")
_URL_RE = re.compile(r"https?://[^\s<>\"{}|\\^`\[\]]+")

_NAV_LABELS = {
    "about",
    "call",
    "call now",
    "call today",
    "ceiling fans",
    "click here",
    "contact",
    "contact me",
    "contact our team",
    "contact us",
    "details",
    "email us",
    "follow",
    "free quote",
    "get a quote",
    "get in touch",
    "learn more",
    "link",
    "menu",
    "navigation",
    "page",
    "plumber bulimba",
    "quick links",
    "quicklinks",
    "read bio",
    "read more",
    "request a quote",
    "roof restoration",
    "send a message",
    "send message",
    "send us a message",
    "sitemap",
    "this week",
    "use",
    "visit",
    "web design",
    "website",
}

_GENERIC_NAME_WORDS = {
    "info",
    "contact",
    "sales",
    "support",
    "hello",
    "team",
    "careers",
    "hiring",
    "leasing",
    "rent",
    "feedback",
    "admin",
    "office",
    "help",
    "service",
    "marketing",
    "press",
    "billing",
    "jobs",
    "recruiting",
    "hr",
    "legal",
    "media",
    "customer",
    "inquiries",
    "inquiry",
    "questions",
    "apply",
    "job",
    "realestate",
    "realtor",
    "agent",
    "agency",
    "firm",
    "company",
    "email",
    "us",
    "click",
    "here",
    "call",
    "text",
    "message",
    "send",
    "more",
    "learn",
    "today",
    "now",
    "inquire",
    "fb",
    "ig",
    "li",
    "tt",
    "facebook",
    "instagram",
    "twitter",
    "tiktok",
    "youtube",
    "sitemap",
    "connect",
    "visit",
    "read",
    "details",
    "link",
    "follow",
    "about",
    "plumber",
    "electrician",
    "roofing",
    "restoration",
    "roof",
    "ceiling",
    "fans",
    "bulimba",
    "design",
    "web",
    "quote",
    "free",
    "get",
    "in",
    "touch",
    "this",
    "week",
    "quick",
    "links",
}


def looks_like_html(value: str) -> bool:
    # Detect real HTML/XML tags such as <script>, <span class="x">, </p>, not the
    # angle brackets used in "Name <email>" display forms.
    return (
        bool(re.search(r"<[a-zA-Z][\w-]*(?:\s[^>]*)?/?>", value))
        or "&lt;" in value
        or "&gt;" in value
    )


def extract_email(value: str) -> str | None:
    """Return a syntactically valid email address, extracting it from display forms."""
    if looks_like_html(value):
        return None
    # Decode common URL-encoded spacing that can appear in mailto/display forms.
    value = value.replace("%20", " ")
    # Try "Name <email>" or "Name (title) <email>".
    m = re.search(r"<([^<>]+@[^<>]+)>", value)
    candidate = m.group(1).strip() if m else value.strip()
    # If the candidate still contains spaces, the email is probably the last token.
    if " " in candidate and "@" in candidate:
        parts = [p for p in candidate.split() if "@" in p]
        candidate = parts[-1] if parts else candidate.split()[-1]
    candidate = candidate.lower()
    if not re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", candidate):
        return None
    if ".." in candidate or candidate.startswith(".") or candidate.endswith("."):
        return None
    local, _, domain = candidate.partition("@")
    if not local or not domain or "." not in domain.rstrip("."):
        return None
    if domain in ("example.com", "test.com"):
        return None
    return candidate


def extract_phone(value: str) -> str | None:
    """Return a usable phone number extracted from a value or display form."""
    if looks_like_html(value):
        return None
    # Decode common URL-encoded spacing so tel: links render as plain numbers.
    value = value.replace("%20", " ").replace("%2B", "+").replace("%2b", "+")
    m = re.search(r"<([+\d\s().-]+)>", value)
    candidate = m.group(1) if m else value
    # Require at least seven digits.
    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 7:
        return None
    # Prefer the longest phone-like token.
    best: str | None = None
    best_len = 0
    for match in _PHONE_RE.finditer(candidate):
        token = match.group(0).strip()
        token_digits = re.sub(r"\D", "", token)
        if len(token_digits) > best_len:
            best = token
            best_len = len(token_digits)
    return best if best else candidate.strip()


def extract_url(value: str) -> str | None:
    """Return an absolute HTTP(S) URL or reject the value."""
    if looks_like_html(value):
        return None
    m = _URL_RE.search(value)
    if not m:
        return None
    candidate = m.group(0).strip()
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return candidate


def is_valid_named_contact(value: str) -> bool:
    """Return True if the value represents a real person, not a navigation label."""
    text = value.strip()
    if not text or len(text) > 80:
        return False
    if looks_like_html(text):
        return False
    # Parse "Name (Title)" or "Name".
    m = re.match(r"^(.*?)\s*(?:\((.*)\))?\s*$", text)
    name = m.group(1).strip() if m else text
    if not name:
        return False
    lower = name.lower()
    # Reject obvious navigation labels and boilerplate.
    if lower in _NAV_LABELS:
        return False
    for label in _NAV_LABELS:
        if len(label) > 4 and label in lower:
            return False
    words = name.split()
    if not (2 <= len(words) <= 4):
        return False
    # Reject values that are phone numbers, emails, or contain URLs.
    if any(re.search(r"\d", w) for w in words):
        return False
    if "@" in name or "://" in name or "<" in name:
        return False
    # Reject business/role words masquerading as names.
    return not any(w.lower() in _GENERIC_NAME_WORDS for w in words)


def normalize_route_value(route_type: str, value: str) -> str | None:
    """Validate a contact route and return a canonical plain value, or None to drop it."""
    if route_type in ("generic_email", "named_work_email_approved"):
        email = extract_email(value)
        return email if email else None
    if route_type == "business_phone":
        phone = extract_phone(value)
        return phone if phone else None
    if route_type in ("sales_form", "contact_form", "demo_booking"):
        return extract_url(value)
    if route_type == "named_contact":
        return value if is_valid_named_contact(value) else None
    if route_type == "social_profile_review_only":
        return value if extract_url(value) else None
    # Unknown route types fall through unchanged.
    return value


def _resolve_route_type(raw_type: str) -> ContactRouteType:
    try:
        return ContactRouteType(raw_type.lower())
    except ValueError:
        return ContactRouteType.GENERIC_EMAIL


async def enrich_contact_routes(
    session: AsyncSession,
    workspace_id: UUID,
    company_id: UUID,
    routes_raw: list[dict[str, Any]],
) -> list[DBContactRoute]:
    """Persist verified contact routes for a resolved company.

    Routes are normalised and validated at the shared boundary: display-form
    emails and phone numbers are extracted to plain addresses, forms require an
    absolute HTTP(S) URL, and named contacts must be real person names, not
    navigation labels or HTML fragments.
    """
    existing = {
        (r.route_type, r.value.lower())
        for r in (
            await session.scalars(
                select(DBContactRoute).where(
                    DBContactRoute.workspace_id == workspace_id,
                    DBContactRoute.company_id == company_id,
                )
            )
        ).all()
    }
    created: list[DBContactRoute] = []
    for route in routes_raw:
        if not isinstance(route, dict):
            continue
        raw_value = str(route.get("value", "")).strip()
        if not raw_value or len(raw_value) > 255:
            continue
        route_type = _resolve_route_type(route.get("type", "generic_email")).value
        value = normalize_route_value(route_type, raw_value)
        if not value:
            continue
        if (route_type, value.lower()) in existing:
            continue
        existing.add((route_type, value.lower()))
        record = DBContactRoute(
            id=uuid4(),
            workspace_id=workspace_id,
            company_id=company_id,
            route_type=route_type,
            value=value,
            is_verified=bool(route.get("is_verified", False)),
        )
        session.add(record)
        created.append(record)
    await session.flush()
    return created


__all__ = [
    "enrich_contact_routes",
    "extract_email",
    "extract_phone",
    "extract_url",
    "is_valid_named_contact",
    "normalize_route_value",
]
