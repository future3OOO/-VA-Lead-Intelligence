"""Tests for the FastAPI application."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from api.app import app


def _headers(workspace_id: UUID | None = None) -> dict:
    return {
        "x-workspace-id": str(workspace_id or uuid4()),
        "x-api-key": "dev-api-key",
    }


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _create_workspace(client: httpx.AsyncClient) -> str:
    payload = {
        "name": "Acme",
        "slug": "acme",
        "billing_email": "billing@acme.example",
        "plan": "trial",
    }
    response = await client.post("/workspaces/", json=payload, headers=_headers())
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_and_get_workspace(client: httpx.AsyncClient) -> None:
    workspace_id = await _create_workspace(client)
    get = await client.get(f"/workspaces/{workspace_id}", headers=_headers(UUID(workspace_id)))
    assert get.status_code == 200
    assert get.json()["name"] == "Acme"


async def test_unauthorized_request(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/workspaces/", headers={"x-workspace-id": str(uuid4()), "x-api-key": "wrong"}
    )
    assert response.status_code == 401


async def test_create_company_requires_workspace(client: httpx.AsyncClient) -> None:
    workspace_id = await _create_workspace(client)
    payload = {
        "canonical_name": "Acme Corp",
        "primary_domain": "acme.example",
        "country_code": "US",
        "industry": "Software",
        "employee_count": 100,
    }
    response = await client.post("/companies/", json=payload, headers=_headers(UUID(workspace_id)))
    assert response.status_code == 201
    assert response.json()["workspace_id"] == workspace_id


async def test_workspace_isolation(client: httpx.AsyncClient) -> None:
    workspace_a = await _create_workspace(client)
    payload = {
        "canonical_name": "Acme Corp",
        "primary_domain": "acme.example",
        "country_code": "US",
        "industry": "Software",
        "employee_count": 100,
    }
    created = await client.post("/companies/", json=payload, headers=_headers(UUID(workspace_a)))
    company_id = created.json()["id"]

    other_workspace = uuid4()
    get = await client.get(f"/companies/{company_id}", headers=_headers(other_workspace))
    assert get.status_code == 404

    list_resp = await client.get("/companies/", headers=_headers(other_workspace))
    assert list_resp.status_code == 200
    assert list_resp.json() == []


async def test_source_hit_rejects_company_from_another_workspace(
    client: httpx.AsyncClient,
) -> None:
    workspace_a = UUID(await _create_workspace(client))
    workspace_b = UUID(await _create_workspace(client))
    company = await client.post(
        "/companies/",
        json={
            "canonical_name": "Other Workspace Company",
            "primary_domain": "other.example",
            "country_code": "NZ",
            "industry": "Finance",
            "employee_count": 10,
        },
        headers=_headers(workspace_b),
    )
    assert company.status_code == 201
    now = datetime.now(timezone.utc).isoformat()
    response = await client.post(
        "/source-hits/",
        json={
            "company_id": company.json()["id"],
            "source_key": "manual_seed",
            "source_native_id": "cross-workspace",
            "source_url": "https://example.org/source",
            "observed_at": now,
            "published_at": now,
            "title": "Cross-workspace source hit",
            "body_excerpt": "",
            "company_name_raw": "Other Workspace Company",
            "company_domain_raw": "other.example",
            "location_raw": "Auckland, New Zealand",
            "workplace_type": "inferred_remote_friendly",
            "contact_routes_raw": [],
            "content_hash": "cross-workspace",
            "access_policy_version": "source-policy-v1",
        },
        headers=_headers(workspace_a),
    )
    assert response.status_code == 404


async def test_source_run_rejects_campaign_from_another_workspace(
    client: httpx.AsyncClient,
) -> None:
    workspace_a = UUID(await _create_workspace(client))
    workspace_b = UUID(await _create_workspace(client))
    campaign = await client.post(
        "/campaigns/",
        json={
            "name": "Other Workspace Campaign",
            "status": "active",
            "capability_filter": ["virtual_assistant"],
            "score_threshold": 0.5,
        },
        headers=_headers(workspace_b),
    )
    assert campaign.status_code == 201
    now = datetime.now(timezone.utc).isoformat()
    response = await client.post(
        "/source-runs/",
        json={
            "campaign_id": campaign.json()["id"],
            "source_key": "manual_seed",
            "status": "pending",
            "started_at": now,
            "completed_at": now,
            "hits_total": 0,
            "hits_qualified_total": 0,
            "hits_duplicate_total": 0,
            "errors_total": 0,
            "checkpoint": {},
        },
        headers=_headers(workspace_a),
    )
    assert response.status_code == 404


async def test_source_pagination_rejects_negative_values(client: httpx.AsyncClient) -> None:
    workspace_id = UUID(await _create_workspace(client))
    response = await client.get(
        "/source-hits/?skip=-1&limit=0",
        headers=_headers(workspace_id),
    )
    assert response.status_code == 422
