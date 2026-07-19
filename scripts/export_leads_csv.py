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

EXPORT_SOURCES = {
    "workable_jobs",
    "workable_search",
    "workable_company",
    "workable_html_search",
    "breezy_jobs",
    "greenhouse_jobs",
    "lever_jobs",
    "ashby_jobs",
    "smartrecruiters_postings",
    "jobicy",
    "openstreetmap",
}

ANZ_REGION_RE = re.compile(
    r"\b(australia|new zealand|apac|sydney|melbourne|brisbane|perth|adelaide|canberra|darwin|hobart|auckland|wellington|christchurch|queensland|victoria|nsw|new south wales|western australia|south australia|tasmania|northern territory|north island|south island)\b",
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
    "farmer",
    "hammerjack",
    "sourcefit",
    "d2b",
    "huzzle",
    "huzzle.app",
    "huzzle.ai",
    "axiom",
    "axiomlaw",
    "first focus",
    "firstfocus",
    "teamified",
    "steadfast solutions",
    "steadfastsolutions",
    "kg talent",
    "kgtalent",
    "inautalent",
    "inaudalent",
    "hire resolve",
    "hire resolve.com",
]

NON_TARGET_DENY = [
    "datacom",
    "redox",
    "journey beyond",
    "amer sports",
    "actionstep",
    "prophix",
    "cloudbeds",
    "figma",
    "first focus",
    "firstfocus",
    "teamified",
    "steadfast solutions",
    "steadfastsolutions",
    "huzzle",
    "huzzle.app",
    "huzzle.ai",
    "axiom",
    "axiomlaw",
    "clickview",
    "education perfect",
    "online education services",
    "kubota",
    "triskele labs",
    "control risks",
    "centorrino technologies",
    "centorrino",
    "king kong",
    "dof",
    "entain",
    "serko",
    "frank green",
    "fe fundinfo",
    "rimkus",
    "leap legal software",
    "leap legal",
    "proquest consulting",
    "vald",
    "cathay digital",
    "scientific safety alliance",
    "isthmus",
    "apexfocusgroup",
    "apex focus group",
    "tmgm",
    "fleetpartners",
    "fleet partners",
    "corto",
    "corto pty ltd",
    "legalvision",
    "the halo trust",
    "grant thornton",
    "grant thornton new zealand",
    "australian payments plus",
    "australianpaymentsplus",
    "ofload",
    "compass education",
    "compasseducation",
    "peopleworth",
    "civica",
    "infosys",
    "natterbox",
    "vizrt",
    "genetec",
    "veracross",
    "timescapes",
    "hire resolve.com",
    "hire resolve",
    "moreton capital partners",
    "red energy",
    "sasmar",
    "lyka",
    "eatclub",
    "mathspace",
    "hosting.com",
    "hostingcom",
    "rfi global",
    "squared away",
    "dext",
    "valsoft",
    "valsoft corporation",
    "efm",
    "infosys singapore & australia",
    "natterbox ltd",
    "redenergy",
    "today",
    "genetec inc",
    "vizrt ltd",
]

# Role-based signals.  A "direct" role is something a VA can fill or directly
# support; an "operational support" role indicates the company has admin
# workload that a VA can take off the team.  The scoring model weights the
# company sector + role signal together so a senior accountant at an
# accounting practice still scores as a medium lead (the firm needs admin),
# while a senior accountant at a tech company is dropped.
DIRECT_VA_ROLES = [
    "virtual assistant",
    "executive assistant",
    "senior executive assistant",
    "personal assistant",
    "administrative assistant",
    "admin assistant",
    "admin officer",
    "administration officer",
    "administrative officer",
    "office manager",
    "office administrator",
    "office assistant",
    "receptionist",
    "front desk receptionist",
    "front desk",
    "data entry",
    "data entry clerk",
    "data entry operator",
    "bookkeeper",
    "bookkeeping",
    "senior bookkeeper",
    "payroll officer",
    "payroll administrator",
    "payroll specialist",
    "payroll clerk",
    "accounts payable",
    "accounts receivable",
    "accounts assistant",
    "accounts clerk",
    "finance assistant",
    "assistant accountant",
    "accounting assistant",
    "tax assistant",
    "paralegal",
    "senior paralegal",
    "legal assistant",
    "legal secretary",
    "law clerk",
    "conveyancing assistant",
    "conveyancing clerk",
    "property administrator",
    "property management assistant",
    "property assistant",
    "leasing consultant",
    "leasing assistant",
    "leasing coordinator",
    "maintenance coordinator",
    "maintenance assistant",
    "scheduling coordinator",
    "appointment setter",
    "appointment scheduler",
    "customer support",
    "customer service",
    "customer care",
    "sales support",
    "sales administrator",
    "operations assistant",
    "operations coordinator",
    "operations administrator",
    "project coordinator",
    "claims officer",
    "retentions officer",
    "collections officer",
    "loan processor",
    "loan administrator",
    "insurance administrator",
    "mortgage assistant",
    "insurance assistant",
    "underwriter assistant",
    "mortgage broker assistant",
    "finance broker",
    "remote services administrator",
    "company secretary",
    "company secretarial",
]

