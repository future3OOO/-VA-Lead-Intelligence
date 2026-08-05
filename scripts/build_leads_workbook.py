#!/usr/bin/env python3
"""Build the readable four-sheet workbook from the canonical CSV exports."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import NamedTuple

from export_leads_csv import COMPANY_FIELDS, CONTACT_FIELDS, LEAD_FIELDS, PRIMARY_CONTACT_FIELDS
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table

from services.source_engine.enricher import email_matches_person, extract_email


class SheetSpec(NamedTuple):
    name: str
    path: Path
    fields: list[str]
    table_name: str


HEADER_FILL = PatternFill("solid", fgColor="404040")
HEADER_FONT = Font(color="FFFFFF", bold=True)
HEADER_ALIGNMENT = Alignment(vertical="center", wrap_text=False)
BODY_ALIGNMENT = Alignment(vertical="center", wrap_text=False)
COORDINATES_RE = re.compile(
    r"^'?\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+"
    r"(?:\s*,\s*(?P<country>Australia|New Zealand|NZ))?\s*$",
    re.IGNORECASE,
)
PRIMARY_PERSON_FIELDS = [
    "primary_contact_name",
    "primary_contact_title",
    "primary_contact_email",
    "primary_contact_phone",
    "primary_contact_linkedin",
]
WORKBOOK_FIELDS = {
    "Leads": [
        "company_name",
        "primary_domain",
        "rank",
        "qualification_score",
        "job_title",
        "outreach_type",
        "contact_name",
        "contact_title",
        "contact_emails",
        "company_email",
        "contact_phones",
        "company_phone",
        "contact_linkedin_urls",
        "company_form",
        "best_email",
        "best_phone",
        "best_form",
        "category",
        "location",
        "workplace_type",
        "source",
        "source_url",
        "intent_label",
        "published_at",
        "explanation",
        "outreach_target_id",
        "lead_id",
        "company_id",
        "contact_id",
        "primary_contact_id",
        *PRIMARY_PERSON_FIELDS,
        "coordinates",
    ],
    "Primary Contacts": [
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
        "lead_id",
        "company_id",
        "primary_contact_id",
    ],
    "Contacts": [
        "company_name",
        "primary_domain",
        "contact_name",
        "contact_title",
        "contact_emails",
        "contact_phones",
        "contact_linkedin_urls",
        "contact_id",
        "company_id",
    ],
    "Companies": [
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
        "company_id",
    ],
}
DISPLAY_HEADERS = {
    "company_name": "Company",
    "primary_domain": "Domain",
    "job_title": "Lead title",
    "outreach_type": "Outreach type",
    "contact_name": "Contact name",
    "contact_title": "Contact title",
    "contact_emails": "Person email(s)",
    "contact_phones": "Person phone(s)",
    "contact_linkedin_urls": "Person LinkedIn profile(s)",
    "rank": "Rank",
    "qualification_score": "Score",
    "category": "Category",
    "location": "Location",
    "workplace_type": "Workplace type",
    "company_email": "Unattributed email",
    "company_phone": "Company phone",
    "company_form": "Company contact form",
    "best_email": "Best email",
    "best_phone": "Best phone",
    "best_form": "Best contact form",
    "source": "Source",
    "source_url": "Source URL",
    "intent_label": "Intent",
    "published_at": "Published",
    "explanation": "Explanation",
    "outreach_target_id": "Outreach target ID",
    "lead_id": "Lead ID",
    "company_id": "Company ID",
    "contact_id": "Contact ID",
    "primary_contact_id": "Primary contact ID",
    "coordinates": "Coordinates",
    "primary_contact_status": "Contact status",
    "primary_contact_name": "Selected primary name",
    "primary_contact_title": "Selected primary title",
    "primary_contact_email": "Selected primary email",
    "primary_contact_phone": "Selected primary phone",
    "primary_contact_linkedin": "Selected primary LinkedIn",
    "target_fit": "Target fit",
    "source_hit_count": "Source hits",
    "named_contact_name": "Named contact",
    "named_contact_title": "Named contact title",
    "named_contact_email": "Named contact email",
    "named_contact_phone": "Named contact phone",
    "named_contact_linkedin": "Named contact LinkedIn",
}
HIDDEN_FIELDS = {
    "outreach_target_id",
    "lead_id",
    "company_id",
    "contact_id",
    "primary_contact_id",
    "coordinates",
}
SHEET_HIDDEN_FIELDS = {"Leads": HIDDEN_FIELDS | set(PRIMARY_PERSON_FIELDS)}
HYPERLINK_FIELDS = {
    "primary_contact_linkedin",
    "contact_linkedin_urls",
    "named_contact_linkedin",
    "company_form",
    "best_form",
    "source_url",
}
TEXT_COLUMNS = {
    "lead_id",
    "company_id",
    "primary_contact_id",
    "contact_id",
    "primary_contact_email",
    "primary_contact_phone",
    "primary_contact_linkedin",
    "contact_emails",
    "contact_phones",
    "contact_linkedin_urls",
    "coordinates",
    "named_contact_email",
    "named_contact_phone",
    "named_contact_linkedin",
    "company_email",
    "company_phone",
    "company_form",
    "best_email",
    "best_phone",
    "best_form",
}
WIDE_COLUMNS = {
    "lead_id": 38,
    "company_id": 38,
    "primary_contact_id": 38,
    "contact_id": 38,
    "company_name": 28,
    "primary_domain": 28,
    "primary_contact_name": 24,
    "primary_contact_title": 25,
    "primary_contact_email": 30,
    "primary_contact_phone": 22,
    "primary_contact_linkedin": 40,
    "contact_name": 24,
    "contact_title": 25,
    "contact_emails": 34,
    "contact_phones": 25,
    "contact_linkedin_urls": 40,
    "outreach_type": 18,
    "coordinates": 24,
    "named_contact_name": 24,
    "named_contact_title": 25,
    "named_contact_email": 30,
    "named_contact_phone": 22,
    "named_contact_linkedin": 40,
    "company_email": 30,
    "company_phone": 22,
    "company_form": 40,
    "best_email": 30,
    "best_phone": 22,
    "best_form": 40,
    "job_title": 34,
    "location": 26,
    "source_url": 40,
    "explanation": 56,
}


def _has_exported_email(value: str) -> bool:
    emails = [candidate.strip() for candidate in value.split(";") if candidate.strip()]
    return bool(emails) and all(
        extract_email(candidate) == candidate.casefold() for candidate in emails
    )


def _operational_leads(
    leads: list[dict[str, str]], contacts: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Build one row per actionable outreach target without changing route ownership."""
    contacts_by_id = {contact["contact_id"]: contact for contact in contacts}
    contacts_by_company: dict[str, list[dict[str, str]]] = {}
    for contact in contacts:
        contacts_by_company.setdefault(contact["company_id"], []).append(contact)
    rank_order = {"high": 0, "medium": 1}
    ranked_leads = sorted(
        (lead for lead in leads if lead["rank"].casefold() in rank_order),
        key=lambda lead: (
            rank_order[lead["rank"].casefold()],
            lead["lead_id"],
        ),
    )
    company_leads: dict[str, dict[str, str]] = {}
    for lead in ranked_leads:
        company_leads.setdefault(lead["company_id"], lead)

    attributed_emails: dict[tuple[str, str], str] = {}
    promoted_emails: dict[str, set[str]] = {}
    for lead in ranked_leads:
        email = lead["company_email"].casefold()
        if not _has_exported_email(email):
            continue
        matches = [
            contact
            for contact in contacts_by_company.get(lead["company_id"], [])
            if email_matches_person(contact["contact_name"], email)
        ]
        if len(matches) == 1:
            contact_id = matches[0]["contact_id"]
            attributed_emails[(lead["company_id"], email)] = contact_id
            promoted_emails.setdefault(contact_id, set()).add(email)

    def projected_contact(contact: dict[str, str]) -> dict[str, str]:
        promoted = promoted_emails.get(contact.get("contact_id", ""), set())
        if not promoted:
            return contact
        emails = {
            value.strip().casefold()
            for value in contact["contact_emails"].split(";")
            if value.strip()
        } | promoted
        return {**contact, "contact_emails": "; ".join(sorted(emails))}

    rows: list[dict[str, str]] = []
    represented_contacts: set[str] = set()
    represented_emails: set[tuple[str, str]] = set()

    def append_row(
        lead: dict[str, str], contact: dict[str, str], role: str, target_id: str
    ) -> None:
        row = {field: lead.get(field, "") for field in LEAD_FIELDS}
        row.update(
            {
                field: contact.get(field, "")
                for field in (
                    "contact_id",
                    "contact_name",
                    "contact_title",
                    "contact_emails",
                    "contact_phones",
                    "contact_linkedin_urls",
                )
            }
        )
        row["outreach_type"] = role
        row["outreach_target_id"] = target_id
        raw_location = lead.get("location", "")
        coordinates = COORDINATES_RE.fullmatch(raw_location)
        row["coordinates"] = raw_location.removeprefix("'") if coordinates else ""
        country = coordinates.group("country") if coordinates else ""
        row["location"] = (
            "New Zealand"
            if country and country.casefold() in {"new zealand", "nz"}
            else "Australia"
            if country
            else "Mapped location"
            if coordinates
            else raw_location
        )
        rows.append(row)

    for lead in ranked_leads:
        contact = projected_contact(contacts_by_id.get(lead["primary_contact_id"], {}))
        person_is_actionable = _has_exported_email(contact.get("contact_emails", "")) or bool(
            contact.get("contact_linkedin_urls", "").strip()
        )
        company_email = lead["company_email"].casefold()
        company_email_key = (lead["company_id"], company_email)
        email_owner = attributed_emails.get(company_email_key)
        company_email_is_actionable = _has_exported_email(company_email) and not email_owner
        if email_owner:
            lead = {**lead, "company_email": ""}
        if person_is_actionable:
            target_id = contact["contact_id"]
            if target_id in represented_contacts:
                continue
            represented_contacts.add(target_id)
            if company_email_is_actionable:
                if company_email_key in represented_emails:
                    lead = {**lead, "company_email": ""}
                else:
                    represented_emails.add(company_email_key)
            append_row(lead, contact, "Primary", target_id)
            continue
        if company_email_is_actionable and company_email_key not in represented_emails:
            represented_emails.add(company_email_key)
            append_row(
                lead,
                {},
                "Unattributed email",
                f"email:{lead['company_id']}:{company_email}",
            )

    for raw_contact in contacts:
        contact = projected_contact(raw_contact)
        contact_id = contact["contact_id"]
        if contact_id in represented_contacts:
            continue
        has_email = _has_exported_email(contact["contact_emails"])
        has_linkedin = bool(contact["contact_linkedin_urls"].strip())
        representative = company_leads.get(contact["company_id"])
        if not has_linkedin and (not has_email or representative is None):
            continue
        represented_contacts.add(contact_id)
        append_row(
            {**representative, "company_email": ""}
            if representative
            else {
                "company_id": contact["company_id"],
                "company_name": contact["company_name"],
                "primary_domain": contact["primary_domain"],
            },
            contact,
            "Additional",
            contact_id,
        )

    rows.sort(
        key=lambda row: (
            0
            if _has_exported_email(row["contact_emails"])
            else 1
            if _has_exported_email(row["company_email"])
            else 2,
            rank_order.get(row["rank"].casefold(), 2),
            row["company_name"].casefold(),
            row["outreach_target_id"],
        )
    )
    return rows


