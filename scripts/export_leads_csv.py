#!/usr/bin/env python3
"""Export qualified small-business leads with explanation and ranking."""

import argparse
import asyncio
import csv
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from db.models.company import Company
from db.models.contact_route import ContactRoute
from db.models.source_hit import SourceHit
from db.session import AsyncSessionLocal

JOB_BOARD_SOURCES = {
    "workable_jobs",
    "workable_search",
    "breezy_jobs",
    "greenhouse_jobs",
    "lever_jobs",
    "ashby_jobs",
    "smartrecruiters_postings",
}

ANZ_REGION_RE = re.compile(
    r"\b(australia|new zealand|sydney|melbourne|brisbane|perth|adelaide|canberra|darwin|hobart|auckland|wellington|christchurch|queensland|victoria|nsw|new south wales|western australia|south australia|tasmania|northern territory|north island|south island)\b",
    re.I,
)

REMOTE_KEYWORDS_RE = re.compile(
    r"\b(remote|hybrid|wfh|work from home|work at home|telecommut|virtual assistant)\b",
    re.I,
)

ONSITE_KEYWORDS_RE = re.compile(
    r"\b(on[-\s]?site|on site|in[-\s]?office|in office|office[-\s]?based|site[-\s]?based)\b",
    re.I,
)


def _is_remote_friendly(title: str, body: str, location: str, workplace_type: str = "") -> bool:
    """Return True if the role is advertised as remote/hybrid or clearly virtual."""
    wp = (workplace_type or "").lower()
    if wp in {"remote", "hybrid"}:
        return True
    if wp == "on_site":
        return False
    text = f"{title} {body} {location}".lower()
    if ONSITE_KEYWORDS_RE.search(text) and not REMOTE_KEYWORDS_RE.search(text):
        return False
    return bool(REMOTE_KEYWORDS_RE.search(text))


CATEGORY_PATTERNS = [
    (
        "Property/Facilities",
        r"\bproperty management\b|\bproperty manager\b|\bassistant property manager\b|\bproperty services\b|\bproperty portfolio\b|\bresidential property\b|\bcommercial property\b|\bproperty maintenance\b|\bfacilities management\b|\bfacility management\b|\bbody corporate\b|\bleasing consultant\b|\bproperty administrator\b|\blandlord\b|\btenant\b|\brent roll\b|\brental property\b|\bproperty investment\b",
    ),
    (
        "Real Estate",
        r"\breal estate\b|\brealty\b|\breal estate agency\b|\brealestate\b|\breal estate sales\b|\bproperty sales\b|\breal estate broker\b|\bproperty broker\b|\binvestment property\b|\bcommercial real estate\b|\bresidential real estate\b|\breal estate investment\b",
    ),
    (
        "Financial Services",
        r"\bmortgage broker\b|\bmortgage lender\b|\bmortgage company\b|\bmortgage provider\b|\bmortgage adviser\b|\bmortgage advisor\b|\binsurance broker\b|\binsurance adviser\b|\binsurance advisor\b|\binsurance company\b|\binsurance agency\b|\binsurance brokerage\b|\binsurer\b|\bunderwriter\b|\bfinancial adviser\b|\bfinancial advisor\b|\bwealth adviser\b|\bwealth advisor\b|\baccounting firm\b|\baccounting services\b|\baccountancy\b|\bpublic practice\b|\bchartered accountants\b|\btax agent\b|\bregistered tax agent\b|\baccounting and tax\b|\bpayroll services\b|\bcredit union\b|\blender\b|\bfinancial planning\b|\bfinancial services\b|\bhome loans?\b",
    ),
    (
        "Home Services/Construction",
        r"\bplumbing\b|\bhvac\b|\broofing\b|\belectrician\b|\bhandyman\b|\bhome services\b|\bhome improvement\b|\bconstruction\b|\brenovation\b|\bremodel\b|\bpainting\b|\bchimney\b|\bfire protection\b|\bplumber\b|\belectrical contractor\b|\bsprinkler\b|\bbathroom renovation\b|\bkitchen renovation\b|\bhome builder\b|\bhomebuilder\b|\bbuilding services\b|\bmaintenance services\b|\bproperty maintenance\b|\bhandyman services\b|\btrade services\b",
    ),
    (
        "Legal/Professional",
        r"\blaw firm\b|\blaw office\b|\blegal services\b|\battorney\b|\bllp\b|\blawyers\b",
    ),
]