# Roles that carry heavy administrative burden and are commonly supported by VAs.
OPERATIONAL_SUPPORT_ROLES = [
    "property manager",
    "assistant property manager",
    "property coordinator",
    "leasing manager",
    "facilities manager",
    "facilities coordinator",
    "body corporate manager",
    "strata manager",
    "building manager",
    "operations manager",
    "practice manager",
    "business manager",
    "project manager",
    "maintenance manager",
    "claims consultant",
    "claims assessor",
    "claims officer",
    "retentions officer",
    "collections officer",
    "loan processor",
    "loan administrator",
    "insurance administrator",
    "mortgage assistant",
    "insurance assistant",
    "underwriter assistant",
    "business support",
    "client services",
    "client services manager",
    "sales support",
    "sales administrator",
    "sales coordinator",
    "customer support",
    "customer service",
    "customer care",
]

# Client-facing roles that create admin follow-up work but are not pure admin.
CLIENT_FACING_ROLES = [
    "account manager",
    "customer success manager",
    "client success manager",
    "client relationship",
    "account executive",
]

# Professional service-provider roles.  The open job is not a VA role, but the
# firm itself is a strong VA prospect because professionals produce admin work.
PROFESSIONAL_ROLES = [
    "mortgage broker",
    "insurance broker",
    "financial planner",
    "paraplanner",
    "conveyancer",
    "lawyer",
    "solicitor",
    "barrister",
    "attorney",
    "associate",
    "senior associate",
    "accountant",
    "tax accountant",
    "senior accountant",
    "accounting manager",
    "finance manager",
    "tax manager",
    "payroll manager",
    "accounts manager",
    "credit controller",
    "billing officer",
    "debt collector",
    "ar manager",
    "ap manager",
    "administration manager",
    "office coordinator",
]

# Titles that are clearly not VA-relevant, regardless of sector.
NON_ADMIN_ROLES_RE = re.compile(
    r"\b(?:software engineer|data engineer|data scientist|devops|sre|nurse|registered nurse|doctor|gp|chef|cook|truck driver|forklift|warehouse|mechanic|electrician|plumber|carpenter|painter|teacher|lecturer|scientist|pharmacist|physiotherapist|psychologist|social worker|sales development|business development manager|sales manager|sales lead|outbound sales|account executive|marketing manager|brand manager|product manager|program manager|hr manager|people manager|recruitment manager|talent acquisition|recruiter|data analyst|business analyst|ai engineer|machine learning engineer)\b",
    re.I,
)

SENIOR_PROFESSIONAL_RE = re.compile(
    r"\b(?:senior|lead|principal|managing director|chief\s+\w+\s+officer|chief\s+\w+|head of|vice president|vp)\b",
    re.I,
)

# Senior professional titles that signal the open role is not a VA hire.
# The firm may still need admin support, but the advertised role itself is not
# suitable for a virtual assistant.
NOT_VA_SENIOR_RE = re.compile(
    r"\b(?:senior\s+(?:accountant|financial\s+accountant|tax\s+accountant|accounting\s+manager|finance\s+manager|tax\s+manager|payroll\s+manager|accounts\s+manager|credit\s+controller|lawyer|solicitor|associate|paralegal|conveyancer|underwriter|loan\s+officer)|lead\s+(?:accountant|lawyer|solicitor)|principal\s+(?:accountant|lawyer|solicitor))\b",
    re.I,
)

# Signals that the company is a technology vendor, not the small/midsize
# service business that would hire a VA.
TECH_VENDOR_RE = re.compile(
    r"\b(?:software\s+(?:company|business|provider|platform|vendor|solutions|product|products)|saas|cloud\s+platform|technology\s+(?:company|provider|solutions|platform|start-up|startup)|tech\s+(?:company|start-up|startup)|ai\s+(?:agent|platform|solution|powered)|ai[-\s]?powered\s+(?:software|platform|solution|legal)|voice\s+ai|education\s+technology|vertical\s+market\s+software|enterprise\s+(?:software|solutions)|software\s+acquisition|acquire\s+.*\bsoftware|trusted\s+by\s+.*\b(?:firms|companies|law\s+firms|businesses)\s+worldwide)\b",
    re.I,
)

