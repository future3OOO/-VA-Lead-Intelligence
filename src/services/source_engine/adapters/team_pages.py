"""Bounded team-page extractor for named contacts and social profiles."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup

from services.source_engine.adapters.base import BaseSourceAdapter
from services.source_engine.config import SourceConfig
from services.source_engine.enricher import (
    _name_in_email_local,
    extract_contact_form_url,
    extract_email,
    extract_linkedin_profile_url,
    extract_phone,
    is_valid_named_contact,
)

_TITLE_KEYWORDS = [
    "CEO",
    "Founder",
    "Co-Founder",
    "Co-founder",
    "President",
    "COO",
    "CFO",
    "CTO",
    "CMO",
    "VP",
    "Vice President",
    "Vice-President",
    "Director",
    "Manager",
    "Partner",
    "Principal",
    "Associate",
    "Advisor",
    "Adviser",
    "Broker",
    "Agent",
    "Property Manager",
    "Asset Manager",
    "Leasing",
    "Finance",
    "Accounting",
    "Operations",
    "Maintenance",
    "Supervisor",
    "Estimator",
    "Chairman",
    "Chairwoman",
    "Chairperson",
    "Directors",
    "Managing",
    "Executive",
    "Senior",
    "Junior",
    "Officer",
    "Head",
    "Lead",
    "Member",
    "Trustee",
    "Representative",
    "Analyst",
    "Administrator",
    "Coordinator",
    "Assistant",
    "Secretary",
    "Receptionist",
    "Controller",
    "Planner",
    "Strategist",
    "Specialist",
    "Consultant",
    "Advisor",
    "Adviser",
    "General Counsel",
    "Attorney",
    "CPA",
    "Accountant",
    "Bookkeeper",
    "Recruiter",
    "Recruitment",
    "Hiring",
    "Human Resources",
    "HR",
    "Talent",
    "Office Manager",
    "Executive Assistant",
    "Administrative",
]


_TITLE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t).lower() for t in _TITLE_KEYWORDS) + r")\b",
    re.I,
)

_NAME_RE = re.compile(r"\b([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)+)\b")

_NAV_WORDS = {
    "company",
    "about",
    "team",
    "our",
    "join",
    "how",
    "it",
    "works",
    "faq",
    "stories",
    "founders",
    "sitemap",
    "menu",
    "navigation",
    "use",
    "website",
    "page",
    "read",
    "connect",
    "the",
    "and",
    "with",
    "for",
    "from",
    "home",
    "opening",
    "hours",
    "privacy",
    "policy",
    "stamp",
    "duty",
    "calculator",
    "final",
    "thoughts",
    "rental",
    "appraisal",
    "open",
    "homes",
    "buyer",
    "enquiry",
    "enquiries",
    "what",
    "we",
    "do",
}

_PERSON_CARD_RE = re.compile(
    r"(?:team|staff|employee|person|profile|agent|member|people|leadership)", re.I
)

_TEAM_PAGE_PATHS = [
    "/team",
    "/about/team",
    "/about/people",
    "/about-us",
    "/about",
    "/leadership",
    "/leadership-team",
    "/people",
    "/our-team",
    "/our-people",
    "/meet-the-team",
    "/team-members",
    "/executive-team",
    "/executives",
    "/management",
    "/directors",
    "/board",
    "/staff",
    "/our-staff",
    "/who-we-are",
    "/company",
    "/company/team",
    "/company/people",
    "/about-us/team",
    "/about-us/our-team",
    "/agents",
    "/our-agents",
    "/meet-our-team",
    "/contact",
    "/contact-us",
    "/get-in-touch",
]


def _parse_linkedin_slug(slug: str) -> str:
    """Convert a LinkedIn profile slug like 'andy-chien-67424846' into a name."""
    slug = slug.strip("/")
    if not slug:
        return ""
    # Drop trailing id segments that contain digits or are empty.
    parts = [p for p in slug.split("-") if p]
    parts = [p for p in parts if not any(c.isdigit() for c in p)]
    if not parts:
        return ""
    return " ".join(p if len(p) == 1 and p.isalpha() else p.title() for p in parts)


def _title_case_name(name: str) -> str:
    """Title-case a name while preserving known acronyms/initials."""
    if not name:
        return ""
    parts = name.split()
    cleaned: list[str] = []
    for p in parts:
        if (
            len(p) == 1
            and p.isalpha()
            or re.match(r"^[A-Z]\.?$", p)
            or p.upper() in {"CEO", "COO", "CFO", "CTO", "CMO", "VP", "CPA", "HR"}
        ):
            cleaned.append(p.upper())
        else:
            cleaned.append(p.title())
    return " ".join(cleaned)


_TITLE_BOILERPLATE = re.compile(
    r"\b(Read Bio|Read More|Connect|LinkedIn|Facebook|Instagram|Twitter|TikTok|YouTube)\b",
    re.I,
)


def _clean_title(title: str) -> str:
    """Strip HTML entities and boilerplate from a title string."""
    title = re.sub(r"<[^>]+>", "", title)
    title = title.replace("&amp;", "&").replace("&nbsp;", " ")
    title = _TITLE_BOILERPLATE.sub("", title)
    title = title.replace("|", " ").replace("  ", " ")
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title


def _is_plausible_person_name(name: str) -> bool:
    """Return True if the extracted string looks like a real person name."""
    if not name or len(name) > 80 or len(name) < 3:
        return False
    if "@" in name or "http" in name.lower() or "/" in name or "linkedin" in name.lower():
        return False
    words = name.split()
    if not (2 <= len(words) <= 4):
        return False
    # Reject phone numbers and other numeric fragments that made it through.
    if any(w.isdigit() or re.search(r"\d", w) for w in words):
        return False
    # Reject all-caps 1-3 letter tokens such as initials/acronyms without a real name.
    if all(w.isupper() and len(w) <= 3 for w in words):
        return False
    return is_valid_named_contact(name)


class _PersonResult:
    """Simple container for an extracted person."""

    def __init__(
        self,
        name: str = "",
        title: str = "",
        email: str = "",
        phone: str = "",
        linkedin: str = "",
        structured: bool = False,
    ) -> None:
        self.name = _title_case_name(name)
        self.title = _clean_title(title)
        self.email = email.strip().lower()
        self.phone = phone.strip()
        self.linkedin = linkedin.strip()
        self.structured = structured

    def _is_generic_name(self) -> bool:
        """Return True if the extracted 'name' is a department/role, not a person."""
        return not _is_plausible_person_name(self.name)

    def as_routes(self) -> list[dict[str, Any]]:
        """Return ContactRoute-compatible route dicts."""
        routes: list[dict[str, Any]] = []
        is_person = not self._is_generic_name()
        named_email = bool(self.email and is_person and _name_in_email_local(self.name, self.email))
        # A telephone link inside the same structured person card is explicit
        # person evidence, even when the page does not publish an email or
        # LinkedIn profile.
        has_person_evidence = (
            self.structured or named_email or bool(self.phone and is_person) or bool(self.linkedin)
        )
        if self.email:
            if named_email:
                display = (
                    f"{self.name} ({self.title}) <{self.email}>"
                    if self.title
                    else f"{self.name} <{self.email}>"
                )
            else:
                display = self.email
            if len(display) <= 255:
                routes.append(
                    {
                        "type": ("named_work_email_approved" if named_email else "generic_email"),
                        "value": display,
                        "is_verified": False,
                    }
                )
        if self.phone:
            display = (
                f"{self.name} ({self.title}) <{self.phone}>"
                if (has_person_evidence and self.title)
                else (f"{self.name} <{self.phone}>" if has_person_evidence else self.phone)
            )
            if len(display) <= 255:
                routes.append(
                    {
                        "type": "business_phone",
                        "value": display,
                        "is_verified": False,
                    }
                )
        if self.linkedin:
            display = (
                f"{self.name} ({self.title}) - {self.linkedin}"
                if (self.name and self.title)
                else (f"{self.name} - {self.linkedin}" if self.name else self.linkedin)
            )
            if len(display) <= 255:
                routes.append(
                    {
                        "type": "social_profile_review_only",
                        "value": display,
                        "is_verified": False,
                    }
                )
        if self.name and is_person and has_person_evidence:
            display = f"{self.name} ({self.title})" if self.title else self.name
            if len(display) <= 255:
                routes.append(
                    {
                        "type": "named_contact",
                        "value": display,
                        "is_verified": False,
                    }
                )
        return routes


def _is_plausible_title(text: str) -> bool:
    """Return True if text looks like a job title rather than navigation boilerplate."""
    if not text or len(text) > 80:
        return False
    words = text.split()
    if not (1 <= len(words) <= 8):
        return False
    if any(w.lower() in _NAV_WORDS for w in words):
        return False
    return bool(_TITLE_RE.search(text))


def _extract_title_phrase(text: str, name: str = "") -> str:
    """Return the most plausible job-title phrase, excluding the person's name."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    # Look for a capitalized phrase that contains a title keyword but does
    # not start with the person's name.
    for match in re.finditer(r"([A-Z][A-Za-z\-&'\.]+(?:\s+[A-Za-z\-&'\.]+){0,6})", text):
        phrase = match.group(1).strip()
        if not _is_plausible_title(phrase):
            continue
        if name and phrase.lower().startswith(name.lower()):
            # Try to return only the title portion.
            for tmatch in _TITLE_RE.finditer(phrase):
                tail = phrase[tmatch.start() :].strip()
                if _is_plausible_title(tail):
                    return tail
            continue
        return phrase
    return ""