def _read_rows(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        try:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None:
                raise ValueError(f"{path} is empty")
            if reader.fieldnames != expected_fields:
                raise ValueError(
                    f"{path} has unexpected columns; expected {', '.join(expected_fields)}"
                )
            rows = list(reader)
        except csv.Error as exc:
            raise ValueError(f"{path} contains malformed CSV: {exc}") from exc
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f"{path} contains a row with an unexpected number of values")
        return rows


def _index(rows: list[dict[str, str]], field: str, label: str) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row[field]
        if not value:
            raise ValueError(f"{label} contains a blank {field}")
        if value in indexed:
            raise ValueError(f"{label} contains duplicate {field} {value}")
        indexed[value] = row
    return indexed


def _validate_relations(rows_by_sheet: dict[str, list[dict[str, str]]]) -> None:
    leads = rows_by_sheet["Leads"]
    primary_contacts = rows_by_sheet["Primary Contacts"]
    contacts = _index(rows_by_sheet["Contacts"], "contact_id", "Contacts")
    companies = _index(rows_by_sheet["Companies"], "company_id", "Companies")
    _index(leads, "lead_id", "Leads")
    _index(primary_contacts, "lead_id", "Primary Contacts")

    if [row["lead_id"] for row in leads] != [row["lead_id"] for row in primary_contacts]:
        raise ValueError("Primary Contacts must contain exactly one ordered row per lead")

    for lead, primary in zip(leads, primary_contacts, strict=True):
        if (lead["company_id"], lead["primary_contact_id"]) != (
            primary["company_id"],
            primary["primary_contact_id"],
        ):
            raise ValueError(f"lead and primary contact references differ for {lead['lead_id']}")
        contact_id = lead["primary_contact_id"]
        company_id = lead["company_id"]
        status = primary["primary_contact_status"]
        if status == "available" and (not contact_id or not primary["primary_contact_name"]):
            raise ValueError(
                f"primary contact {lead['lead_id']} is available without a contact ID and name"
            )
        if status == "unavailable" and (
            contact_id or any(primary[field] for field in PRIMARY_PERSON_FIELDS)
        ):
            raise ValueError(
                f"primary contact {lead['lead_id']} is unavailable but has person data"
            )
        if status not in {"available", "unavailable"}:
            raise ValueError(f"primary contact {lead['lead_id']} has invalid status {status!r}")
        if contact_id and contact_id not in contacts:
            raise ValueError(f"lead {lead['lead_id']} references unknown contact {contact_id}")
        if company_id and company_id not in companies:
            raise ValueError(f"lead {lead['lead_id']} references unknown company {company_id}")
        if contact_id and contacts[contact_id]["company_id"] != company_id:
            raise ValueError(f"lead {lead['lead_id']} references a contact from another company")

    for contact in contacts.values():
        company_id = contact["company_id"]
        if company_id and company_id not in companies:
            raise ValueError(
                f"contact {contact['contact_id']} references unknown company {company_id}"
            )


