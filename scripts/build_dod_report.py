#!/usr/bin/env python3
"""Build a requirement-to-test traceability (DOD) report."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


def load_requirements(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def load_junit(junit_path: Path) -> dict[str, str]:
    if not junit_path.exists():
        return {}
    tree = ET.parse(junit_path)
    root = tree.getroot()
    statuses: dict[str, str] = {}
    for testcase in root.iter("testcase"):
        name = testcase.get("name", "")
        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")
        if failure is not None:
            statuses[name] = "failed"
        elif error is not None:
            statuses[name] = "error"
        elif skipped is not None:
            statuses[name] = "skipped"
        else:
            statuses[name] = "passed"
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    reqs = load_requirements(args.requirements)
    statuses = load_junit(args.junit)

    lines = [f"# DOD Traceability Report — {reqs.get('project', 'Unknown')}", ""]
    lines.append("| Requirement | Title | Tests | Status | Evidence |")
    lines.append("|-------------|-------|-------|--------|----------|")

    blocking: list[str] = []
    for req in reqs.get("requirements", []):
        tests = req.get("tests", [])
        if tests:
            status = "passed"
            for test in tests:
                if statuses.get(test, "missing") != "passed":
                    status = "blocked"
                    blocking.append(f"{req['id']} ({test}: {statuses.get(test, 'missing')})")
            evidence = ", ".join(f"`{t}`" for t in tests)
        else:
            req_status = req.get("status", "")
            verification = req.get("verification", "")
            if req_status != "implemented" or not verification:
                status = "blocked"
                blocking.append(
                    f"{req['id']} (status={req_status or 'missing'}, verification={verification or 'missing'})"
                )
            else:
                status = "passed"
            evidence = verification or ""
        lines.append(f"| {req['id']} | {req['title']} | {len(tests)} | {status} | {evidence} |")

    lines.extend(["", "## Blockers"])
    if blocking:
        for item in blocking:
            lines.append(f"- {item}")
    else:
        lines.append("No blocking items.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    print(f"DOD report written to {args.output}")
    if blocking:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
