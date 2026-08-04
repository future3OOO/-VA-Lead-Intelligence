"""Tests for documentation and governance artifacts."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_adrs_accepted() -> None:
    adr_dir = REPO_ROOT / "docs" / "adr"
    adrs = list(adr_dir.glob("ADR-*.md"))
    assert len(adrs) >= 1
    for path in adrs:
        assert "accepted" in path.read_text().lower(), f"{path} is not accepted"


def test_runbooks_exist() -> None:
    runbook_dir = REPO_ROOT / "docs" / "runbooks"
    required = [
        "incident-response.md",
        "rollback.md",
        "deployment.md",
        "crawler-operations.md",
        "scoring-tuning.md",
    ]
    for name in required:
        assert (runbook_dir / name).exists(), f"Missing runbook: {name}"


def test_readme_lists_every_configured_openstreetmap_tag() -> None:
    registry = yaml.safe_load(
        (REPO_ROOT / "config" / "sources" / "source-registry.yaml").read_text()
    )
    tags = registry["sources"]["openstreetmap"]["adapter_config"]["tags"]
    readme = (REPO_ROOT / "README.md").read_text()

    assert len(tags) == 16
    for tag in tags:
        row = f"| `{tag['key']}` | `{tag['value']}` | {tag['title']} | {tag['category']} |"
        assert readme.count(row) == 1

    for detail in (
        "https://z.overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "operator` tag is retained as listing context only",
        "`branch` or `addr:suburb` value is appended",
        "Latitude/longitude is used when no address is available",
        "a website remains company metadata",
        "0.2 requests/second",
        "bounded per-request and overall query",
    ):
        assert detail in readme
