#!/usr/bin/env python3
"""Manual backfill of primary_domain and contact routes for target companies."""

import asyncio
from uuid import UUID

from sqlalchemy import select

from db.models.company import Company
from db.models.contact_route import ContactRoute
from db.session import AsyncSessionLocal


def _normalize_phone(value: str) -> str:
    return value.replace(" ", "")[:255]


def _normalize_email(value: str) -> str:
    return value.strip().lower()[:255]


def _normalize_url(value: str) -> str:
    return value.strip()[:255]


BACKFILLS: dict[str, dict[str, list[str] | str]] = {
    "F&F Properties": {
        "domain": "fandfinc.com",
        "emails": ["Leasing@fandfinc.com"],
        "phones": ["(619) 501-3222"],
        "forms": ["https://www.fandfinc.com/contact"],
    },
    "Cove Living Pte Ltd": {
        "domain": "cove.sg",
        "emails": ["sophie@cove.sg"],
        "phones": ["+65 8740 7138"],
        "forms": ["https://cove.sg/contact"],
    },
    "Pleasant Valley Corporation": {
        "domain": "pleasantvalleycorporation.com",
        "emails": [],
        "phones": ["330-239-0176"],
        "forms": ["https://www.pleasantvalleycorporation.com/contact-us/"],
    },
    "Greenline Apartment Management": {
        "domain": "greenlinemanagement.com",
        "emails": [],
        "phones": [],
        "forms": ["https://www.greenlinemanagement.com/contact-us"],
    },
    "AMS Solutions": {
        "domain": "ams-solutions.com",
        "emails": ["info@ams-solutions.com"],
        "phones": ["(866) 973-2221", "(214) 522-0474"],
        "forms": ["https://ams-solutions.com/contact/"],
    },
    "National Horizon Real Estate Services / Blue Summit": {
        "domain": "nh-res.com",
        "emails": ["info@nh-res.com"],
        "phones": ["(888) 973-3460"],
        "forms": ["https://nh-res.com/"],
    },
    "Elevate Commercial": {
        "domain": "elevatesmg.com",
        "emails": ["investors@elevate-commercial.com"],
        "phones": ["619-378-0196"],
        "forms": ["https://www.elevatesmg.com/contact"],
    },
    "R3 Roofing & Exteriors | R3 Heating & Air": {
        "domain": "r3roofs.com",
        "emails": [],
        "phones": ["(949) 595-5990", "563-888-1017"],
        "forms": ["https://r3roofs.com/contact-us/"],
    },
    "Radiant Plumbing and Air Conditioning": {
        "domain": "radiantplumbing.com",
        "emails": [],
        "phones": ["512-265-6994", "210-294-6703"],
        "forms": ["https://radiantplumbing.com/contact-us/"],
    },
    "Budget Right Handyman": {
        "domain": "getbrh.com",
        "emails": ["office@brh.io"],
        "phones": ["877-507-2126"],
        "forms": ["https://www.getbrh.com/estimate"],
    },
    "John Byrne Painting": {
        "domain": "johnbyrnepainting.com",
        "emails": [],
        "phones": ["610-337-3711", "609-391-7788"],
        "forms": ["https://www.johnbyrnepainting.com/contact-us/"],
    },
    "Workman LLP": {
        "domain": "workman.co.uk",
        "emails": ["info@workman.co.uk"],
        "phones": ["+44 (0) 20 7227 6200"],
        "forms": ["https://workman.co.uk/contact/"],
    },
    "Goodsmith": {
        "domain": "ggulaw.com",
        "emails": [],
        "phones": ["312-322-1981"],
        "forms": ["https://ggulaw.com/contact"],
    },
    "GoodSmith & Co. | Investment Banking & Corporate Finance": {
        "domain": "ggulaw.com",
        "emails": [],
        "phones": ["312-322-1981"],
        "forms": ["https://ggulaw.com/contact"],
    },
    "TruBlue Total House Care": {
        "domain": "trubluehousecare.com",
        "emails": ["info@trubluehousecare.com"],
        "phones": ["513-999-9926"],
        "forms": ["https://trubluehousecare.com/"],
    },
    "Meron Financial Agency": {
        "domain": "meronandkemboifinancialagency.com",
        "emails": [],
        "phones": ["832-251-7280"],
        "forms": ["https://meronandkemboifinancialagency.com/join-team"],
    },
    "Glenholme Healthcare Ltd": {
        "domain": "glenholme.org.uk",
        "emails": [],
        "phones": [],
        "forms": ["https://www.glenholme.org.uk/contact-us/"],
    },
    "Q-Block Computing": {
        "domain": "q-block.ca",
        "emails": ["qtask@q-block.ca"],
        "phones": [],
        "forms": ["https://www.q-block.ca/contact"],
    },
    "RGroup Realty": {
        "domain": "rgroupaz.com",
        "emails": [],
        "phones": ["520-618-7331"],
        "forms": ["https://rgroupaz.com/contact"],
    },
    "MINK Life & Legacy Agency": {
        "domain": "minklifelegacy.com",
        "emails": [],
        "phones": [],
        "forms": ["https://minklifelegacy.com/home-page-page"],
    },
    "Guardian Fire Services": {
        "domain": "overheadfire.com",
        "emails": ["main@overheadfire.com"],
        "phones": ["775-856-3444"],
        "forms": ["https://overheadfire.com/contact-us/"],
    },
    "Unified Commercial Property Management": {
        "domain": "unifiedcpm.com",
        "emails": [],
        "phones": ["480-398-2222"],
        "forms": ["https://www.unifiedcpm.com/"],
    },
    "Ace Handyman Services Albuquerque": {
        "domain": "acehandymanservices.com",
        "emails": ["andy.bell@acehandymanservices.com"],
        "phones": ["(866) 349-6946"],
        "forms": [],
    },
    "Apex Mechanical, a division of Farbman Group,": {
        "domain": "apex-ms.com",
        "emails": [],
        "phones": ["888-530-2739"],
        "forms": ["https://apex-ms.com/"],
    },
    "Bridge33 Capital": {
        "domain": "bridge33capital.com",
        "emails": ["leasing@bridge33capital.com"],
        "phones": ["206-538-0083", "206-690-6553"],
        "forms": ["https://bridge33capital.com/contact"],
    },
    "C1 Insurance Group": {
        "domain": "c1ig.com",
        "emails": ["info@c1ig.com"],
        "phones": ["214-420-0888"],
        "forms": ["https://c1ig.com/contact/dallas-tx-insurance/"],
    },
    "C1 Insurance Group - Dallas, TX": {
        "domain": "c1ig.com",
        "emails": ["info@c1ig.com"],
        "phones": ["214-420-0888"],
        "forms": ["https://c1ig.com/contact/dallas-tx-insurance/"],
    },
}


