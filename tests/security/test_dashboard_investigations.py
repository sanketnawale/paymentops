"""Phase 2D integration test: dashboard investigation counts are real and tenant-scoped."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from paymentops_api.auth import AuthenticatedClient
from paymentops_api.db.models import Investigation, Organization
from paymentops_api.routers.dashboard import dashboard
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


def _inv(org_id, inv_id: str, source: str, status: str, repair: dict | None) -> Investigation:
    return Investigation(
        investigation_id=inv_id,
        organization_id=org_id,
        demo_case_key="upload" if source == "upload" else "pacs008-missing-town",
        source=source,
        message_version="pacs.008.001.08",
        input_hash="0" * 64,
        status=status,
        repair=repair,
        created_at=datetime.now(UTC),
    )


async def test_dashboard_counts_reflect_db_and_are_tenant_scoped():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org_a = Organization(name="A", public_id="dash-a")
        org_b = Organization(name="B", public_id="dash-b")
        session.add_all([org_a, org_b])
        await session.commit()
        await session.refresh(org_a)
        await session.refresh(org_b)

        session.add_all(
            [
                _inv(
                    org_a.id,
                    "inv-dash-1",
                    "upload",
                    "COMPLETED",
                    {"status": "VALIDATED", "test": {"review_status": "VALIDATED"}},
                ),
                _inv(org_a.id, "inv-dash-2", "demo", "FAILED", None),
                _inv(
                    org_a.id,
                    "inv-dash-3",
                    "upload",
                    "RUNNING",
                    {"status": "REVIEW_REQUIRED", "test": None},
                ),
                _inv(org_b.id, "inv-dash-4", "upload", "COMPLETED", None),
            ]
        )
        await session.commit()

        client_a = AuthenticatedClient("c", str(org_a.id), [], "g")
        data = await dashboard(client=client_a, session=session)
        inv = data["investigations"]
        assert inv["total"] == 3  # org B's row is excluded
        assert inv["completed"] == 1
        assert inv["failed"] == 1
        assert inv["running"] == 1
        assert inv["uploads"] == 2
        assert inv["samples"] == 1
        assert inv["sandbox_tests"] == 1
        assert inv["sandbox_validated"] == 1
        assert inv["review_required"] == 1
    await engine.dispose()
