#!/usr/bin/env python3
"""Export qualified small-business leads with explanation and ranking."""

import argparse
import asyncio
import csv
import re
import shutil
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import func, select

from db.models.company import Company
from db.models.contact_route import ContactRoute
from db.models.source_hit import SourceHit
from db.session import AsyncSessionLocal
from services.source_engine.contact_selection import list_named_contacts
from services.source_engine.contact_selection import select_company_routes as _best_company_contact
from services.source_engine.contact_selection import select_contact_routes as _best_contact
from services.source_engine.contact_selection import select_lead_person as _lead_named_contact
from services.source_engine.contact_selection import select_named_person as _best_named_contact
from services.source_engine.enricher import extract_phone

EXPORT_SOURCES = {
    "openstreetmap",
    "finance_directory",
    "nz_finance_advisers",
}

LEAD_FIELDS = [
    "lead_id",
    "company_id",
    "primary_contact_id",
    "company_name",
    "primary_domain",
    "primary_contact_name",
    "primary_contact_title",
    "primary_contact_email",
    "primary_contact_phone",
    "primary_contact_linkedin",
    "company_email",
    "company_phone",
    "company_form",
    "best_email",
    "best_phone",
    "best_form",
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
]

PRIMARY_CONTACT_FIELDS = [
    "lead_id",
    "company_id",
    "primary_contact_id",
    "company_name",
    "primary_domain",
    "job_title",
    "primary_contact_status",
    "primary_contact_name",
    "primary_contact_title",
    "primary_contact_email",
    "primary_contact_phone",
    "primary_contact_linkedin",
    "source",
    "source_url",
]

CONTACT_FIELDS = [
    "contact_id",
    "company_id",
    "company_name",
    "primary_domain",
    "contact_name",
    "contact_title",
    "contact_emails",
    "contact_phones",
    "contact_linkedin_urls",
]

COMPANY_FIELDS = [
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
    "named_contact_phone",
    "named_contact_linkedin",
]

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


def _csv_safe(value: object, *, phone_number: bool = False) -> object:
    """Keep externally sourced text inert when a CSV is opened in a spreadsheet."""
    if isinstance(value, str):
        value = " ".join(value.split())
        if phone_number and value.startswith("+"):
            phones = [part.strip() for part in value.split(";")]
            if all(extract_phone(phone) == phone for phone in phones):
                return value
        if value.startswith(("=", "+", "-", "@")):
            return f"'{value}"
    return value


def _csv_value(field: str, value: object) -> object:
    value = "; ".join(sorted(value, key=str.lower)) if isinstance(value, set) else value
    return _csv_safe(value, phone_number=field.endswith(("phone", "phones")))


def _contact_id(company_id: UUID, person_key: str) -> UUID:
    return uuid5(UUID("02779786-bdba-4c41-9c01-b1a0fa0685d2"), f"{company_id}:{person_key}")


def _merge_contact_record(
    records: dict[tuple[UUID, str], dict[str, Any]],
    company: Company,
    contact: Mapping[str, Any],
) -> None:
    person_key = contact["key"]
    record = records.setdefault(
        (company.id, person_key),
        {
            "contact_id": _contact_id(company.id, person_key),
            "company_id": company.id,
            "company_name": company.canonical_name,
            "primary_domain": company.primary_domain or "",
            "contact_name": contact["name"],
            "contact_title": contact["title"],
            "contact_emails": set(),
            "contact_phones": set(),
            "contact_linkedin_urls": set(),
        },
    )
    if not record["contact_title"] and contact["title"]:
        record["contact_title"] = contact["title"]
    # Person-list projections use plural tuples; selected-lead projections use singular values.
    for field, plural, singular in (
        ("contact_emails", "emails", "email"),
        ("contact_phones", "phones", "phone"),
        ("contact_linkedin_urls", "linkedins", "linkedin"),
    ):
        values = contact.get(plural, (contact.get(singular, ""),))
        record[field].update(value for value in values if value)


def _is_remote_friendly(title: str, body: str, location: str, workplace_type: str = "") -> bool:
    """Return whether the opportunity can reasonably be served remotely."""
    wp = (workplace_type or "").lower()
    if wp in {"remote", "hybrid", "inferred_remote_friendly"}:
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
    # Target-sector companies are leads even when the open role is senior or a
    # trade title, because the firm itself likely needs VA support.
    if category != "Other":
        return True
    # Non-target companies only make the cut if the role is clearly admin.
    return _is_direct_va_role(text) or _is_operational_support_role(text)


