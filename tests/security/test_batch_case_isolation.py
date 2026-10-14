"""Batch + case tenant isolation and operator-state tests (require PostgreSQL; skipped)."""

from __future__ import annotations

import os

import pytest
from paymentops_api.db.models import Organization, PaymentCase
from paymentops_api.services import batch_service, case_service, integration_service
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from integration_profiles.models import InputFormat, IntegrationProfile
from mapping_engine.models import FieldMapping, MappingDefinition, SourceFormat

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


async def _seed(session):
    org_a = Organization(name="Org A", public_id="org-a")
    org_b = Organization(name="Org B", public_id="org-b")
    session.add_all([org_a, org_b])
    await session.commit()
    await session.refresh(org_a)
    await session.refresh(org_b)

    mapping = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.JSON,
        record_selector="$.p[*]",
        fields=[FieldMapping(source="$.id", target="instruction_id")],
    )
    profile_a = await integration_service.create_profile(
        session,
        str(org_a.id),
        IntegrationProfile(
            organization_id=str(org_a.id), name="A", input_format=InputFormat.JSON, mapping=mapping
        ),
    )
    return org_a, org_b, profile_a


async def test_org_b_cannot_read_org_a_batch():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org_a, org_b, profile_a = await _seed(session)
        job = await batch_service.create_batch_job(session, str(org_a.id), str(profile_a.id), 1)
        # Org B cannot read Org A's batch.
        with pytest.raises(LookupError):
            await batch_service.get_job(session, str(org_b.id), str(job.id))
        # Org A reads its own batch.
        got = await batch_service.get_job(session, str(org_a.id), str(job.id))
        assert got.status == "QUEUED"
    await engine.dispose()


async def test_org_b_cannot_read_org_a_case_and_transitions():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org_a, org_b, profile_a = await _seed(session)
        case = PaymentCase(case_id="case-x", organization_id=org_a.id, status="NEW")
        session.add(case)
        await session.commit()

        with pytest.raises(LookupError):
            await case_service.get_case(session, str(org_b.id), "case-x")

        # Approve then re-approve (already closed) -> ValueError.
        await case_service.transition_case(
            session, str(org_a.id), "case-x", "approve", operator="op", note=None
        )
        with pytest.raises(ValueError):
            await case_service.transition_case(
                session, str(org_a.id), "case-x", "reject", operator="op", note=None
            )
        # Unsupported action -> ValueError.
        with pytest.raises(ValueError):
            await case_service.transition_case(
                session, str(org_a.id), "case-x", "destroy", operator="op", note=None
            )
    await engine.dispose()
