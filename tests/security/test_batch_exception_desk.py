"""Phase 3A security/integration tests: Batch Exception Desk + evidence-gap reporting.

Require PostgreSQL (skipped without TEST_DATABASE_URL). The real engine is used; the Evolus client
is a local fake (no network), so these tests are mocked with respect to the live workflow.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from paymentops_api.db.models import Organization
from paymentops_api.evolus.client import WorkflowExecution, WorkflowRun
from paymentops_api.routers import investigations as investigations_router
from paymentops_api.services import batch_runner
from paymentops_api.services import exception_batch_service as batch_service
from paymentops_api.settings import Settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)

_REPO = Path(__file__).resolve().parents[2]
_MISSING_TOWN = (_REPO / "tests" / "fixtures" / "pacs008" / "missing_town.xml").read_text(
    encoding="utf-8"
)
_VALID = (_REPO / "tests" / "fixtures" / "pacs008" / "valid_structured.xml").read_text(
    encoding="utf-8"
)
_EVIDENCE_INCOMPLETE = json.loads(
    (_REPO / "examples" / "uploads" / "incomplete" / "evidence.json").read_text(encoding="utf-8")
)
_EVIDENCE_COMPLETE = json.loads(
    (_REPO / "examples" / "uploads" / "complete" / "evidence.json").read_text(encoding="utf-8")
)


def _pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )


def _settings() -> Settings:
    return Settings(app_environment="test", metrics_enabled=False)


class FakeEvolus:
    """Duck-typed Evolus client: counts starts, completes immediately on poll."""

    def __init__(self) -> None:
        self.configured = True
        self.start_calls = 0

    async def start_workflow(self, prompt: str) -> WorkflowRun:
        self.start_calls += 1
        return WorkflowRun(execution_id=f"exec-{self.start_calls}", raw={})

    async def get_execution(self, execution_id: str) -> WorkflowExecution:
        return WorkflowExecution(
            status="COMPLETED",
            raw_status="Completed",
            output_text="# Report\nNo structured proposal.",
            result=None,
            raw={},
        )


async def _org(session, public_id: str) -> Organization:
    org = Organization(name=public_id, public_id=public_id)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def test_create_batch_isolates_invalid_items():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-iso")
        items = [
            {"xml": _MISSING_TOWN, "evidence": _EVIDENCE_INCOMPLETE, "filename": "a.xml"},
            {"xml": _VALID, "evidence": None, "filename": "clean.xml"},
            {"xml": "<not-xml", "evidence": None, "filename": "bad.xml"},
        ]
        batch, rows, created = await batch_service.create_batch(session, org.id, items)
        assert created is True
        assert batch.total_items == 3
        assert rows[0].status == "PENDING"
        assert rows[1].status == "PENDING"
        assert rows[2].status == "REJECTED"
        assert rows[2].error and "rejected" in rows[2].error.lower()
        # A rejected item does not stop the others and is not stored as a payload.
        assert rows[2].payload_xml is None
        assert rows[0].payload_xml is not None
        assert rows[2].display_filename == "bad.xml"
    await engine.dispose()


async def test_batch_max_five_items():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-max")
        items = [{"xml": _VALID, "evidence": None} for _ in range(6)]
        with pytest.raises(batch_service.BatchValidationError):
            await batch_service.create_batch(session, org.id, items)
    await engine.dispose()


async def test_batch_idempotency_returns_same_batch():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-idem")
        items = [{"xml": _MISSING_TOWN, "evidence": None}]
        first, _rows, created1 = await batch_service.create_batch(
            session, org.id, items, idempotency_key="key-1"
        )
        second, _rows2, created2 = await batch_service.create_batch(
            session, org.id, items, idempotency_key="key-1"
        )
        assert created1 is True and created2 is False
        assert first.batch_id == second.batch_id
    await engine.dispose()


async def test_batch_tenant_isolation():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org_a = await _org(session, "batch-tenant-a")
        org_b = await _org(session, "batch-tenant-b")
        batch, _rows, _ = await batch_service.create_batch(
            session, org_a.id, [{"xml": _VALID, "evidence": None}]
        )
        with pytest.raises(LookupError):
            await batch_service.get_batch(session, org_b.id, batch.batch_id)
        with pytest.raises(LookupError):
            await batch_service.build_export(session, org_b.id, batch.batch_id)
        got, _items = await batch_service.get_batch(session, org_a.id, batch.batch_id)
        assert got.batch_id == batch.batch_id
    await engine.dispose()


async def test_runner_starts_once_then_completes_sequentially():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-runner")
        batch, rows, _ = await batch_service.create_batch(
            session, org.id, [{"xml": _MISSING_TOWN, "evidence": None}]
        )
        client = FakeEvolus()
        kwargs = {
            "settings": _settings(),
            "pipeline": _pipeline(),
            "registry": build_default_registry(),
            "evolus_client": client,
        }
        assert await batch_runner.process_once(session, **kwargs) is True  # start
        await session.refresh(rows[0])
        assert client.start_calls == 1
        assert rows[0].investigation_id is not None
        # Second tick polls to terminal; the workflow is NOT started again.
        assert await batch_runner.process_once(session, **kwargs) is True  # poll
        await session.refresh(rows[0])
        await session.refresh(batch)
        assert client.start_calls == 1
        assert rows[0].status == "COMPLETED"
        assert batch.status == "COMPLETED"
    await engine.dispose()


async def test_recovery_marks_ambiguous_start_failed_without_retry():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-recover")
        _batch, rows, _ = await batch_service.create_batch(
            session, org.id, [{"xml": _MISSING_TOWN, "evidence": None}]
        )
        rows[0].status = "STARTING"
        session.add(rows[0])
        await session.commit()
        count = await batch_runner.recover_interrupted_starts(session)
        assert count >= 1
        await session.refresh(rows[0])
        assert rows[0].status == "FAILED"
        assert rows[0].error and "ambiguous" in rows[0].error.lower()
        # A later process_once must not start a new workflow for the ambiguous item.
        client = FakeEvolus()
        await batch_runner.process_once(
            session,
            settings=_settings(),
            pipeline=_pipeline(),
            registry=build_default_registry(),
            evolus_client=client,
        )
        assert client.start_calls == 0
    await engine.dispose()


async def test_evidence_gaps_show_server_derived_when_agent_empty():
    """Server-derived gaps remain visible even when the agent supplies an empty structured list."""
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "gaps-agent-empty")
        from paymentops_api.services import investigation_service as inv_svc

        inv = await inv_svc.start_uploaded_investigation(
            session,
            str(org.id),
            _MISSING_TOWN.encode("utf-8"),
            _EVIDENCE_INCOMPLETE,
            settings=_settings(),
            pipeline=_pipeline(),
            registry=build_default_registry(),
            evolus_client=FakeEvolus(),  # type: ignore[arg-type]
            start_workflow=False,
        )
        # Simulate a completed agent run that supplied an EMPTY structured gap list.
        inv.repair = {
            "status": "PROPOSED",
            "proposal": {
                "status": "PROPOSED",
                "missing_evidence": [],
                "missing_evidence_present": True,
                "server_validation": {"allowed": [], "rejected": []},
            },
        }
        session.add(inv)
        await session.commit()

        gaps = investigations_router._evidence_gaps(inv)
        assert gaps["agent_reported"] == []
        assert gaps["agent_reported_status"] == "PROVIDED"
        # The creditor finding has no supporting-record entry -> a server-derived gap remains.
        assert any(g["party"] == "Cdtr" for g in gaps["server_derived"])
        assert gaps["supporting_record"]  # the record's own gap is preserved separately
    await engine.dispose()


async def test_export_distinguishes_proposed_from_tested():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-export")
        batch, _rows, _ = await batch_service.create_batch(
            session, org.id, [{"xml": _MISSING_TOWN, "evidence": None}]
        )
        report = await batch_service.build_export(session, org.id, batch.batch_id)
        assert report["synthetic"] is True
        assert report["batch"]["batch_id"] == batch.batch_id
        item = report["items"][0]
        assert "proposed_changes" in item and "applied_changes" in item
        assert item["input_hash"]
        assert "evolus_execution_id" in item
        # No secrets or model reasoning leak into the export.
        blob = json.dumps(report)
        assert "api_key" not in blob.lower()
        assert "reasoning" not in blob.lower()
    await engine.dispose()


async def test_export_validation_and_sandbox_semantics():
    """Export must state validation_performed and sandbox_review_status explicitly.

    Rejected uploads are never inferred as evaluated; a clean, evaluated original can have
    validation_performed=true while sandbox_tested=false.
    """
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "batch-semantics")
        items = [
            {"xml": _MISSING_TOWN, "evidence": _EVIDENCE_COMPLETE, "filename": "complete.xml"},
            {"xml": _VALID, "evidence": None, "filename": "clean.xml"},
            {"xml": "<not-xml", "evidence": None, "filename": "bad.xml"},
        ]
        batch, rows, _ = await batch_service.create_batch(session, org.id, items)
        client = FakeEvolus()
        kwargs = {
            "settings": _settings(),
            "pipeline": _pipeline(),
            "registry": build_default_registry(),
            "evolus_client": client,
        }
        for _ in range(8):
            await batch_runner.process_once(session, **kwargs)
            await session.refresh(batch)
            if batch.status in {"COMPLETED", "PARTIAL", "FAILED"}:
                break

        # Persist a sandbox test on the first (complete-evidence) item.
        invs = await batch_service.load_investigations(session, rows)
        inv0 = invs[rows[0].investigation_id or ""]
        inv0.repair = {"status": "VALIDATED", "test": {"review_status": "VALIDATED"}}
        session.add(inv0)
        await session.commit()

        export = await batch_service.build_export(session, org.id, batch.batch_id)
        by_index = {i["item_index"]: i for i in export["items"]}

        complete = by_index[0]
        assert complete["validation_performed"] is True
        assert complete["sandbox_review_status"] == "VALIDATED"
        assert complete["sandbox_tested"] is True

        clean = by_index[1]
        assert clean["validation_performed"] is True
        assert clean["sandbox_review_status"] is None
        assert clean["sandbox_tested"] is False

        malformed = by_index[2]
        assert malformed["status"] == "REJECTED"
        assert malformed["validation_performed"] is False
        assert malformed["sandbox_review_status"] is None
        assert malformed["sandbox_tested"] is False
    await engine.dispose()
