"""Tests for the FastAPI application."""

from __future__ import annotations

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
