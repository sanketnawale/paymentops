"""Tenant isolation security tests (require a real PostgreSQL; skipped otherwise)."""

from __future__ import annotations

import os

import pytest
from paymentops_api.db.models import (
    Organization,
)
from paymentops_api.services import integration_service
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


async def test_org_a_cannot_read_org_b_profile():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org_a, org_b, profile_a = await _seed(session)
        # Org B tries to read Org A's profile -> must raise (tenant scoping).
        with pytest.raises(LookupError):
            await integration_service.get_profile(session, str(org_b.id), profile_a.id)
        # Org A reads its own profile -> OK.
        p = await integration_service.get_profile(session, str(org_a.id), profile_a.id)
        assert p.name == "A"
    await engine.dispose()