def _qualification_score(
    company_name: str,
    title: str,
    body: str,
    location: str,
    published_at: datetime,
    routes: dict[str, str],
    workplace_type: str = "",
    intent_label: str = "",
) -> tuple[int, str, list[str], str]:
    text = f"{title} {body} {company_name} {location}".lower()
    title_lower = title.lower()
    category = _detect_category(text)
    score = 0
    reasons: list[str] = []
    is_listing = intent_label == "company_existence_only"

    # 0. Technology/software vendor check.  Vendors sell tools to target
    # businesses but are rarely the end-user service business that needs a VA.
    is_tech_vendor = bool(TECH_VENDOR_RE.search(f"{company_name} {body}".lower()))

    # 1. Sector fit (company-level signal)
    if is_tech_vendor:
        category = "Other"
        score -= 25
        reasons.append("company appears to be a technology/software vendor, not a service business")
    elif category != "Other":
        score += 40 if is_listing else 30
        reasons.append(f"company is in the {category} sector")
    elif not is_listing and _is_direct_va_role(title):
        score += 5
        reasons.append("role is a direct admin/VA role")

    if is_listing:
        if category != "Other":
            score += 25
            reasons.append("sector commonly carries delegable administrative workload")
        if workplace_type == "inferred_remote_friendly":
            score += 5
            reasons.append("listed business can be approached for remote administrative support")
    else:
        # 2. Observed role signal.
        if _is_direct_va_role(text):
            score += 25
            reasons.append("role is a direct VA/admin function")
        elif _is_operational_support_role(text):
            score += 15
            reasons.append("role is operational support that creates admin burden")
        elif _is_client_facing_role(text):
            score += 10
            reasons.append("role is client-facing and likely creates admin follow-up")
        elif _is_professional_role(text):
            score += 10
            reasons.append(
                "role is a professional service provider role; the firm likely needs admin support"
            )
        elif NON_ADMIN_ROLES_RE.search(title_lower):
            score -= 10
            reasons.append("title appears senior/technical/sales-only, less direct VA fit")

        if _is_senior_professional(title):
            score -= 10
            reasons.append("senior/leadership title; the firm may still need admin support")
        if ADMIN_BURDEN_RE.search(text):
            score += 10
            reasons.append("description signals high administrative workload")

        wp = (workplace_type or "").lower()
        if wp in {"remote", "hybrid"} or REMOTE_KEYWORDS_RE.search(text):
            score += 10
            reasons.append("role is remote/hybrid (ideal for a VA)")
        if ONSITE_KEYWORDS_RE.search(text):
            score -= 20
            reasons.append("on-site language detected — harder to service remotely")

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

    has_contact = bool(
        routes.get("best_email") or routes.get("best_phone") or routes.get("best_form")
    )
    score = max(0, min(score, 100))
    rank = "Low"
    if score >= 75 and has_contact:
        rank = "High"
    elif score >= 55:
        rank = "Medium"
        if score >= 75 and not has_contact:
            reasons.append("contact route missing; rank capped at Medium")
    return score, rank, reasons, category


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
    intent_label: str = "",
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
    if intent_label == "company_existence_only":
        explanation = (
            f"{rank} fit ({score}/100): {company_name} ({category}) in {location} "
            f"is a public business listing from {source_key} tagged as '{title}'. {use_case} "
            f"Key signal: {top_reasons}. Best contact: {contact}."
        )
    else:
        explanation = (
            f"{rank} fit ({score}/100): {company_name} ({category}) in {location} is advertising "
            f"'{title}'. {use_case} Key signal: {top_reasons}. Best contact: {contact}."
        )
    return explanation