def _find_person_ancestor(tag: Any) -> Any:
    """Climb the DOM looking for a card/block that likely contains one person."""
    for _ in range(6):
        if tag is None:
            return None
        if tag.name in {"div", "li", "article", "section"}:
            cls = " ".join(tag.get("class", [])).lower()
            text = tag.get_text(separator=" ", strip=True).lower()
            if any(
                k in cls or k in text
                for k in ("team", "member", "person", "profile", "card", "bio")
            ):
                return tag
        tag = tag.parent
    return None


def _name_and_title_from_parent(a_tag: Any) -> tuple[str, str]:
    """Given an <a> tag, try to find the person's name and title in surrounding DOM."""
    parent = _find_person_ancestor(a_tag)
    if parent is None:
        parent = a_tag.parent
    if parent is None:
        return "", ""

    name = ""
    # Prefer an explicit heading/span/div that is just a name.
    for tag in parent.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "span", "div", "p"]):
        txt = tag.get_text(separator=" ", strip=True)
        if _is_plausible_person_name(txt):
            match = _NAME_RE.search(txt)
            if match:
                name = match.group(1)
                break

    title = ""
    # Search the same parent block for a title-bearing tag that is not the name.
    for tag in parent.find_all(["h2", "h3", "h4", "h5", "h6", "span", "div", "p"]):
        txt = tag.get_text(separator=" ", strip=True)
        if name and (name.lower() in txt.lower() or txt.lower() in name.lower()):
            continue
        if _is_plausible_title(txt):
            title = _clean_title(txt)
            if name.lower() not in title.lower():
                break

    return name, title


