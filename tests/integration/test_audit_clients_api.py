"""Tenant isolation tests for the audit trail and API-client list (require PostgreSQL)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from paymentops_api.db.models import ApiClient, AuditEvent, Organization
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


async def _seed(session):
    org_a = Organization(name="Org A", public_id="audit-a")
    org_b = Organization(name="Org B", public_id="audit-b")
    session.add_all([org_a, org_b])
    await session.commit()
    await session.refresh(org_a)
    await session.refresh(org_b)
    session.add(
        AuditEvent(
            organization_id=org_a.id,
            case_id="case-a",
            event_type="case.approve",
            created_at=datetime.now(UTC),
        )
    )
    session.add(
        ApiClient(
            client_id="cn_audit_a",
            secret_hash="x$y",
            organization_id=org_a.id,
            allowed_profiles=[],
            status="ACTIVE",
        )
    )
    await session.commit()
    return org_a, org_b


async def test_audit_and_clients_are_tenant_scoped():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org_a, org_b = await _seed(session)
        # Org A sees its own audit event and client.
        a_events = await session.execute(
            select(AuditEvent).where(AuditEvent.organization_id == org_a.id)
        )
        assert len(list(a_events.scalars().all())) >= 1
        # Org B sees none of Org A's audit events.
        b_events = await session.execute(
            select(AuditEvent).where(AuditEvent.organization_id == org_b.id)
        )
        assert list(b_events.scalars().all()) == []
        b_clients = await session.execute(
            select(ApiClient).where(ApiClient.organization_id == org_b.id)
        )
        assert list(b_clients.scalars().all()) == []
    await engine.dispose()