RANK_ORDER = {"low": 1, "medium": 2, "high": 3}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Export qualified leads and company contacts")
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--leads-path", default="/tmp/small_business_leads_with_contacts.csv")
    parser.add_argument("--companies-path", default="/tmp/all_companies.csv")
    parser.add_argument("--primary-contacts-path", default="")
    parser.add_argument("--contacts-path", default="")
    parser.add_argument(
        "--leads-alias-path",
        default="",
        help="Optional byte-identical copy of the complete lead export",
    )
    parser.add_argument(
        "--companies-alias-path",
        default="",
        help="Optional byte-identical copy of the complete company export",
    )
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
    primary_contacts_path = args.primary_contacts_path
    contacts_path = args.contacts_path
    leads_alias_path = args.leads_alias_path
    companies_alias_path = args.companies_alias_path
    region_filter = args.region
    min_rank = args.min_rank

    async with AsyncSessionLocal() as session:
        # Load all contact routes keyed by company_id
        contact_rows = (
            await session.scalars(
                select(ContactRoute)
                .where(ContactRoute.workspace_id == workspace_id)
                .order_by(
                    ContactRoute.company_id,
                    ContactRoute.route_type,
                    ContactRoute.value,
                    ContactRoute.id,
                )
            )
        ).all()
        contact_by_company: dict[UUID, list[dict[str, str]]] = defaultdict(list)
        for cr in contact_rows:
            contact_by_company[cr.company_id].append({"type": cr.route_type, "value": cr.value})

        # Load companies
        company_rows = (
            await session.scalars(
                select(Company)
                .where(Company.workspace_id == workspace_id)
                .order_by(func.lower(Company.canonical_name), Company.id)
            )
        ).all()
        companies_by_id = {c.id: c for c in company_rows}

        source_hits = (
            await session.scalars(
                select(SourceHit)
                .where(SourceHit.workspace_id == workspace_id)
                .order_by(SourceHit.id)
            )
        ).all()

        contacts_by_key: dict[tuple[UUID, str], dict[str, Any]] = {}
        for contact_company in company_rows:
            for contact in list_named_contacts(
                contact_by_company.get(contact_company.id, []),
                contact_company.canonical_name,
            ):
                _merge_contact_record(contacts_by_key, contact_company, contact)

        # Write all companies
        with open(companies_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\r\n")
            writer.writerow(COMPANY_FIELDS)
            for c in company_rows:
                company_routes = contact_by_company.get(c.id, [])
                best = _best_contact(company_routes)
                named = _best_named_contact(company_routes, c.canonical_name)
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
                values = [
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
                    named.get("phone", ""),
                    named.get("linkedin", ""),
                ]
                writer.writerow(
                    [
                        _csv_safe(value, phone_number=field.endswith("phone"))
                        for field, value in zip(COMPANY_FIELDS, values, strict=True)
                    ]
                )

        # Build leads. Each (company, title) is deduplicated to the strongest
        # scoring hit and franchises are capped per company record (domain) so
        # distinct branches keep their own contacts.
        lead_candidates: dict[tuple[Any, str], dict[str, Any]] = {}
        for hit in source_hits:
            company = companies_by_id.get(hit.company_id) if hit.company_id else None
            hit_routes = [
                {"type": str(route.get("type", "")), "value": str(route.get("value", ""))}
                for route in (hit.contact_routes_raw or [])
                if isinstance(route, dict) and route.get("type") and route.get("value")
            ]
            if company:
                for contact in list_named_contacts(hit_routes, company.canonical_name):
                    _merge_contact_record(contacts_by_key, company, contact)
            if hit.source_key not in EXPORT_SOURCES:
                continue
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

            domain = (
                (company.primary_domain or hit.company_domain_raw or "")
                if company
                else (hit.company_domain_raw or "")
            )
            company_routes = contact_by_company.get(company.id, []) if company else []
            named = _lead_named_contact(
                title,
                hit_routes,
                company_routes,
                company.canonical_name if company else company_name,
            )
            company_contacts = _best_company_contact(
                company_routes,
                exclude_email=named.get("email", ""),
                exclude_phone=named.get("phone", ""),
                exclude_name=named.get("name", ""),
            )
            best_routes = dict(company_contacts)
            if named.get("email"):
                best_routes["best_email"] = named["email"]
            if named.get("phone"):
                best_routes["best_phone"] = named["phone"]
            score, rank, reasons, category = _qualification_score(
                company_name,
                title,
                body,
                location,
                hit.published_at,
                best_routes,
                hit.workplace_type,
                hit.intent_label,
            )

            if RANK_ORDER.get(rank.lower(), 0) < RANK_ORDER.get(min_rank, 1):
                continue

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
                hit.intent_label,
            )
            company_key = company.id if company else (domain or company_name)
            title_key = title.lower().strip()
            primary_contact_id: UUID | str = ""
            person_key = named.get("key", "")
            if company and person_key:
                primary_contact_id = _contact_id(company.id, person_key)
                _merge_contact_record(contacts_by_key, company, named)
            existing = lead_candidates.get((company_key, title_key))
            tie_key = (
                hit.published_at.isoformat() if hit.published_at else "",
                hit.source_url,
                str(hit.id),
            )
            if existing and (
                existing["qualification_score"],
                existing["__tie_key"],
            ) >= (score, tie_key):
                continue

            lead_candidates[(company_key, title_key)] = {
                "lead_id": hit.id,
                "company_id": company.id if company else "",
                "primary_contact_id": primary_contact_id,
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
                "primary_contact_name": named.get("name", ""),
                "primary_contact_title": named.get("title", ""),
                "primary_contact_email": named.get("email", ""),
                "primary_contact_phone": named.get("phone", ""),
                "primary_contact_linkedin": named.get("linkedin", ""),
                "company_email": company_contacts.get("best_email", ""),
                "company_phone": company_contacts.get("best_phone", ""),
                "company_form": company_contacts.get("best_form", ""),
                "__company_key": company_key,
                "__tie_key": tie_key,
            }

        lead_rows = sorted(
            lead_candidates.values(),
            key=lambda x: (
                -x["qualification_score"],
                x["company_name"].lower(),
                x["job_title"].lower(),
                x["source_url"],
            ),
        )

        # Cap each company record at the strongest 18 leads so distinct franchise
        # branches are preserved instead of folding by canonical name.
        per_company_count: dict[Any, int] = defaultdict(int)
        capped_rows: list[dict[str, Any]] = []
        for row in lead_rows:
            company_key = row.pop("__company_key")
            row.pop("__tie_key")
            if per_company_count[company_key] >= 18:
                continue
            per_company_count[company_key] += 1
            capped_rows.append(row)
        lead_rows = capped_rows

        with open(leads_path, "w", newline="", encoding="utf-8") as f:
            leads_writer = csv.DictWriter(
                f,
                lineterminator="\r\n",
                fieldnames=LEAD_FIELDS,
            )
            leads_writer.writeheader()
            leads_writer.writerows(
                {key: _csv_value(key, value) for key, value in row.items()} for row in lead_rows
            )

        if primary_contacts_path:
            with open(primary_contacts_path, "w", newline="", encoding="utf-8") as f:
                primary_writer = csv.DictWriter(
                    f,
                    fieldnames=PRIMARY_CONTACT_FIELDS,
                    lineterminator="\r\n",
                )
                primary_writer.writeheader()
                primary_writer.writerows(
                    {
                        field: _csv_value(
                            field,
                            ("available" if row["primary_contact_id"] else "unavailable")
                            if field == "primary_contact_status"
                            else row[field],
                        )
                        for field in PRIMARY_CONTACT_FIELDS
                    }
                    for row in lead_rows
                )
            print(f"Exported {len(lead_rows)} primary contacts to {primary_contacts_path}")

        if contacts_path:
            contact_records = sorted(
                contacts_by_key.values(),
                key=lambda row: (
                    str(row["company_name"]).lower(),
                    str(row["company_id"]),
                    str(row["contact_name"]).lower(),
                    str(row["contact_title"]).lower(),
                ),
            )
            with open(contacts_path, "w", newline="", encoding="utf-8") as f:
                contacts_writer = csv.DictWriter(
                    f,
                    fieldnames=CONTACT_FIELDS,
                    lineterminator="\r\n",
                )
                contacts_writer.writeheader()
                contacts_writer.writerows(
                    {field: _csv_value(field, row[field]) for field in CONTACT_FIELDS}
                    for row in contact_records
                )
            print(f"Exported {len(contact_records)} contacts to {contacts_path}")

        for source_path, alias_path in (
            (leads_path, leads_alias_path),
            (companies_path, companies_alias_path),
        ):
            if alias_path and Path(source_path).resolve() != Path(alias_path).resolve():
                shutil.copyfile(source_path, alias_path)

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
