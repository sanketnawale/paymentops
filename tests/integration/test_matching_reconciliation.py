"""Reconciliation run integration tests (require PostgreSQL; skipped otherwise).

Covers one-to-many ambiguity, many-to-one ambiguity, duplicate candidates, and tenant
isolation for reconciliation data.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest
from paymentops_api.db.models import Organization
from paymentops_api.services import matching_service
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from matching_engine import MatchRecord, RecordType, default_policy

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


def _inv(rid: str, ref: str, amount: str, cname: str) -> MatchRecord:
    return MatchRecord(
        record_id=rid,
        record_type=RecordType.INVOICE,
        organization_id="org-a",
        amount=Decimal(amount),
        currency="EUR",
        remittance_reference=ref,
        creditor_name=cname,
        value_date=date(2026, 1, 10),
    )


def _pay(rid: str, ref: str, amount: str, cname: str) -> MatchRecord:
    return MatchRecord(
        record_id=rid,
        record_type=RecordType.PAYMENT,
        organization_id="org-a",
        amount=Decimal(amount),
        currency="EUR",
        remittance_reference=ref,
        creditor_name=cname,
        value_date=date(2026, 1, 10),
    )


async def _seed_org(session, public_id: str):
    org = Organization(name=public_id, public_id=public_id)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def _make_run(session, org, source: list[MatchRecord], cands: list[MatchRecord]):
    for r in source + cands:
        await matching_service.create_match_record(session, str(org.id), r)
    run = await matching_service.create_reconciliation_run(
        session,
        str(org.id),
        source_dataset={"record_ids": [r.record_id for r in source]},
        candidate_dataset={"record_ids": [r.record_id for r in cands]},
        policy_id=None,
    )
    return await matching_service.execute_reconciliation(
        session,
        str(org.id),
        str(run.id),
        source_records=source,
        candidate_records=cands,
        policy=default_policy(str(org.id)),
    )


async def test_duplicate_candidate_detected():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "dup-org")
        source = [_inv("inv-a", "INV-92881", "12500", "ACME INDUSTRIA SPA")]
        cands = [
            _pay("pay-1", "INV92881", "12500", "ACME INDUSTRIA S.P.A."),
            _pay("pay-2", "INV92881", "12500", "ACME INDUSTRIA SPA"),
        ]
        run = await _make_run(session, org, source, cands)
        assert run.duplicate_candidate == 1
        cands_rows = await matching_service.list_run_candidates(session, str(org.id), str(run.id))
        assert cands_rows[0].classification == "DUPLICATE_CANDIDATE"
    await engine.dispose()


async def test_many_to_one_ambiguity_routed_to_review():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "mto-org")
        source = [
            _inv("inv-d", "INV-9", "500", "GAMMA"),
            _inv("inv-e", "INV-9", "500", "GAMMA"),
        ]
        cands = [_pay("pay-4", "INV-9", "500", "GAMMA")]
        run = await _make_run(session, org, source, cands)
        # One source claims the single candidate (matched); the other hits many-to-one review.
        assert run.matched == 1
        assert run.review_required == 1
    await engine.dispose()


async def test_cross_tenant_reconciliation_isolated():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org_a = await _seed_org(session, "iso-a")
        org_b = await _seed_org(session, "iso-b")
        source = [_inv("inv-x", "INV-1", "100", "DELTA")]
        cands = [_pay("pay-x", "INV-1", "100", "DELTA")]
        run = await _make_run(session, org_a, source, cands)
        # Org B cannot read Org A's run.
        with pytest.raises(LookupError):
            await matching_service.get_run(session, str(org_b.id), str(run.id))
    await engine.dispose()
