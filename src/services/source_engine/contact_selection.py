"""Select the most useful company and person contact routes for a lead."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TypedDict

from services.source_engine.enricher import (
    email_matches_person,
    extract_contact_form_url,
    extract_email,
    extract_linkedin_profile_url,
    extract_phone,
    is_valid_named_contact,
    parse_named_contact,
)


def select_contact_routes(routes: list[dict[str, str]]) -> dict[str, str]:
    """Return deterministic, syntactically usable company contact routes."""
    candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for r in routes:
        t = r["type"]
        v = r["value"]
        if t in ("named_work_email_approved", "generic_email"):
            email = extract_email(v)
            if email:
                candidates["best_email"].append(
                    (0 if t == "named_work_email_approved" else 1, email)
                )
        elif t == "business_phone":
            phone = extract_phone(v)
            if phone:
                candidates["best_phone"].append((0, phone))
        elif t in ("sales_form", "contact_form", "demo_booking"):
            url = extract_contact_form_url(v)
            if url:
                candidates["best_form"].append((0, url))
    return {
        key: sorted(set(values), key=lambda candidate: (candidate[0], candidate[1].lower()))[0][1]
        for key, values in candidates.items()
    }


def select_company_routes(
    routes: list[dict[str, str]],
    *,
    exclude_email: str = "",
    exclude_phone: str = "",
    exclude_name: str = "",
) -> dict[str, str]:
    """Return generic company routes without borrowing person-associated details."""
    company_routes: list[dict[str, str]] = []
    for route in routes:
        route_type = route["type"]
        if route_type == "generic_email":
            email = extract_email(route["value"])
            if (
                email
                and email != exclude_email
                and not (exclude_name and email_matches_person(exclude_name, email))
            ):
                company_routes.append(route)
        elif route_type == "business_phone" and not _parse_named_route(route["value"]):
            phone = extract_phone(route["value"])
            if phone and phone != exclude_phone:
                company_routes.append(route)
        elif route_type in ("sales_form", "contact_form", "demo_booking"):
            company_routes.append(route)
    return select_contact_routes(company_routes)


_TITLE_BOILERPLATE = re.compile(
    r"\b(Read Bio|Read More|Connect|LinkedIn|Facebook|Instagram|Twitter|TikTok|YouTube)\b",
    re.I,
)


def _clean_title_text(title: str) -> str:
    title = _TITLE_BOILERPLATE.sub("", title)
    title = title.replace("|", " ").replace("  ", " ")
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def _validated_person(name: str, title: str, company_name: str = "") -> tuple[str, str] | None:
    title = _clean_title_text(title)
    if title and (len(title) > 60 or len(title.split()) > 8):
        title = ""
    display = f"{name} ({title})" if title else name
    if not is_valid_named_contact(display, company_name):
        return None
    return name, title


def _parse_named_route(value: str) -> dict[str, str]:
    """Parse a formatted named route such as 'Name (Title) <email>'."""
    parsed = parse_named_contact(value)
    if not parsed:
        return {}
    person = _validated_person(parsed["name"], parsed["title"])
    if not person:
        return {}
    name, title = person
    return {"name": name, "title": title, "value": parsed["value"]}


class _NamedPersonRoutes(TypedDict):
    name: str
    title: str
    emails: set[str]
    phones: set[str]
    linkedins: set[str]


def _name_key(name: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z]+", name.lower()))


def _generic_email_matches_target(target_name: str, email: str) -> bool:
    target = _name_key(target_name)
    if len(target) < 2 or "@" not in email:
        return False
    local = tuple(re.findall(r"[a-z]+", email.split("@", 1)[0].lower()))
    if not local:
        return False
    compact = "".join(local)
    return local in (target, (target[0], target[-1])) or compact in {
        "".join(target),
        target[0] + target[-1],
    }


def _collect_named_people(
    routes: list[dict[str, str]],
    company_name: str = "",
    target_name: str = "",
) -> tuple[dict[str, _NamedPersonRoutes], list[str]]:
    """Parse and group every validated person-associated route."""
    candidates: dict[str, _NamedPersonRoutes] = {}

    def _matches_target(name: str) -> bool:
        if not target_name:
            return True
        candidate = _name_key(name)
        target = _name_key(target_name)
        if not candidate or not target:
            return False
        return candidate == target or (
            len(candidate) >= 2
            and len(target) >= 2
            and (len(candidate) == 2 or len(target) == 2)
            and candidate[0] == target[0]
            and candidate[-1] == target[-1]
        )

    def _upsert(
        name: str,
        title: str = "",
        email: str = "",
        phone: str = "",
        linkedin: str = "",
    ) -> None:
        person = _validated_person(name, title, company_name)
        if not person or not _matches_target(name):
            return
        name, title = person
        key = " ".join(_name_key(name))
        existing = candidates.get(key)
        if not existing:
            existing = {
                "name": name,
                "title": title,
                "emails": set(),
                "phones": set(),
                "linkedins": set(),
            }
            candidates[key] = existing
        elif title and not existing["title"]:
            existing["title"] = title
        if email:
            existing["emails"].add(email)
        if phone:
            existing["phones"].add(phone)
        if linkedin:
            existing["linkedins"].add(linkedin)

    generic_emails: list[str] = []
    for route in sorted(routes, key=lambda item: (item["type"], item["value"].lower())):
        route_type = route["type"]
        value = route["value"]
        if route_type == "named_contact":
            match = re.match(r"^(.*?)\s*(?:\((.*?)\))?\s*$", value.strip())
            if match:
                _upsert(match.group(1).strip(), (match.group(2) or "").strip())
        elif route_type == "generic_email" and target_name:
            email = extract_email(value)
            if email and _generic_email_matches_target(target_name, email):
                generic_emails.append(email)
        elif route_type in (
            "named_work_email_approved",
            "business_phone",
            "social_profile_review_only",
        ):
            parsed = _parse_named_route(value)
            if not parsed:
                continue
            name = parsed["name"]
            title = parsed["title"]
            payload = parsed["value"]
            if route_type == "named_work_email_approved":
                email = extract_email(payload)
                if email and email_matches_person(name, email):
                    _upsert(name, title=title, email=email)
            elif route_type == "business_phone":
                phone = extract_phone(payload)
                if phone:
                    _upsert(name, title=title, phone=phone)
            else:
                url = extract_linkedin_profile_url(payload)
                if url and url.startswith("http"):
                    _upsert(name, title=title, linkedin=url)
    return candidates, generic_emails


def list_named_contact_routes(
    routes: list[dict[str, str]], company_name: str = ""
) -> list[dict[str, str]]:
    """Return every validated person-linked email, phone, and LinkedIn route."""
    candidates, _ = _collect_named_people(routes, company_name)
    results: list[dict[str, str]] = []
    for candidate in sorted(
        candidates.values(), key=lambda item: (item["name"].lower(), item["title"].lower())
    ):
        for contact_type, values in (
            ("email", candidate["emails"]),
            ("phone", candidate["phones"]),
            ("linkedin", candidate["linkedins"]),
        ):
            for value in sorted(values, key=str.lower):
                results.append(
                    {
                        "name": candidate["name"],
                        "title": candidate["title"],
                        "contact_type": contact_type,
                        "contact_value": value,
                    }
                )
    return results


def select_named_person(
    routes: list[dict[str, str]],
    company_name: str = "",
    target_name: str = "",
    target_title: str = "",
) -> dict[str, str]:
    """Return the best named contact with an explicitly associated email/phone/LinkedIn.

    Generic company emails and phones are not paired with named people, except
    that a generic email may be used when its local part matches target_name.
    When target_name is supplied, only routes naming or matching that person
    are considered; middle names may differ but first and last names must match.
    named_contact_email is only populated when a named_work_email_approved
    or social_profile route explicitly carries that person's name and the
    email local part or LinkedIn URL plausibly matches the person's name.
    A business_phone display route is person-specific only when it explicitly
    carries the person's name.
    """
    candidates, generic_emails = _collect_named_people(routes, company_name, target_name)
    matching = list(candidates.values())
    if target_name and matching:
        target_key = _name_key(target_name)
        exact = [candidate for candidate in matching if _name_key(candidate["name"]) == target_key]
        if exact:
            matching = exact
        elif len(matching) > 1:
            return {}
    if not matching and target_name and generic_emails:
        person = _validated_person(target_name, "", company_name)
        if person:
            name, title = person
            matching = [
                {
                    "name": name,
                    "title": title,
                    "emails": {generic_emails[0]},
                    "phones": set(),
                    "linkedins": set(),
                }
            ]
    elif len(matching) == 1 and generic_emails and not matching[0]["emails"]:
        matching[0]["emails"].add(generic_emails[0])

    if not matching:
        return {}

    def _role_score(contact_title: str) -> int:
        lead = target_title.lower()
        role = contact_title.lower()
        priorities: tuple[str, ...]
        if "property" in lead or "real estate" in lead:
            priorities = (
                "property manager",
                "property management",
                "operations manager",
                "office manager",
                "principal",
                "director",
                "owner",
            )
        elif "law" in lead or "legal" in lead:
            priorities = (
                "practice manager",
                "operations manager",
                "office manager",
                "partner",
                "principal",
                "lawyer",
                "solicitor",
                "director",
            )
        elif "account" in lead:
            priorities = (
                "practice manager",
                "operations manager",
                "office manager",
                "partner",
                "principal",
                "accountant",
                "director",
            )
        elif any(word in lead for word in ("insurance", "financial", "finance")):
            priorities = (
                "operations manager",
                "practice manager",
                "office manager",
                "broker",
                "financial planner",
                "adviser",
                "advisor",
                "principal",
                "director",
            )
        elif any(
            word in lead
            for word in (
                "maintenance",
                "electric",
                "plumb",
                "roof",
                "carpent",
                "hvac",
                "paint",
                "build",
            )
        ):
            priorities = (
                "operations manager",
                "service manager",
                "office manager",
                "maintenance coordinator",
                "administrator",
                "owner",
                "director",
            )
        else:
            priorities = (
                "operations manager",
                "practice manager",
                "office manager",
                "administration manager",
                "administrator",
                "principal",
                "director",
                "owner",
                "partner",
            )
        return next(
            (len(priorities) - index for index, phrase in enumerate(priorities) if phrase in role),
            0,
        )

    def _score(c: _NamedPersonRoutes) -> tuple[bool, int, int]:
        contactability = bool(c["emails"]) * 3 + bool(c["phones"]) * 2 + bool(c["linkedins"])
        return bool(contactability), contactability, _role_score(c["title"])

    best = max(
        matching,
        key=lambda c: (_score(c), c["name"]),
    )
    return {
        "name": best["name"],
        "title": best["title"],
        "email": sorted(best["emails"], key=str.lower)[0] if best["emails"] else "",
        "phone": sorted(best["phones"], key=str.lower)[0] if best["phones"] else "",
        "linkedin": sorted(best["linkedins"], key=str.lower)[0] if best["linkedins"] else "",
    }


def select_lead_person(
    title: str,
    hit_routes: list[dict[str, str]],
    company_routes: list[dict[str, str]],
    company_name: str,
) -> dict[str, str]:
    """Select the person intended by one lead without using another employee."""
    target = select_named_person(hit_routes, company_name).get("name", "")
    has_named_title = " — " in title
    if not target and has_named_title:
        candidate = title.split(" — ", 1)[0].strip()
        if not is_valid_named_contact(candidate, company_name):
            return {}
        target = candidate
    return select_named_person(
        hit_routes + company_routes,
        company_name,
        target_name=target,
        target_title=title,
    )


__all__ = [
    "list_named_contact_routes",
    "select_company_routes",
    "select_contact_routes",
    "select_lead_person",
    "select_named_person",
]
