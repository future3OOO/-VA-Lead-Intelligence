#!/usr/bin/env python3
"""Export qualified small-business leads with explanation and ranking."""

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
    "breezy_jobs",
    "greenhouse_jobs",
    "lever_jobs",
    "ashby_jobs",
    "smartrecruiters_postings",
}

CATEGORY_PATTERNS = [
    (
        "Property/Facilities",
        r"\bproperty\b|\bapartment\b|\bmultifamily\b|\bresidential\b|\bleasing\b|\blandlord\b|\bhoa\b|\bhomeowner\b|\bhousing\b|\bfacilit|\bmaintenance\b|\bcommunity\b|\bcondo\b|\bproperty management\b",
    ),
    (
        "Real Estate",
        r"\breal estate\b|\brealty\b|\bbrokerage\b|\bbroker\b|\binvestment property\b|\basset manager\b|\bportfolio\b|\bcommercial real estate\b",
    ),
    (
        "Financial Services",
        r"\bmortgage\b|\bloan\b|\bfinancial\b|\bwealth\b|\binsurance\b|\badvisor\b|\badviser\b|\bbookkeep\b|\baccounting\b|\bcpa\b|\bcredit\b|\blender\b|\bfiscal\b",
    ),
    (
        "Home Services/Construction",
        r"\bplumbing\b|\bhvac\b|\broofing\b|\belectrician\b|\bhandyman\b|\bhome service\b|\bconstruction\b|\brenovation\b|\bremodel\b|\bpainting\b|\bchimney\b|\bfire protection\b|\bplumber\b|\belectrical\b|\bsprinkler\b|\bbath\b|\bhomes?\b|\bhardware\b",
    ),
    ("Legal/Professional", r"\blaw\b|\blegal\b|\battorney\b|\bllp\b|\baccounting\b|\bcpa\b"),
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
    "farmer",  # too broad? keep only if combined with insurance and not target
]

STRONG_ADMIN_TITLES = [
    "virtual assistant",
    "administrative assistant",
    "executive assistant",
    "office manager",
    "bookkeeper",
    "property manager",
    "assistant property manager",
    "transaction coordinator",
    "operations coordinator",
    "maintenance coordinator",
    "project coordinator",
    "customer service",
    "dispatcher",
    "scheduling coordinator",
    "appointment setter",
    "sales support",
    "crm administrator",
]

MEDIUM_ADMIN_TITLES = [
    "coordinator",
    "assistant",
    "admin",
    "manager",
    "support",
    "specialist",
    "representative",
    "analyst",
    "associate",
    "supervisor",
]


def _detect_category(text: str) -> str:
    text = f" {text.lower()} "
    for cat, pat in CATEGORY_PATTERNS:
        if re.search(pat, text):
            return cat
    return "Other"


def _is_target(text: str) -> bool:
    text_lower = text.lower()
    for term in STAFFING_DENY:
        if term in text_lower:
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
    if any(t in title_lower for t in STRONG_ADMIN_TITLES):
        score += 30
        reasons.append("title is a strong VA-adjacent role")
    elif any(t in title_lower for t in MEDIUM_ADMIN_TITLES):
        score += 15
        reasons.append("title shows admin/coordination responsibilities")

    category = _detect_category(text)
    if category != "Other":
        score += 10
        reasons.append(f"company/role in {category} sector")

    if "remote" in text or "hybrid" in text or "work from home" in text:
        score += 10
        reasons.append("role is remote/hybrid (well suited to a VA)")

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
        if t == "generic_email" and "best_email" not in result:
            result["best_email"] = v
        elif t == "business_phone" and "best_phone" not in result:
            result["best_phone"] = v
        elif t == "sales_form" and "best_form" not in result:
            result["best_form"] = v
    return result


async def main() -> None:
    workspace_id = UUID("f72ae1f9-f45e-45dc-a0d9-1a9e5e0b2a24")
    leads_path = "/tmp/small_business_leads_with_contacts.csv"
    companies_path = "/tmp/all_companies.csv"

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
                ]
            )
            for c in company_rows:
                company_routes = contact_by_company.get(c.id, [])
                best = _best_contact(company_routes)
                target = _is_target(f"{c.canonical_name} {c.primary_domain or ''}")
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
            text = f"{title} {company_name} {body} {location}"
            if not _is_target(text):
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

            lead_rows.append(
                {
                    "company_name": company_name,
                    "primary_domain": domain,
                    "job_title": title,
                    "location": location,
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
                }
            )

        lead_rows.sort(key=lambda x: (-x["qualification_score"], x["company_name"].lower()))

        with open(leads_path, "w", newline="", encoding="utf-8") as f:
            leads_writer = csv.DictWriter(
                f,
                fieldnames=[
                    "company_name",
                    "primary_domain",
                    "job_title",
                    "location",
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