def _add_sheet(workbook: Workbook, spec: SheetSpec, rows: list[dict[str, str]]) -> None:
    sheet = workbook.create_sheet(spec.name)
    fields = WORKBOOK_FIELDS[spec.name]
    hidden_fields = SHEET_HIDDEN_FIELDS.get(spec.name, HIDDEN_FIELDS)
    sheet.append([DISPLAY_HEADERS.get(field, field.replace("_", " ").title()) for field in fields])
    for row in rows:
        sheet.append([row[field] for field in fields])

    sheet.freeze_panes = "A2"
    sheet.row_dimensions[1].height = 18
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    for column, field in enumerate(fields, start=1):
        letter = sheet.cell(row=1, column=column).column_letter
        sheet.column_dimensions[letter].width = WIDE_COLUMNS.get(field, 18)
        sheet.column_dimensions[letter].hidden = field in hidden_fields
        for cell in sheet.iter_cols(min_col=column, max_col=column, min_row=2):
            for value_cell in cell:
                value_cell.alignment = BODY_ALIGNMENT
                if field in TEXT_COLUMNS:
                    value_cell.number_format = "@"
                value = value_cell.value
                if (
                    field in HYPERLINK_FIELDS
                    and isinstance(value, str)
                    and value.startswith(("https://", "http://"))
                    and ";" not in value
                ):
                    value_cell.hyperlink = value
                    value_cell.style = "Hyperlink"

    table = Table(displayName=spec.table_name, ref=sheet.dimensions)
    sheet.add_table(table)


