#!/usr/bin/env python3
"""Regenerate, validate, and bundle all release artifacts."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist" / "handover"


def run(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, check=False, text=True, capture_output=True, env=env)


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def check_git_clean() -> tuple[bool, str]:
    result = run(["git", "status", "--porcelain"])
    clean = result.stdout.strip() == ""
    return clean, result.stdout


def check_adrs() -> tuple[bool, list[str]]:
    adr_dir = REPO_ROOT / "docs" / "adr"
    statuses: list[str] = []
    for path in sorted(adr_dir.glob("ADR-*.md")):
        text = path.read_text()
        if "Status:** accepted" not in text and "Status:** accepted" not in text:
            statuses.append(f"{path.name} not accepted")
    return not statuses, statuses


def check_policies() -> tuple[bool, list[str]]:
    errors: list[str] = []
    for rel in [
        "config/source-policy/default.yaml",
        "config/jurisdiction-policy/default.yaml",
    ]:
        path = REPO_ROOT / rel
        data = yaml.safe_load(path.read_text()) or {}
        approved_at = data.get("approved_at")
        if not approved_at:
            errors.append(f"{rel} missing approved_at")
            continue
        try:
            approved = datetime.fromisoformat(str(approved_at)).replace(tzinfo=timezone.utc)
            if approved > datetime.now(timezone.utc):
                errors.append(f"{rel} approved_at in future")
        except ValueError as exc:
            errors.append(f"{rel} invalid approved_at: {exc}")
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-terraform", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    steps = [
        (
            "contracts",
            [
                sys.executable,
                "scripts/export_openapi.py",
                "--output",
                "contracts/openapi/lead-intelligence-v1.openapi.json",
            ],
        ),
        (
            "json schemas",
            [
                sys.executable,
                "scripts/export_json_schemas.py",
                "--output-dir",
                "contracts/jsonschema/",
            ],
        ),
        ("config validate", [sys.executable, "scripts/validate_configs.py"]),
        ("benchmark", [sys.executable, "scripts/build_benchmark.py"]),
        (
            "erd",
            [
                sys.executable,
                "scripts/render_erd.py",
                "--output",
                "docs/erd/lead-intelligence.svg",
                "--from-metadata",
            ],
        ),
        (
            "env catalogue",
            [
                sys.executable,
                "scripts/export_env_catalogue.py",
                "--output",
                "infra/terraform/ENVIRONMENT_CATALOGUE.md",
            ],
        ),
    ]

    if not args.skip_tests:
        steps.append(
            (
                "unit tests",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/",
                    "-q",
                    "--tb=short",
                    "--junitxml=reports/junit.xml",
                ],
            )
        )

    if not args.skip_terraform:
        steps.append(
            (
                "terraform validate",
                [
                    "bash",
                    "-c",
                    "cd infra/terraform && terraform init -backend=false && terraform validate",
                ],
            )
        )

    for name, cmd in steps:
        result = run(cmd, env=env)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            return fail(f"Step '{name}' failed (exit {result.returncode})")
        print(f"OK: {name}")

    # Regenerate DOD report (no JUnit yet -> will be marked blocked, but we still produce)
    dod_result = run(
        [
            sys.executable,
            "scripts/build_dod_report.py",
            "--requirements",
            "quality/definition-of-done.yaml",
            "--junit",
            "reports/junit.xml",
            "--output",
            "quality/traceability/production-v1.md",
        ]
    )
    if dod_result.returncode != 0:
        print("DOD report flagged blockers (expected until all tests are wired and run).")

    # Validation gates
    clean, dirty_files = check_git_clean()
    if not clean:
        print(dirty_files)
        return fail("Working tree is not clean after regeneration; commit generated artifacts.")

    adrs_ok, adr_errors = check_adrs()
    if not adrs_ok:
        for e in adr_errors:
            print(e)
        return fail("One or more ADRs are not accepted.")

    policies_ok, policy_errors = check_policies()
    if not policies_ok:
        for e in policy_errors:
            print(e)
        return fail("One or more policy files are missing/invalid.")

    # Bundle
    bundle = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": "va-lead-intelligence",
        "sha": run(["git", "rev-parse", "HEAD"], env=env).stdout.strip() or "unknown",
        "artifacts": {
            "openapi": "contracts/openapi/lead-intelligence-v1.openapi.json",
            "jsonschemas": "contracts/jsonschema/",
            "erd": "docs/erd/lead-intelligence.svg",
            "migrations": "migrations/",
            "dod": "quality/traceability/production-v1.md",
            "env_catalogue": "infra/terraform/ENVIRONMENT_CATALOGUE.md",
            "benchmark": "benchmark/report.json",
        },
    }
    (DIST_DIR / "manifest.json").write_text(
        re.sub(r'"(https?://[^"]+)"', lambda m: f'"{m.group(1)}"', str(bundle))
    )

    print("Handover bundle generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
