"""Phase 2B integration tests for the sandbox repair service (require PostgreSQL).

These exercise the REAL engine and DB; they are skipped without TEST_DATABASE_URL.
"""

from __future__ import annotations

import os

import pytest
from paymentops_api.db.models import AuditEvent, Investigation, Organization
from paymentops_api.evolus.demo_cases import get_demo_case
from paymentops_api.services import investigation_service as inv_svc
from paymentops_api.services import repair_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


def _pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )


async def _make_investigation(
    session, case_key: str, changes: list[dict[str, str]]
) -> Investigation:
    org = Organization(name="Repair Org", public_id=f"repair-{case_key}")
    session.add(org)
    await session.commit()
    await session.refresh(org)
    demo = get_demo_case(case_key)
    pipeline = _pipeline()
    result = inv_svc.run_deterministic_validation(
        demo.load(), pipeline=pipeline, registry=build_default_registry()
    )
    inv = Investigation(
        investigation_id=f"inv-{case_key[:10]}",
        organization_id=org.id,
        demo_case_key=case_key,
        message_version=result.message_version or demo.message_version,
        input_hash=inv_svc.payload_sha256(demo.load()),
        ruleset_version="cloudnova-address-v1",
        engine_version=result.engine_version,
        status="COMPLETED",
        deterministic_findings=inv_svc.deterministic_record(result),
        supporting_record=(demo.supporting_record.to_dict() if demo.supporting_record else None),
        repair={"status": "PROPOSED", "proposal": {"status": "PROPOSED", "changes": changes}},
    )
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    return inv


async def test_repair_validates_and_revalidates_sandbox():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        inv = await _make_investigation(
            session,
            "pacs008-missing-town",
            [
                {
                    "target": "Dbtr/PstlAdr/TwnNm",
                    "value": "Milano",
                    "evidence_ref": "SR-1:debtor-town",
                },
                {
                    "target": "Cdtr/PstlAdr/TwnNm",
                    "value": "Roma",
                    "evidence_ref": "SR-1:creditor-town",
                },
            ],
        )
        original_hash = inv.input_hash
        inv = await repair_service.test_repair(
            session, inv, pipeline=_pipeline(), registry=build_default_registry()
        )
        repair = inv.repair or {}
        test = repair["test"]
        assert repair["status"] == "VALIDATED"
        assert test["review_status"] == "VALIDATED"
        assert test["xsd_valid"] is True
        assert test["sandbox_hash"] and test["sandbox_hash"] != original_hash
        assert test["original_hash"] == original_hash
        # ADR-001 is resolved in the sandbox.
        assert "ADR-001" not in {f["rule_id"] for f in test["after_findings"]}
        # Original payload was never mutated (same bytes/hash).
        assert get_demo_case("pacs008-missing-town").sha256 == original_hash

        events = await session.execute(
            select(AuditEvent).where(
                AuditEvent.case_id == inv.investigation_id,
                AuditEvent.event_type == "repair.test",
            )
        )
        assert len(list(events.scalars().all())) == 1
    await engine.dispose()


async def test_repair_rejects_invented_value():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        inv = await _make_investigation(
            session,
            "pacs008-missing-town",
            [
                {
                    "target": "Dbtr/PstlAdr/TwnNm",
                    "value": "Torino",
                    "evidence_ref": "SR-1:debtor-town",
                }
            ],
        )
        inv = await repair_service.test_repair(
            session, inv, pipeline=_pipeline(), registry=build_default_registry()
        )
        repair = inv.repair or {}
        assert repair["status"] == "REJECTED"
        assert repair["test"] is None
        assert repair["rejected_changes"][0]["reason"] == (
            "proposed value does not match the recorded evidence value"
        )
    await engine.dispose()


async def test_repair_rejects_unsupported_path():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        inv = await _make_investigation(
            session,
            "pacs008-missing-town",
            [{"target": "Dbtr/PstlAdr/StrtNm", "value": "X", "evidence_ref": "SR-1:debtor-town"}],
        )
        inv = await repair_service.test_repair(
            session, inv, pipeline=_pipeline(), registry=build_default_registry()
        )
        repair = inv.repair or {}
        assert repair["status"] == "REJECTED"
        assert "allowlisted" in repair["rejected_changes"][0]["reason"]
    await engine.dispose()


async def test_incomplete_evidence_requires_review_no_invented_town():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Agent tries to invent the creditor town from the incomplete record.
        inv = await _make_investigation(
            session,
            "pacs008-missing-town-incomplete",
            [
                {
                    "target": "Dbtr/PstlAdr/TwnNm",
                    "value": "Milano",
                    "evidence_ref": "SR-2:debtor-town",
                },
                {
                    "target": "Cdtr/PstlAdr/TwnNm",
                    "value": "Roma",
                    "evidence_ref": "SR-2:creditor-town",
                },
            ],
        )
        inv = await repair_service.test_repair(
            session, inv, pipeline=_pipeline(), registry=build_default_registry()
        )
        repair = inv.repair or {}
        # Only the debtor change is allowed; the creditor change is rejected -> human review.
        assert repair["status"] == "REVIEW_REQUIRED"
        rejected = {r["target"] for r in repair["rejected_changes"]}
        assert "Cdtr/PstlAdr/TwnNm" in rejected
        # A remaining ADR-001 (creditor town) is surfaced as a remaining issue.
        assert any(
            f["rule_id"] == "ADR-001" and f["target"] == "Cdtr/PstlAdr"
            for f in repair["test"]["after_findings"]
        )
    await engine.dispose()
