from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

LEAD_FIELDS = [
    "company_name",
    "primary_domain",
    "named_contact_name",
    "named_contact_title",
    "named_contact_email",
    "named_contact_phone",
    "named_contact_linkedin",
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

NAMED_CONTACT_FIELDS = [
    "company_id",
    "company_name",
    "primary_domain",
    "named_contact_name",
    "named_contact_title",
    "named_contact_emails",
    "named_contact_phones",
    "named_contact_linkedin_urls",
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


def _write_csv(path: Path, fields: list[str], row: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def _distinct_row(fields: list[str], prefix: str) -> dict[str, str]:
    row = {field: f"{prefix}:{field}" for field in fields}
    for index, field in enumerate(fields):
        if "phone" in field:
            row[field] = f"+64 21 555 {index:04d}"
        elif "email" in field:
            row[field] = f"{prefix}.{field}@example.org"
        elif "linkedin" in field:
            row[field] = f"https://www.linkedin.com/in/{prefix}-{field}"
    return row


def test_workbook_cli_preserves_all_three_export_tables(tmp_path: Path) -> None:
    leads_path = tmp_path / "leads.csv"
    contacts_path = tmp_path / "named_contacts.csv"
    companies_path = tmp_path / "companies.csv"
    workbook_path = tmp_path / "leads.xlsx"

    lead_row = _distinct_row(LEAD_FIELDS, "lead")
    contact_row = _distinct_row(NAMED_CONTACT_FIELDS, "contact")
    company_row = _distinct_row(COMPANY_FIELDS, "company")
    _write_csv(leads_path, LEAD_FIELDS, lead_row)
    _write_csv(contacts_path, NAMED_CONTACT_FIELDS, contact_row)
    _write_csv(companies_path, COMPANY_FIELDS, company_row)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_leads_workbook.py",
            "--leads",
            str(leads_path),
            "--named-contacts",
            str(contacts_path),
            "--companies",
            str(companies_path),
            "--output",
            str(workbook_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    workbook = load_workbook(workbook_path, read_only=False, data_only=False)
    assert workbook.sheetnames == ["Leads", "Named Contacts", "Companies"]

    expected = [
        ("Leads", LEAD_FIELDS, lead_row, "LeadsTable"),
        ("Named Contacts", NAMED_CONTACT_FIELDS, contact_row, "NamedContactsTable"),
        ("Companies", COMPANY_FIELDS, company_row, "CompaniesTable"),
    ]
    for sheet_name, fields, row, table_name in expected:
        sheet = workbook[sheet_name]
        assert sheet.max_row == 2
        assert sheet.max_column == len(fields)
        assert [cell.value for cell in sheet[1]] == fields
        assert [cell.value for cell in sheet[2]] == [row[field] for field in fields]
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref == sheet.dimensions
        assert sheet.row_dimensions[1].height == 18
        assert all(not cell.alignment.wrap_text for cell in sheet[1])
        assert all(not cell.alignment.wrap_text for cell in sheet[2])
        assert sheet.tables[table_name].ref == sheet.dimensions
        assert sheet.tables[table_name].tableStyleInfo is None
        contact_column = next(
            index for index, field in enumerate(fields, start=1) if "phone" in field
        )
        assert sheet.cell(row=2, column=contact_column).number_format == "@"


def test_workbook_cli_rejects_an_unexpected_csv_contract(tmp_path: Path) -> None:
    leads_path = tmp_path / "leads.csv"
    contacts_path = tmp_path / "named_contacts.csv"
    companies_path = tmp_path / "companies.csv"
    workbook_path = tmp_path / "leads.xlsx"
    _write_csv(leads_path, ["wrong_column"], {"wrong_column": "value"})
    _write_csv(contacts_path, NAMED_CONTACT_FIELDS, {})
    _write_csv(companies_path, COMPANY_FIELDS, {})

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_leads_workbook.py",
            "--leads",
            str(leads_path),
            "--named-contacts",
            str(contacts_path),
            "--companies",
            str(companies_path),
            "--output",
            str(workbook_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unexpected columns" in result.stderr
    assert not workbook_path.exists()