# Phrases in the company/job description that indicate a high administrative
# workload that a VA can relieve.
ADMIN_BURDEN_RE = re.compile(
    r"\b(?:high volume|heavy workload|busy|fast[\s\-]?paced|growing|expanding|new office|multiple sites|administrative support|admin support|inbox|crm|data entry|scheduling|diary management|client onboarding|tenant|maintenance request|claims processing|loan files|invoicing|billing|accounts|reconciliation|compliance|documentation|filing|phones|emails|correspondence|coordination|coordinating|paperwork|reporting|deadlines|backlog|expanding team|small team)\b",
    re.I,
)

VA_USE_CASES = {
    "Property/Facilities": "Property management firms handle tenant enquiries, maintenance coordination, lease admin, and rent-roll data entry — core VA workloads.",
    "Real Estate": "Real estate agencies need listing admin, CRM updates, buyer/tenant follow-up, and appointment scheduling.",
    "Financial Services": "Accounting, bookkeeping, mortgage, and insurance firms produce high volumes of client files, claims, loan paperwork, scheduling, and compliance admin.",
    "Home Services/Construction": "Trade and home-service businesses with field staff need scheduling, dispatch, invoicing, and customer follow-up.",
    "Legal/Professional": "Small law firms and professional practices need document prep, client intake, diary management, and billing admin.",
    "Other": "The company is building operational/admin support and may need flexible VA capacity.",
}

# Common words used in job titles so we don't mistake them for a person's name.
VA_ROLE_WORDS: set[str] = set()
for _phrase in DIRECT_VA_ROLES + OPERATIONAL_SUPPORT_ROLES:
    VA_ROLE_WORDS.update(w.lower() for w in _phrase.split())
VA_ROLE_WORDS.update(
    {
        "manager",
        "assistant",
        "officer",
        "coordinator",
        "consultant",
        "specialist",
        "admin",
        "support",
        "executive",
        "director",
        "partner",
        "associate",
        "senior",
        "lead",
        "principal",
    }
)


def _has_role(title: str, roles: list[str]) -> bool:
    title_lower = title.lower()
    return any(role in title_lower for role in roles)


def _is_direct_va_role(title: str) -> bool:
    return _has_role(title, DIRECT_VA_ROLES)


def _is_operational_support_role(title: str) -> bool:
    return _has_role(title, OPERATIONAL_SUPPORT_ROLES) and not _is_direct_va_role(title)


def _is_client_facing_role(title: str) -> bool:
    return _has_role(title, CLIENT_FACING_ROLES)


def _is_professional_role(title: str) -> bool:
    return _has_role(title, PROFESSIONAL_ROLES)


def _is_senior_professional(title: str) -> bool:
    # A "Senior Executive Assistant" or "Senior Paralegal" is still a direct admin role.
    if _is_direct_va_role(title):
        return False
    return bool(SENIOR_PROFESSIONAL_RE.search(title))


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
    # Senior professional postings (e.g., Senior Accountant, Lead Lawyer) are
    # not themselves VA roles even when the firm is in a target sector.
    if NOT_VA_SENIOR_RE.search(title_lower):
        return False
    category = _detect_category(text)
    # Target-sector companies are leads even when the open role is senior,
    # because the firm itself likely needs VA support.  Screen out obviously
    # unrelated technical/health/trade titles.
    if category != "Other":
        return not bool(NON_ADMIN_ROLES_RE.search(title_lower))
    # Non-target companies only make the cut if the role is clearly admin.
    return _is_direct_va_role(title) or _is_operational_support_role(title)


