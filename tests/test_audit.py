"""Tests for the audit trail."""
from __future__ import annotations

from uuid import uuid4

from db.models import AuditEvent, Workspace
from db.session import AsyncSessionLocal


async def test_audit_event() -> None:
    async with AsyncSessionLocal() as session:
        workspace = Workspace(
            name="Audit Test",
            slug="audit-test",
            billing_email="audit@example.com",
            plan="trial",
        )
        session.add(workspace)
        await session.flush()

        event = AuditEvent(
            workspace_id=workspace.id,
            actor_id=uuid4(),
            action="test",
            resource_type="workspace",
            resource_id=uuid4(),
            payload={"reason": "test"},
        )
        session.add(event)
        await session.commit()
        assert event.id is not None