STAFFING_DENY = [
    "spacex",
    "stripe",
    "airbnb",
    "brex",
    "flexport",
    "conveo",
    "bjak",
    "gmo",
    "instawork",
    "perpay",
    "offchainlabs",
    "hillhousehome",
    "deeter",
    "field-ai",
    "equalparts.ai",
    "the-global-talent-co",
    "salvo software",
    "paladin security",
    "reworks solutions",
    "vora",
    "numa",
    "grounded",
    "classet",
    "ourassistants",
    "apm help",
    "syndi-co",
    "20four7va",
    "hoa talent",
    "manila recruitment",
    "remote recruitment",
    "global talent",
    "remote-raven",
    "pavago",
    "virtuhire",
    "lago-1",
    "hire-with-reef",
    "winning-assistants",
    "d2b-1",
    "msa outsourcing",
    "uptalent",
    "squared away",
    "field-ai",
    "deeter analytics",
    "remotely",
    "farmer",
    "hammerjack",
    "sourcefit",
    "d2b",
]

NON_TARGET_DENY = [
    "datacom",
    "redox",
    "journey beyond",
    "amer sports",
    "clickview",
    "education perfect",
    "online education services",
    "tmgm",
    "kubota",
    "triskele labs",
    "control risks",
    "centorrino technologies",
    "centorrino",
    "king kong",
    "fleetpartners",
    "fleet partners",
    "dof",
    "entain",
    "serko",
    "frank green",
    "fe fundinfo",
    "rimkus",
    "leap legal software",
    "leap legal",
    "legalvision",
    "proquest consulting",
    "vald",
    "cathay digital",
    "scientific safety alliance",
    "isthmus",
    "apexfocusgroup",
    "apex focus group",
]

ALWAYS_STRONG_TITLES = [
    "property manager",
    "assistant property manager",
    "property management assistant",
    "property administrator",
    "leasing consultant",
    "transaction coordinator",
    "maintenance coordinator",
    "real estate assistant",
    "mortgage broker",
    "insurance broker",
    "mortgage broker assistant",
    "mortgage assistant",
    "insurance assistant",
    "mortgage adviser",
    "mortgage advisor",
    "insurance adviser",
    "insurance advisor",
    "loan processor",
    "paraplanner",
    "conveyancing assistant",
    "conveyancer",
    "body corporate manager",
    "facilities manager",
    "facilities coordinator",
]

SECTOR_DEPENDENT_TITLES = [
    "bookkeeper",
    "senior bookkeeper",
    "bookkeeping manager",
    "accountant",
    "senior accountant",
    "assistant accountant",
    "accounting manager",
    "accounts assistant",
    "accounts payable",
    "accounts receivable",
    "payroll",
    "payroll officer",
    "payroll administrator",
    "payroll specialist",
    "tax accountant",
    "tax manager",
    "finance officer",
    "admin officer",
    "administration officer",
    "operations coordinator",
    "project coordinator",
    "scheduling coordinator",
    "appointment setter",
    "sales support",
    "crm administrator",
    "contracts administrator",
    "sales administrator",
    "insurance coordinator",
    "customer support coordinator",
    "remote services administrator",
    "collections officer",
    "retentions officer",
    "novated leasing consultant",
    "lease administrator",
    "operations assistant",
]

UNIVERSAL_ADMIN_TITLES = [
    "virtual assistant",
    "executive assistant",
    "administrative assistant",
    "office manager",
    "receptionist",
    "data entry",
    "legal assistant",
    "legal secretary",
]

STRONG_ADMIN_TITLES = ALWAYS_STRONG_TITLES + SECTOR_DEPENDENT_TITLES + UNIVERSAL_ADMIN_TITLES

MEDIUM_ADMIN_TITLES = [
    "coordinator",
    "assistant",
    "admin",
    "support",
    "associate",
    "officer",
    "clerk",
    "operations",
    "service delivery",
    "client operations",
    "people operations",
    "business operations",
]


def _detect_category(text: str) -> str:
    text = f" {text.lower()} "
    for cat, pat in CATEGORY_PATTERNS:
        if re.search(pat, text):
            return cat
    return "Other"


