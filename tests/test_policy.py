"""Tests for the source and jurisdiction policy engine."""
from __future__ import annotations

from core.policy_engine import evaluate_jurisdiction, evaluate_source


def test_allowed_source() -> None:
    result = evaluate_source("linkedin_public")
    assert result["allowed"] is True


def test_prohibited_source() -> None:
    result = evaluate_source("dark_web")
    assert result["allowed"] is False


def test_allowed_jurisdiction() -> None:
    result = evaluate_jurisdiction("US")
    assert result["allowed"] is True


def test_blocked_jurisdiction() -> None:
    result = evaluate_jurisdiction("CN")
    assert result["allowed"] is False


def test_unknown_jurisdiction_uses_default() -> None:
    result = evaluate_jurisdiction("FR")
    assert "reason" in result


def test_source_policy() -> None:
    assert evaluate_source("linkedin_public")["allowed"] is True
    assert evaluate_source("dark_web")["allowed"] is False


def test_jurisdiction_policy() -> None:
    assert evaluate_jurisdiction("US")["allowed"] is True
    assert evaluate_jurisdiction("CN")["allowed"] is False