def _qualification_score(
    company_name: str,
    title: str,
    body: str,
    location: str,
    published_at: datetime,
    routes: dict[str, str],
    workplace_type: str = "",
) -> tuple[int, str, list[str]]:
    text = f"{title} {body} {company_name} {location}".lower()
    title_lower = title.lower()
    category = _detect_category(text)
    score = 0
    reasons: list[str] = []

    # 0. Technology/software vendor check.  Vendors sell tools to target
    # businesses but are rarely the end-user service business that needs a VA.
    is_tech_vendor = bool(TECH_VENDOR_RE.search(f"{company_name} {body}".lower()))

    # 1. Sector fit (company-level signal)
    if is_tech_vendor:
        category = "Other"
        score -= 25
        reasons.append("company appears to be a technology/software vendor, not a service business")
    elif category != "Other":
        score += 30
        reasons.append(f"company/role is in the {category} sector")
    elif _is_direct_va_role(title):
        score += 5
        reasons.append("role is a direct admin/VA role")

    # 2. Role signal (is the open job admin/VA, operational, professional, or unrelated?)
    if _is_direct_va_role(title):
        score += 25
        reasons.append("role is a direct VA/admin function")
    elif _is_operational_support_role(title):
        score += 15
        reasons.append("role is operational support that creates admin burden")
    elif _is_client_facing_role(title):
        score += 10
        reasons.append("role is client-facing and likely creates admin follow-up")
    elif _is_professional_role(title):
        score += 10
        reasons.append(
            "role is a professional service provider role; the firm likely needs admin support"
        )
    elif NON_ADMIN_ROLES_RE.search(title_lower):
        score -= 10
        reasons.append("title appears senior/technical/sales-only, less direct VA fit")

    # 3. Seniority/leadership penalty (direct VA roles are exempt)
    if _is_senior_professional(title):
        score -= 10
        reasons.append("senior/leadership title; the firm may still need admin support")

    # 4. Admin burden in the description
    if ADMIN_BURDEN_RE.search(text):
        score += 10
        reasons.append("description signals high administrative workload")

    # 5. Workplace fit
    wp = (workplace_type or "").lower()
    if wp in {"remote", "hybrid"} or REMOTE_KEYWORDS_RE.search(text):
        score += 10
        reasons.append("role is remote/hybrid (ideal for a VA)")
    if ONSITE_KEYWORDS_RE.search(text):
        score -= 20
        reasons.append("on-site language detected — harder to service remotely")

    # 6. Recency
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

    # 7. Contact route available
    if routes.get("best_email") or routes.get("best_phone") or routes.get("best_form"):
        score += 5
        reasons.append("contact route available")

    score = max(0, min(score, 100))
    rank = "Low"
    if score >= 75:
        rank = "High"
    elif score >= 55:
        rank = "Medium"
    return score, rank, reasons


def _build_explanation(
    company_name: str,
    title: str,
    location: str,
    category: str,
    score: int,
    rank: str,
    routes: dict[str, str],
    reasons: list[str],
    source_key: str = "",
) -> str:
    contact_parts = []
    if routes.get("best_email"):
        contact_parts.append(f"email {routes['best_email']}")
    if routes.get("best_phone"):
        contact_parts.append(f"phone {routes['best_phone']}")
    if routes.get("best_form"):
        contact_parts.append(f"contact form {routes['best_form']}")
    contact = "; ".join(contact_parts) if contact_parts else "no direct contact route yet"
    use_case = VA_USE_CASES.get(category, VA_USE_CASES["Other"])
    top_reasons = (
        "; ".join(reasons[:3]) if reasons else "company and role profile match VA support patterns"
    )
    if source_key == "openstreetmap":
        explanation = (
            f"{rank} fit ({score}/100): {company_name} ({category}) in {location} "
            f"is an OpenStreetMap business listing tagged as '{title}'. {use_case} "
            f"Key signal: {top_reasons}. Best contact: {contact}."
        )
    else:
        explanation = (
            f"{rank} fit ({score}/100): {company_name} ({category}) in {location} is advertising "
            f"'{title}'. {use_case} Key signal: {top_reasons}. Best contact: {contact}."
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
    if any(w.lower() in generic or w.lower() in VA_ROLE_WORDS for w in words):
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


RANK_ORDER = {"low": 1, "medium": 2, "high": 3}


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
    parser.add_argument(
        "--min-rank",
        choices=["low", "medium", "high"],
        default="low",
        help="Only export leads with at least this rank (low = all)",
    )
    args = parser.parse_args()

    workspace_id = args.workspace_id
    leads_path = args.leads_path
    companies_path = args.companies_path
    region_filter = args.region
    min_rank = args.min_rank

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
                            SourceHit.source_key.in_(EXPORT_SOURCES),
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
                    SourceHit.source_key.in_(EXPORT_SOURCES),
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
            score, rank, reasons = _qualification_score(
                company_name,
                title,
                body,
                location,
                hit.published_at,
                best_routes,
                hit.workplace_type,
            )
            explanation = _build_explanation(
                company_name,
                title,
                location,
                category,
                score,
                rank,
                best_routes,
                reasons,
                hit.source_key,
            )

            if RANK_ORDER.get(rank.lower(), 0) < RANK_ORDER.get(min_rank, 1):
                continue

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