def _is_target(text: str, title: str = "") -> bool:
    text_lower = text.lower()
    for term in STAFFING_DENY:
        if term in text_lower:
            return False
    for term in NON_TARGET_DENY:
        if term in text_lower:
            return False
    title_lower = title.lower()
    if any(t in title_lower for t in STRONG_ADMIN_TITLES):
        return True
    if not any(t in title_lower for t in MEDIUM_ADMIN_TITLES):
        return False
    category = _detect_category(text)
    return category != "Other"


def _qualification_score(
    company_name: str,
    title: str,
    body: str,
    location: str,
    published_at: datetime,
    routes: dict[str, str],
) -> tuple[int, str]:
    text = f"{title} {body} {company_name} {location}".lower()
    score = 40
    rank = "Low"
    reasons: list[str] = []

    title_lower = title.lower()
    category = _detect_category(text)

    if any(t in title_lower for t in ALWAYS_STRONG_TITLES):
        score += 30
        reasons.append("title is a strong, sector-specific VA-adjacent role")
    elif any(t in title_lower for t in UNIVERSAL_ADMIN_TITLES):
        if category != "Other":
            score += 30
            reasons.append("title is a universal admin role in a target sector")
        else:
            score += 15
            reasons.append("title is a universal admin role, but the sector is not clearly target")
    elif any(t in title_lower for t in SECTOR_DEPENDENT_TITLES):
        if category != "Other":
            score += 30
            reasons.append("title is a finance/operations admin role in a target sector")
        else:
            score += 15
            reasons.append(
                "title is a finance/operations admin role, but the sector is not clearly target"
            )
    elif any(t in title_lower for t in MEDIUM_ADMIN_TITLES):
        score += 15
        reasons.append("title shows admin/coordination responsibilities")

    if category != "Other":
        score += 10
        reasons.append(f"company/role in {category} sector")

    if REMOTE_KEYWORDS_RE.search(text):
        score += 10
        reasons.append("role is remote/hybrid (well suited to a VA)")
    if ONSITE_KEYWORDS_RE.search(text):
        score -= 25
        reasons.append("on-site language detected (red flag for remote VA fit)")

    if published_at:
        try:
            age_days = (datetime.now(timezone.utc) - published_at).days
            if age_days <= 30:
                score += 10
                reasons.append("posted within the last 30 days")
            elif age_days <= 90:
                score += 5
                reasons.append("posted within the last 90 days")
        except Exception:
            pass

    if routes.get("best_email") or routes.get("best_phone"):
        score += 5
        reasons.append("verified contact route available")

    score = min(score, 100)
    if score >= 85:
        rank = "High"
    elif score >= 60:
        rank = "Medium"
    return score, rank


def _build_explanation(
    company_name: str,
    title: str,
    location: str,
    category: str,
    score: int,
    rank: str,
    routes: dict[str, str],
) -> str:
    contact_parts = []
    if routes.get("best_email"):
        contact_parts.append(f"email {routes['best_email']}")
    if routes.get("best_phone"):
        contact_parts.append(f"phone {routes['best_phone']}")
    if routes.get("best_form"):
        contact_parts.append(f"contact form {routes['best_form']}")
    contact = "; ".join(contact_parts) if contact_parts else "no direct contact route yet"
    explanation = (
        f"{rank} fit ({score}/100): {company_name} ({category}) is hiring a '{title}' in {location}. "
        f"This role indicates operational/administrative workload that a VA can support "
        f"(inbox/CRM management, scheduling, bookkeeping, maintenance/vendor coordination, or customer follow-up). "
        f"Best contact: {contact}."
    )
    return explanation