def _routes_for(config: dict[str, list[str] | str]) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    for email in config.get("emails", []):
        routes.append({"type": "generic_email", "value": _normalize_email(str(email))})
    for phone in config.get("phones", []):
        routes.append({"type": "business_phone", "value": _normalize_phone(str(phone))})
    for form in config.get("forms", []):
        routes.append({"type": "sales_form", "value": _normalize_url(str(form))})
    return routes


async def main() -> None:
    workspace_id = UUID("f72ae1f9-f45e-45dc-a0d9-1a9e5e0b2a24")
    async with AsyncSessionLocal() as session:
        for canonical_name, config in BACKFILLS.items():
            company = (
                await session.execute(
                    select(Company).where(
                        Company.workspace_id == workspace_id,
                        Company.canonical_name == canonical_name,
                    )
                )
            ).scalar_one_or_none()
            if not company:
                print(f"NOT FOUND: {canonical_name}")
                continue
            domain = str(config.get("domain", "")).strip()
            if domain and not company.primary_domain:
                company.primary_domain = domain
                print(f"DOMAIN {canonical_name} -> {domain}")

            existing = {
                (r.route_type, r.value.lower())
                for r in (
                    await session.scalars(
                        select(ContactRoute).where(
                            ContactRoute.workspace_id == workspace_id,
                            ContactRoute.company_id == company.id,
                        )
                    )
                ).all()
            }
            for route in _routes_for(config):
                if not route["value"]:
                    continue
                key = (route["type"], route["value"].lower())
                if key in existing:
                    continue
                session.add(
                    ContactRoute(
                        workspace_id=workspace_id,
                        company_id=company.id,
                        route_type=route["type"],
                        value=route["value"],
                        is_verified=False,
                    )
                )
                existing.add(key)
                print(f"ROUTE {canonical_name}: {route['type']}={route['value']}")
        await session.commit()


if __name__ == "__main__":
    import sys

    sys.path.insert(0, "src")
    asyncio.run(main())