def build_workbook(
    leads_path: Path,
    primary_contacts_path: Path,
    contacts_path: Path,
    companies_path: Path,
    output_path: Path,
) -> None:
    """Build one workbook without changing or re-associating export data."""
    specs = (
        SheetSpec("Leads", leads_path, LEAD_FIELDS, "LeadsTable"),
        SheetSpec(
            "Primary Contacts",
            primary_contacts_path,
            PRIMARY_CONTACT_FIELDS,
            "PrimaryContactsTable",
        ),
        SheetSpec("Contacts", contacts_path, CONTACT_FIELDS, "ContactsTable"),
        SheetSpec("Companies", companies_path, COMPANY_FIELDS, "CompaniesTable"),
    )
    for spec in specs:
        omitted = set(spec.fields) - set(WORKBOOK_FIELDS[spec.name])
        if omitted:
            raise ValueError(f"{spec.name} workbook columns omit: {', '.join(sorted(omitted))}")
    rows_by_sheet = {spec.name: _read_rows(spec.path, spec.fields) for spec in specs}
    _validate_relations(rows_by_sheet)
    rows_by_sheet["Leads"] = _operational_leads(rows_by_sheet["Leads"], rows_by_sheet["Contacts"])

    workbook = Workbook()
    workbook.remove(workbook.worksheets[0])
    for spec in specs:
        _add_sheet(workbook, spec, rows_by_sheet[spec.name])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--leads",
        type=Path,
        default=Path("exports/anz_remote_leads_with_contacts.csv"),
    )
    parser.add_argument(
        "--primary-contacts",
        type=Path,
        default=Path("exports/anz_primary_contacts.csv"),
    )
    parser.add_argument(
        "--contacts",
        type=Path,
        default=Path("exports/anz_contacts.csv"),
    )
    parser.add_argument(
        "--companies",
        type=Path,
        default=Path("exports/anz_all_companies.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("exports/anz_full_leads_with_targeted_contacts.xlsx"),
    )
    args = parser.parse_args()
    try:
        build_workbook(
            args.leads,
            args.primary_contacts,
            args.contacts,
            args.companies,
            args.output,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Built workbook: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