def _best_contact(routes: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for r in routes:
        t = r["type"]
        v = r["value"]
        if t in ("named_work_email_approved", "generic_email") and "best_email" not in result:
            result["best_email"] = v
        elif t == "business_phone" and "best_phone" not in result:
            result["best_phone"] = v
        elif t == "sales_form" and "best_form" not in result:
            result["best_form"] = v
    return result


def _is_plausible_person_name(name: str) -> bool:
    """Return True if the extracted string looks like a real person name."""
    if not name or len(name) > 50 or len(name) < 3:
        return False
    if "@" in name or "http" in name.lower() or "/" in name or "linkedin" in name.lower():
        return False
    words = name.split()
    if not (2 <= len(words) <= 4):
        return False
    generic = {
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
        "general",
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
        "use",
        "visit",
        "website",
        "page",
        "menu",
        "navigation",
        "read",
        "about",
        "details",
        "link",
        "follow",
    }
    if any(
        w.lower() in generic or w.lower() in STRONG_ADMIN_TITLES or w.lower() in MEDIUM_ADMIN_TITLES
        for w in words
    ):
        return False
    return not all(w.isupper() and len(w) <= 3 for w in words)


_TITLE_BOILERPLATE = re.compile(
    r"\b(Read Bio|Read More|Connect|LinkedIn|Facebook|Instagram|Twitter|TikTok|YouTube)\b",
    re.I,
)


def _clean_title_text(title: str) -> str:
    title = _TITLE_BOILERPLATE.sub("", title)
    title = title.replace("|", " ").replace("  ", " ")
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def _parse_named_route(value: str) -> dict[str, str]:
    """Parse a formatted named route such as 'Name (Title) <email>'."""
    parsed: dict[str, str] = {}
    m = re.match(r"^(.*?)\s*(?:\((.*?)\))?\s*[<-]\s*(.+?)$", value.strip())
    if m:
        name = m.group(1).strip()
        title = _clean_title_text((m.group(2) or "").strip())
        payload = m.group(3).strip().rstrip(">")
        # Drop implausibly long/boilerplate titles while keeping the contact.
        if title and (len(title) > 60 or len(title.split()) > 8):
            title = ""
        if _is_plausible_person_name(name):
            parsed = {"name": name, "title": title, "value": payload}
    return parsed


def _best_named_contact(routes: list[dict[str, str]]) -> dict[str, str]:
    """Return the best named hiring contact (email or LinkedIn) for a company."""
    best: dict[str, str] = {}
    for r in routes:
        if r["type"] != "named_work_email_approved":
            continue
        parsed = _parse_named_route(r["value"])
        if parsed:
            best.update(parsed)
            best.setdefault("email", parsed.get("value", ""))
            break
    # If no named email, try a LinkedIn profile with a name.
    if not best.get("value"):
        for r in routes:
            if r["type"] != "social_profile_review_only":
                continue
            parsed = _parse_named_route(r["value"])
            if parsed and parsed.get("value", "").startswith("http"):
                best.update(parsed)
                best.setdefault("linkedin", parsed.get("value", ""))
                break
    return best


async def main() -> None:
    parser = argparse.ArgumentParser(description="Export qualified leads and company contacts")
    parser.add_argument(
        "--workspace-id", type=UUID, default=UUID("f72ae1f9-f45e-45dc-a0d9-1a9e5e0b2a24")
    )
    parser.add_argument("--leads-path", default="/tmp/small_business_leads_with_contacts.csv")
    parser.add_argument("--companies-path", default="/tmp/all_companies.csv")
    parser.add_argument(
        "--region",
        choices=["all", "anz"],
        default="all",
        help="Filter leads to a region (anz = Australia + New Zealand)",
    )
    args = parser.parse_args()

    workspace_id = args.workspace_id
    leads_path = args.leads_path
    companies_path = args.companies_path
    region_filter = args.region

    async with AsyncSessionLocal() as session:
        # Load all contact routes keyed by company_id
        contact_rows = (
            await session.scalars(
                select(ContactRoute).where(ContactRoute.workspace_id == workspace_id)
            )
        ).all()
        contact_by_company: dict[UUID, list[dict[str, str]]] = defaultdict(list)
        for cr in contact_rows:
            contact_by_company[cr.company_id].append({"type": cr.route_type, "value": cr.value})

        # Load companies
        company_rows = (
            await session.scalars(select(Company).where(Company.workspace_id == workspace_id))
        ).all()
        companies_by_id = {c.id: c for c in company_rows}

        # Write all companies
        with open(companies_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "company_id",
                    "company_name",
                    "primary_domain",
                    "target_fit",
                    "source_hit_count",
                    "best_email",
                    "best_phone",
                    "best_form",
                    "named_contact_name",
                    "named_contact_title",
                    "named_contact_email",
                    "named_contact_linkedin",
                ]
            )
            for c in company_rows:
                company_routes = contact_by_company.get(c.id, [])
                best = _best_contact(company_routes)
                named = _best_named_contact(company_routes)
                target = _is_target(f"{c.canonical_name} {c.primary_domain or ''}", "")
                hit_count = (
                    await session.execute(
                        select(func.count()).where(
                            SourceHit.workspace_id == workspace_id,
                            SourceHit.company_id == c.id,
                            SourceHit.source_key.in_(JOB_BOARD_SOURCES),
                        )
                    )
                ).scalar()
                writer.writerow(
                    [
                        c.id,
                        c.canonical_name,
                        c.primary_domain or "",
                        "Yes" if target else "No",
                        hit_count,
                        best.get("best_email", ""),
                        best.get("best_phone", ""),
                        best.get("best_form", ""),
                        named.get("name", ""),
                        named.get("title", ""),
                        named.get("email", ""),
                        named.get("linkedin", ""),
                    ]
                )

        # Build leads
        source_hits = (
            await session.scalars(
                select(SourceHit).where(
                    SourceHit.workspace_id == workspace_id,
                    SourceHit.source_key.in_(JOB_BOARD_SOURCES),
                )
            )
        ).all()

        lead_rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for hit in source_hits:
            title = hit.title or ""
            company_name = hit.company_name_raw or ""
            location = hit.location_raw or ""
            body = hit.body_excerpt or ""
            workplace_type = hit.workplace_type or ""
            text = f"{title} {company_name} {body} {location}"
            if not _is_target(text, title):
                continue
            if not _is_remote_friendly(title, body, location, workplace_type):
                continue
            if region_filter == "anz" and not ANZ_REGION_RE.search(text):
                continue
            category = _detect_category(text)
            key = (company_name.lower().strip(), title.lower().strip())
            if key in seen:
                continue
            seen.add(key)

            company = companies_by_id.get(hit.company_id) if hit.company_id else None
            domain = (
                (company.primary_domain or hit.company_domain_raw or "")
                if company
                else (hit.company_domain_raw or "")
            )
            best_routes = _best_contact(contact_by_company.get(company.id, [])) if company else {}
            score, rank = _qualification_score(
                company_name, title, body, location, hit.published_at, best_routes
            )
            explanation = _build_explanation(
                company_name, title, location, category, score, rank, best_routes
            )

            named = _best_named_contact(contact_by_company.get(company.id, [])) if company else {}
            lead_rows.append(
                {
                    "company_name": company_name,
                    "primary_domain": domain,
                    "job_title": title,
                    "location": location,
                    "workplace_type": workplace_type,
                    "category": category,
                    "source": hit.source_key,
                    "source_url": hit.source_url,
                    "intent_label": hit.intent_label,
                    "published_at": hit.published_at.isoformat() if hit.published_at else "",
                    "qualification_score": score,
                    "rank": rank,
                    "explanation": explanation,
                    "best_email": best_routes.get("best_email", ""),
                    "best_phone": best_routes.get("best_phone", ""),
                    "best_form": best_routes.get("best_form", ""),
                    "named_contact_name": named.get("name", ""),
                    "named_contact_title": named.get("title", ""),
                    "named_contact_email": named.get("email", ""),
                    "named_contact_linkedin": named.get("linkedin", ""),
                }
            )

        lead_rows.sort(key=lambda x: (-x["qualification_score"], x["company_name"].lower()))

        # Cap each company at the strongest 18 leads so the export stays diverse.
        per_company_count: dict[str, int] = defaultdict(int)
        capped_rows: list[dict[str, Any]] = []
        for row in lead_rows:
            name = row["company_name"].lower().strip()
            if per_company_count[name] >= 18:
                continue
            per_company_count[name] += 1
            capped_rows.append(row)
        lead_rows = capped_rows

        with open(leads_path, "w", newline="", encoding="utf-8") as f:
            leads_writer = csv.DictWriter(
                f,
                fieldnames=[
                    "company_name",
                    "primary_domain",
                    "job_title",
                    "location",
                    "workplace_type",
                    "category",
                    "source",
                    "source_url",
                    "intent_label",
                    "published_at",
                    "qualification_score",
                    "rank",
                    "explanation",
                    "best_email",
                    "best_phone",
                    "best_form",
                    "named_contact_name",
                    "named_contact_title",
                    "named_contact_email",
                    "named_contact_linkedin",
                ],
            )
            leads_writer.writeheader()
            leads_writer.writerows(lead_rows)

        print(f"Exported {len(lead_rows)} leads to {leads_path}")
        print(f"Exported {len(company_rows)} companies to {companies_path}")
        print("Rank breakdown:")
        from collections import Counter

        print(Counter(r["rank"] for r in lead_rows))
        print("Category breakdown:")
        print(Counter(r["category"] for r in lead_rows))


if __name__ == "__main__":
    import sys

    sys.path.insert(0, "src")
    asyncio.run(main())
