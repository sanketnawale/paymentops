"""Week 6 account-reconciliation golden tests (require PostgreSQL; skipped otherwise)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from paymentops_api.db.models import Organization
from paymentops_api.services import account_service, iso_analysis_service, lifecycle_service
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "iso"
REG = build_default_registry()
PIPELINE = AnalysisPipeline(
    address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
)


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


async def _seed_org(session, public_id: str):
    org = Organization(name=public_id, public_id=public_id)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def _analyze(session, org: str, name: str):
    return await iso_analysis_service.analyze_iso_message(
        session, org, _load(name), registry=REG, pipeline=PIPELINE
    )


async def test_case_a_complete_customer_payment_reconciled():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "acct-a")
        oid = str(org.id)
        await _analyze(session, oid, "pain001-00113-valid-single.xml")
        await _analyze(session, oid, "pacs008-00108-lifecycle.xml")
        await _analyze(session, oid, "pacs002-00116-accepted.xml")
        await _analyze(session, oid, "camt054-00114-valid-debit.xml")
        await _analyze(session, oid, "camt053-00114-valid.xml")

        lifecycles = await lifecycle_service.list_lifecycles(session, oid)
        assert len(lifecycles) == 1
        entries = await account_service.list_account_entries(session, oid)
        assert len(entries) == 2  # camt.054 + camt.053
        statuses = {e.reconciliation_status for e in entries}
        assert "RECONCILED" in statuses
    await engine.dispose()


async def test_case_c_missing_account_event_detected():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "acct-c")
        oid = str(org.id)
        await _analyze(session, oid, "pain001-00113-valid-single.xml")
        await _analyze(session, oid, "pacs002-00116-accepted.xml")
        flagged = await account_service.detect_missing_account_events(session, oid, window_hours=0)
        assert len(flagged) == 1
    await engine.dispose()


async def test_case_d_amount_mismatch_not_reconciled():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "acct-d")
        oid = str(org.id)
        await _analyze(session, oid, "pain001-00113-valid-single.xml")
        await _analyze(session, oid, "camt054-00114-amount-mismatch.xml")
        entries = await account_service.list_account_entries(session, oid)
        assert any(e.reconciliation_status == "AMOUNT_MISMATCH" for e in entries)
    await engine.dispose()


async def test_case_e_duplicate_account_entry():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "acct-e")
        oid = str(org.id)
        await _analyze(session, oid, "pain001-00113-valid-single.xml")
        await _analyze(session, oid, "camt054-00114-valid-debit.xml")
        # A different message (distinct MsgId) repeating the same entry identity.
        await _analyze(session, oid, "camt054-00114-duplicate.xml")
        entries = await account_service.list_account_entries(session, oid)
        assert any(e.reconciliation_status == "DUPLICATE_ACCOUNT_ENTRY" for e in entries)
    await engine.dispose()


async def test_case_f_out_of_order_resolves():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "acct-f")
        oid = str(org.id)
        # camt first -> unmatched
        await _analyze(session, oid, "camt054-00114-valid-debit.xml")
        entries = await account_service.list_account_entries(session, oid)
        assert entries[0].reconciliation_status == "UNMATCHED_ACCOUNT_ENTRY"
        # later the payment arrives and creates the lifecycle (account event not auto-relinked here)
        await _analyze(session, oid, "pain001-00113-valid-single.xml")
        lifecycles = await lifecycle_service.list_lifecycles(session, oid)
        assert len(lifecycles) == 1
    await engine.dispose()


async def test_case_g_tenant_isolation():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org_a = await _seed_org(session, "acct-iso-a")
        org_b = await _seed_org(session, "acct-iso-b")
        a_id = str(org_a.id)
        b_id = str(org_b.id)
        await _analyze(session, a_id, "camt053-00114-valid.xml")
        reports = await account_service.list_account_reports(session, a_id)
        assert len(reports) == 1
        # Org B cannot see Org A's report.
        with pytest.raises(LookupError):
            await account_service.get_account_report(session, b_id, str(reports[0].id))
        entries = await account_service.list_account_entries(session, a_id)
        with pytest.raises(LookupError):
            await account_service.get_account_entry(session, b_id, str(entries[0].id))
    await engine.dispose()
