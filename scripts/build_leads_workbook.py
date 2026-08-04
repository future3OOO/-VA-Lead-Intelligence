#!/usr/bin/env python3
"""Build the readable three-sheet workbook from the canonical CSV exports."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import NamedTuple

from export_leads_csv import COMPANY_FIELDS, LEAD_FIELDS, NAMED_CONTACT_FIELDS
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
    "named_contact_email",
    "named_contact_emails",
    "named_contact_phone",
    "named_contact_phones",
    "named_contact_linkedin",
    "named_contact_linkedin_urls",
    "company_email",
    "company_phone",
    "company_form",
    "best_email",
    "best_phone",
    "best_form",
}
WIDE_COLUMNS = {
    "company_name": 28,
    "primary_domain": 28,
    "named_contact_name": 24,
    "named_contact_title": 25,
    "named_contact_email": 30,
    "named_contact_emails": 34,
    "named_contact_phone": 22,
    "named_contact_phones": 25,
    "named_contact_linkedin": 40,
    "named_contact_linkedin_urls": 40,
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


def _read_rows(path: Path, expected_fields: list[str]) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            fields = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path} is empty") from exc
        if fields != expected_fields:
            raise ValueError(
                f"{path} has unexpected columns; expected {', '.join(expected_fields)}"
            )
        return list(reader)


def _add_sheet(workbook: Workbook, spec: SheetSpec) -> None:
    rows = _read_rows(spec.path, spec.fields)
    sheet = workbook.create_sheet(spec.name)
    sheet.append(spec.fields)
    for row in rows:
        if len(row) != len(spec.fields):
            raise ValueError(
                f"{spec.path} contains a row with {len(row)} values; expected {len(spec.fields)}"
            )
        sheet.append(row)

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
    named_contacts_path: Path,
    companies_path: Path,
    output_path: Path,
) -> None:
    """Build one workbook without changing or re-associating export data."""
    workbook = Workbook()
    workbook.remove(workbook.worksheets[0])
    for spec in (
        SheetSpec("Leads", leads_path, LEAD_FIELDS, "LeadsTable"),
        SheetSpec(
            "Named Contacts",
            named_contacts_path,
            NAMED_CONTACT_FIELDS,
            "NamedContactsTable",
        ),
        SheetSpec("Companies", companies_path, COMPANY_FIELDS, "CompaniesTable"),
    ):
        _add_sheet(workbook, spec)
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
        "--named-contacts",
        type=Path,
        default=Path("exports/anz_named_contacts.csv"),
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
        build_workbook(args.leads, args.named_contacts, args.companies, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Built workbook: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
