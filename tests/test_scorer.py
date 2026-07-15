"""Tests for the lead scoring engine."""

from __future__ import annotations

import pytest

from core.scorer import score


@pytest.fixture
def high_fit_features() -> dict:
    return {
        "employee_count_delta": 0.5,
        "funding_round_recency": 90,
        "revenue_range": "50m-100m",
        "role_skill_match": 0.95,
        "hiring_velocity": 5,
        "job_posting_seniority": 4,
        "stack_extraction": "python, kubernetes, aws",
        "integration_mentions": "salesforce, hubspot",
        "job_skill_requirements": "typescript, graphql, rest",
        "country_code": "US",
        "do_not_contact_list": False,
    }


@pytest.fixture
def low_fit_features() -> dict:
    return {
        "employee_count_delta": -0.1,
        "funding_round_recency": 400,
        "revenue_range": "1m-10m",
        "role_skill_match": 0.1,
        "hiring_velocity": 0,
        "job_posting_seniority": 1,
        "stack_extraction": "php, wordpress",
        "integration_mentions": "none",
        "job_skill_requirements": "none",
        "country_code": "US",
        "do_not_contact_list": False,
    }


def test_high_fit_passes(high_fit_features: dict) -> None:
    result = score(high_fit_features)
    assert result["passed"] is True
    assert result["score"] >= 60


def test_low_fit_fails(low_fit_features: dict) -> None:
    result = score(low_fit_features)
    assert result["passed"] is False
    assert result["score"] < 60


def test_score_determinism(high_fit_features: dict) -> None:
    assert score(high_fit_features) == score(high_fit_features)


def test_benchmark() -> None:
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["python", "scripts/build_benchmark.py"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
