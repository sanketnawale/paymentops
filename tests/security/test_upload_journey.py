"""Phase 2C integration tests: the upload journey (require PostgreSQL).

The real engine is used; no Evolus/AMD calls. Skipped without TEST_DATABASE_URL.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from paymentops_api.db.models import Organization
from paymentops_api.evolus import EvolusClient
from paymentops_api.services import investigation_service as inv_svc
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
_MISSING_TOWN = (_REPO / "tests" / "fixtures" / "pacs008" / "missing_town.xml").read_bytes()
_VALID = (_REPO / "tests" / "fixtures" / "pacs008" / "valid_structured.xml").read_bytes()
_EVIDENCE_COMPLETE = json.loads(
    (_REPO / "examples" / "uploads" / "complete" / "evidence.json").read_text(encoding="utf-8")
)


def _pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )


async def _org(session, public_id: str) -> Organization:
    org = Organization(name=public_id, public_id=public_id)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def _upload(session, org, xml, evidence=None):
    settings = Settings(app_environment="test", metrics_enabled=False)
    return await inv_svc.start_uploaded_investigation(
        session,
        str(org.id),
        xml,
        evidence,
        settings=settings,
        pipeline=_pipeline(),
        registry=build_default_registry(),
        evolus_client=EvolusClient(settings),
        start_workflow=False,
    )


async def test_upload_stores_payload_and_tool_uses_uploaded_content():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "upload-a")
        inv = await _upload(session, org, _MISSING_TOWN, _EVIDENCE_COMPLETE)
        assert inv.source == "upload"
        assert inv.demo_case_key == "upload"

        # No stored-demo substitution: the tool validates the uploaded content, not a fixture.
        payload = await inv_svc.validate_case_for_tool(
            session,
            Settings(app_environment="test", metrics_enabled=False),
            case_ref=inv.investigation_id,
            pipeline=_pipeline(),
            registry=build_default_registry(),
        )
        assert payload["input"]["identity_sha256"] == inv.input_hash
        assert payload["input"]["case_origin"] == "user-uploaded synthetic payload"
        assert any(f["rule_id"] == "ADR-001" for f in payload["validation"]["findings"])

        # Immutability: stored payload round-trips to the exact bytes and hash.
        loaded = inv_svc._load_payload(inv)
        assert loaded == _MISSING_TOWN
        assert inv_svc.payload_sha256(loaded) == inv.input_hash
    await engine.dispose()


async def test_changing_xml_changes_hash_and_findings():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "upload-b")
        missing = await _upload(session, org, _MISSING_TOWN, None)
        valid = await _upload(session, org, _VALID, None)
        assert missing.input_hash != valid.input_hash
        assert "ADR-001" in {
            f["rule_id"] for f in (missing.deterministic_findings or {}).get("rule_findings") or []
        }
        assert "ADR-001" not in {
            f["rule_id"] for f in (valid.deterministic_findings or {}).get("rule_findings") or []
        }
    await engine.dispose()


async def test_upload_rejections():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org = await _org(session, "upload-c")
        # Malformed XML.
        with pytest.raises(Exception):
            await _upload(session, org, b"<not-xml", None)
        # Unsupported version (wrong namespace).
        with pytest.raises(Exception):
            await _upload(
                session, org, _VALID.replace(b"pacs.008.001.08", b"pacs.008.001.09"), None
            )
        # Multi-transaction.
        tx = _MISSING_TOWN.split(b"<CdtTrfTxInf>")[1].split(b"</CdtTrfTxInf>")[0]
        multi = _MISSING_TOWN.replace(
            b"</FIToFICstmrCdtTrf>",
            b"<CdtTrfTxInf>" + tx + b"</CdtTrfTxInf></FIToFICstmrCdtTrf>",
        )
        with pytest.raises(inv_svc.UploadValidationError):
            await _upload(session, org, multi, None)
        # Invalid evidence schema.
        with pytest.raises(ValueError):
            await _upload(
                session,
                org,
                _MISSING_TOWN,
                {"entries": [{"ref": "x", "party": "Hacker", "field": "TwnNm", "value": "y"}]},
            )
        # Oversize XML.
        with pytest.raises(inv_svc.UploadValidationError):
            await _upload(session, org, b"<a>" + b"x" * (inv_svc.UPLOAD_MAX_XML_BYTES + 1), None)
    await engine.dispose()


async def test_uploaded_case_is_tenant_scoped():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org_a = await _org(session, "upload-tenant-a")
        org_b = await _org(session, "upload-tenant-b")
        inv = await _upload(session, org_a, _MISSING_TOWN, None)
        with pytest.raises(LookupError):
            await inv_svc.get_investigation(session, str(org_b.id), inv.investigation_id)
        # Owner can read it.
        got = await inv_svc.get_investigation(session, str(org_a.id), inv.investigation_id)
        assert got.investigation_id == inv.investigation_id
    await engine.dispose()
