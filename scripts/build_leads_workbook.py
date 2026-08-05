#!/usr/bin/env python3
"""Build the readable four-sheet workbook from the canonical CSV exports."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import NamedTuple

from export_leads_csv import COMPANY_FIELDS, CONTACT_FIELDS, LEAD_FIELDS, PRIMARY_CONTACT_FIELDS
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table


class SheetSpec(NamedTuple):
    name: str
    path: Path
    fields: list[str]
    table_name: str


HEADER_FILL = PatternFill("solid", fgColor="404040")
HEADER_FONT = Font(color="FFFFFF", bold=True)
HEADER_ALIGNMENT = Alignment(vertical="center", wrap_text=False)
BODY_ALIGNMENT = Alignment(vertical="center", wrap_text=False)
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


def _read_rows(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty")
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"{path} has unexpected columns; expected {', '.join(expected_fields)}"
            )
        rows = list(reader)
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
        person_fields = (
            "primary_contact_name",
            "primary_contact_title",
            "primary_contact_email",
            "primary_contact_phone",
            "primary_contact_linkedin",
        )
        if status == "available" and (not contact_id or not primary["primary_contact_name"]):
            raise ValueError(
                f"primary contact {lead['lead_id']} is available without a contact ID and name"
            )
        if status == "unavailable" and (
            contact_id or any(primary[field] for field in person_fields)
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
    sheet.append(spec.fields)
    for row in rows:
        sheet.append([row[field] for field in spec.fields])

    sheet.freeze_panes = "A2"
    sheet.row_dimensions[1].height = 18
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    for column, field in enumerate(spec.fields, start=1):
        letter = sheet.cell(row=1, column=column).column_letter
        sheet.column_dimensions[letter].width = WIDE_COLUMNS.get(field, 18)
        for cell in sheet.iter_cols(min_col=column, max_col=column, min_row=2):
            for value_cell in cell:
                value_cell.alignment = BODY_ALIGNMENT
                if field in TEXT_COLUMNS:
                    value_cell.number_format = "@"

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
    rows_by_sheet = {spec.name: _read_rows(spec.path, spec.fields) for spec in specs}
    _validate_relations(rows_by_sheet)

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