def _extract_from_soup(soup: BeautifulSoup, base_url: str, domain: str) -> list[dict[str, Any]]:
    """Extract named contact routes from a parsed team/about page."""
    people: dict[str, _PersonResult] = {}

    # 1. JSON-LD Person / employee records
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        pending: list[Any] = [data]
        while pending:
            item = pending.pop()
            if isinstance(item, list):
                pending.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            pending.extend(value for value in item.values() if isinstance(value, (dict, list)))
            types = item.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if "Person" not in types and "employee" not in types:
                continue
            name = item.get("name", "")
            title = item.get("jobTitle", "") or item.get("title", "")
            email = item.get("email", "")
            phone = item.get("telephone", "")
            linkedin = ""
            same_as = item.get("sameAs", [])
            if isinstance(same_as, str):
                same_as = [same_as]
            for sa in same_as:
                if isinstance(sa, str):
                    linkedin = extract_linkedin_profile_url(sa) or linkedin
            p = _PersonResult(name=name, title=title, email=email, phone=phone, linkedin=linkedin)
            if email:
                people[email] = p
            elif linkedin:
                people[linkedin] = p
            elif name:
                people[name.lower()] = p

    # 2. Schema.org Person microdata used by many staff/profile templates.
    for card in soup.find_all(attrs={"itemscope": True}):
        item_type = str(card.get("itemtype", "")).lower()
        if "schema.org/person" not in item_type:
            continue

        props: dict[str, str] = {}
        for prop_name in ("name", "jobTitle", "email", "telephone", "sameAs"):
            tag = card.find(attrs={"itemprop": prop_name})
            props[prop_name] = (
                str(tag.get("content") or tag.get("href") or tag.get_text(" ", strip=True))
                if tag is not None
                else ""
            )

        name = props["name"]
        title = props["jobTitle"]
        email = extract_email(props["email"]) or ""
        phone = extract_phone(props["telephone"]) or ""
        linkedin = extract_linkedin_profile_url(props["sameAs"]) or ""
        if name:
            people[f"microdata:{name.lower()}"] = _PersonResult(
                name=name,
                title=title,
                email=email,
                phone=phone,
                linkedin=linkedin,
            )

    # 3. Ordinary staff/profile cards with an explicit name and job title.
    for card in soup.find_all(["article", "li", "div"], class_=_PERSON_CARD_RE):
        name = ""
        name_tags = list(card.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
        name_tags.extend(card.find_all(["div", "span", "p"], class_=re.compile("name", re.I)))
        for tag in name_tags:
            candidate = tag.get_text(" ", strip=True)
            if _is_plausible_person_name(candidate):
                name = candidate
                break
        if not name:
            continue

        title = ""
        title_tags = list(
            card.find_all(
                ["div", "span", "p"],
                class_=re.compile(r"(?:job|position|role|title)", re.I),
            )
        )
        title_tags.extend(card.find_all(["p", "span"]))
        for tag in title_tags:
            candidate = tag.get_text(" ", strip=True)
            keyword = _TITLE_RE.search(candidate)
            prefix = candidate[: keyword.start()].strip(" ,-|") if keyword else ""
            if prefix and _is_plausible_person_name(prefix):
                continue
            if _is_plausible_title(candidate):
                title = candidate
                break
        if title:
            card_text = card.get_text(" ", strip=True)
            people.setdefault(
                f"card:{name.lower()}",
                _PersonResult(
                    name=name,
                    title=title,
                    email=extract_email(card_text) or "",
                    phone=extract_phone(card_text) or "",
                    linkedin=extract_linkedin_profile_url(card_text) or "",
                    structured=True,
                ),
            )

    # 4. Anchor tags: mailto, tel, LinkedIn
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if href.startswith("mailto:"):
            email = href.split(":", 1)[1].split("?")[0].strip().lower()
            if not email or "@" not in email:
                continue
            name, title = _name_and_title_from_parent(a)
            if not name:
                text_name = a.get_text(strip=True)
                if _is_plausible_person_name(text_name):
                    name = text_name
            p = _PersonResult(name=name, title=title, email=email)
            people[email] = p
        elif href.startswith("tel:"):
            phone = href.split(":", 1)[1].strip()
            if not phone:
                continue
            name, title = _name_and_title_from_parent(a)
            p = _PersonResult(name=name, title=title, phone=phone)
            people[phone] = p
        else:
            linkedin_url = extract_linkedin_profile_url(href)
            if linkedin_url:
                path_parts = urlparse(linkedin_url).path.strip("/").split("/")
                slug = path_parts[1] if len(path_parts) > 1 else ""
                name = _parse_linkedin_slug(slug)
                title = ""
                # Try to find a better name/title in the parent block
                p_name, p_title = _name_and_title_from_parent(a)
                if _is_plausible_person_name(p_name):
                    name = p_name
                if p_title:
                    title = p_title
                if not title:
                    title = (
                        _extract_title_phrase(
                            a.find_parent().get_text(separator=" ", strip=True), name
                        )
                        if a.find_parent()
                        else ""
                    )
                if not _is_plausible_person_name(name):
                    name = _parse_linkedin_slug(slug)
                p = _PersonResult(name=name, title=title, linkedin=linkedin_url)
                people[linkedin_url] = p

    # 5. data-* attributes (common on directory/contact widgets)
    data_attrs: list[tuple[str, str, Callable[[str], str]]] = [
        ("data-email", "email", lambda v: v.strip().lower()),
        ("data-phone", "phone", lambda v: v.strip()),
        ("data-mobile", "phone", lambda v: v.strip()),
        ("data-tel", "phone", lambda v: v.strip()),
    ]
    for attr_name, route_type, normalise in data_attrs:
        for tag in soup.find_all(attrs={attr_name: True}):
            raw = tag.get(attr_name)
            if not raw or not isinstance(raw, str):
                continue
            value = normalise(raw)
            if not value or "example.com" in value or "test.com" in value:
                continue
            if value in people:
                continue
            name, title = _name_and_title_from_parent(tag)
            if not name:
                text_name = tag.get_text(strip=True)
                if _is_plausible_person_name(text_name):
                    name = text_name
            people[value] = _PersonResult(
                name=name,
                title=title,
                email=value if route_type == "email" else "",
                phone=value if route_type == "phone" else "",
            )

    # 6. Visible text emails that appear next to a name
    for email_match in re.finditer(
        r"[\w.+-]+@[\w-]+\.[\w.-]+", soup.get_text(separator=" ", strip=True)
    ):
        email = email_match.group(0).lower()
        if email in people or any(person.email == email for person in people.values()):
            continue
        if "example.com" in email or "test.com" in email:
            continue
        # Try to grab the surrounding 200 chars for context
        start = max(0, email_match.start() - 200)
        context = soup.get_text(separator=" ", strip=True)[start : email_match.end() + 100]
        name = ""
        title = _extract_title_phrase(context, "")
        for name_match in _NAME_RE.finditer(context):
            candidate = name_match.group(1)
            if (
                "@" not in candidate
                and 3 <= len(candidate) <= 40
                and is_valid_named_contact(candidate)
            ):
                name = candidate
                break
        people[email] = _PersonResult(name=name, title=title, email=email)

    routes: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for person in people.values():
        for route in person.as_routes():
            key = (str(route["type"]), str(route["value"]).lower())
            if key in seen:
                continue
            seen.add(key)
            routes.append(route)

    form_url = extract_contact_form_url(base_url) if soup.find("form") else None
    if form_url:
        routes.append({"type": "contact_form", "value": form_url, "is_verified": False})

    return routes


class TeamPagesAdapter(BaseSourceAdapter):
    """Fetch bounded team/about pages and extract named contacts + social profiles."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)
        self._counter = 0
        self._counter_lock = asyncio.Lock()
        self.client = self._new_async_client(
            httpx.Timeout(10.0, connect=5.0, read=15.0, write=5.0, pool=5.0),
            httpx.Limits(max_connections=50, max_keepalive_connections=20),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )

    @property
    def source_key(self) -> str:
        return "team_pages"

    async def _process_domain(
        self,
        domain: str,
        paths: list[str],
        total: int,
        max_pages_per_domain: int | None = None,
    ) -> dict[str, Any] | None:
        async with self._counter_lock:
            self._counter += 1
            idx = self._counter
        print(f"[team_pages] {idx}/{total}: {domain}", flush=True)
        base_url = f"https://{domain}"
        max_pages = max_pages_per_domain or int(
            self.config.adapter_config.get("max_pages_per_domain", 50)
        )
        seen_route_keys: set[tuple[str, str]] = set()
        all_routes: list[dict[str, Any]] = []
        first_url = ""
        first_title = ""
        first_body_excerpt = ""
        first_company_name = ""
        pages_crawled = 0
        for path in paths[:max_pages]:
            url = urljoin(base_url, path)
            if not await self._robots_allowed(url):
                continue
            try:
                response = await self._http_get(url, expected_host=domain)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    continue
                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                routes = _extract_from_soup(soup, str(response.url), domain)
                pages_crawled += 1
                if routes:
                    if not first_url:
                        first_url = str(response.url)
                        title_tag = soup.find("title")
                        first_title = (
                            self._clean_text(title_tag.get_text(strip=True))
                            if title_tag
                            else f"Team page for {domain}"
                        )
                        first_body_excerpt = self._clean_text(
                            soup.get_text(separator=" ", strip=True)
                        )[:2000]
                        h1 = soup.find("h1")
                        h1_text = self._clean_text(h1.get_text(strip=True)) if h1 else ""
                        first_company_name = (
                            h1_text if 3 <= len(h1_text) <= 80 and "@" not in h1_text else domain
                        )
                    for route in routes:
                        key = (str(route["type"]), str(route["value"]).lower())
                        if key in seen_route_keys:
                            continue
                        seen_route_keys.add(key)
                        all_routes.append(route)
            except httpx.HTTPStatusError:
                # 4xx/5xx on a guessed path is expected; keep trying other paths.
                continue
            except httpx.HTTPError as exc:
                self.metrics.record_error("fetch")
                print(f"[team_pages] network error {url}: {exc}", flush=True)
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"[team_pages] error {url}: {exc}", flush=True)
                continue
        if not all_routes or not first_url:
            return None
        return {
            "domain": domain,
            "url": first_url,
            "title": first_title,
            "body_excerpt": first_body_excerpt,
            "company_name": first_company_name,
            "contact_routes": all_routes,
            "pages_crawled": pages_crawled,
        }

    async def fetch(self, workspace_id: UUID, query: dict[str, Any]) -> list[dict[str, Any]]:
        domains = query.get("domains") or self.config.adapter_config.get("domains")
        if not domains:
            single = query.get("domain") or self.config.adapter_config.get("domain")
            domains = [single] if single else []
        domains = [d for d in domains if self._is_safe_domain(str(d))]
        if not domains:
            return []
        paths = query.get("paths", self.config.adapter_config.get("paths", _TEAM_PAGE_PATHS))
        max_pages = int(
            query.get("max_pages_per_domain")
            or self.config.adapter_config.get("max_pages_per_domain", 50)
        )
        results: list[dict[str, Any]] = []
        print(f"[team_pages] starting extraction for {len(domains)} domains", flush=True)
        self._counter = 0

        async def process(domain: str) -> dict[str, Any] | None:
            return await self._process_domain(domain, paths, len(domains), max_pages)

        results = [
            result for result in await self._map_bounded(domains, process) if result is not None
        ]
        print(
            f"[team_pages] extracted routes for {len(results)} domains",
            flush=True,
        )
        return results

    def _clean_text(self, text: str) -> str:
        """Remove null bytes and invalid UTF-8 sequences from extracted text."""
        text = text.replace("\x00", "")
        return text.encode("utf-8", "ignore").decode("utf-8")

    def normalize(self, workspace_id: UUID, raw: dict[str, Any]) -> dict[str, Any]:
        title = raw.get("title") or f"Team page for {raw['domain']}"
        text = raw.get("body_excerpt") or ""
        company_name = raw.get("company_name") or raw["domain"]
        return {
            "workspace_id": workspace_id,
            "source_key": self.source_key,
            "source_native_id": raw["url"],
            "source_url": raw["url"],
            "observed_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "title": title[:255],
            "body_excerpt": text[:2000],
            "company_name_raw": company_name,
            "company_domain_raw": raw["domain"],
            "location_raw": "",
            "workplace_type": "inferred_remote_friendly",
            "contact_routes_raw": raw.get("contact_routes", []),
            "raw_snapshot_uri": "",
            "content_hash": "",
            "access_policy_version": "source-policy-v1",
            "company_id": None,
        }
