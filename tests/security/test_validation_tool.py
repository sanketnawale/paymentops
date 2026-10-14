"""Security tests for the inbound Evolus validation tool.

Two groups:

- HTTP authentication tests (no database required).
- End-to-end validation / tenant-scope tests against a real PostgreSQL (skipped when
  ``TEST_DATABASE_URL`` is unset). These use the REAL deterministic engine.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from paymentops_api.app.factory import create_app
from paymentops_api.db.models import Organization
from paymentops_api.evolus import EvolusClient
from paymentops_api.services import investigation_service as svc
from paymentops_api.settings import Settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset

_TOOL_PATH = "/api/v1/evolus/tools/validate-case"


def _http_app(**overrides: object) -> TestClient:
    base: dict[str, object] = {
        "app_environment": "test",
        "metrics_enabled": False,
        "ready_checks": [],
        "database_password": "test-only-fake",
        "evolus_tool_api_key": "tool-secret",
    }
    base.update(overrides)
    return TestClient(create_app(Settings(**base)))


def test_tool_returns_503_when_not_configured():
    with _http_app(evolus_tool_api_key=None) as client:
        response = client.post(_TOOL_PATH, json={"case_ref": "inv-x"})
    assert response.status_code == 503


def test_tool_rejects_missing_credential():
    with _http_app() as client:
        response = client.post(_TOOL_PATH, json={"case_ref": "inv-x"})
    assert response.status_code == 401


def test_tool_rejects_wrong_credential():
    with _http_app() as client:
        response = client.post(
            _TOOL_PATH, json={"case_ref": "inv-x"}, headers={"X-Tool-Key": "nope"}
        )
    assert response.status_code == 401


def _pipeline() -> AnalysisPipeline:
    return AnalysisPipeline(
        address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
async def test_tool_validates_real_case_and_enforces_tenant_scope():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        app_environment="test",
        metrics_enabled=False,
        evolus_tool_api_key="tool-secret",
        evolus_demo_org_public_id="vt-org-a",
    )
    # Not-configured Evolus client: starting a workflow records a visible FAILED state.
    evolus = EvolusClient(settings)
    pipeline = _pipeline()
    registry = build_default_registry()

    async with session_factory() as session:
        org_a = Organization(name="VT Org A", public_id="vt-org-a")
        org_b = Organization(name="VT Org B", public_id="vt-org-b")
        session.add_all([org_a, org_b])
        await session.commit()
        await session.refresh(org_a)
        await session.refresh(org_b)

        inv_a = await svc.start_investigation(
            session,
            str(org_a.id),
            "pacs008-missing-town",
            settings=settings,
            pipeline=pipeline,
            registry=registry,
            evolus_client=evolus,
        )
        assert inv_a.status == "FAILED"  # Evolus not configured -> visible failure
        assert inv_a.error and "not configured" in inv_a.error

        payload = await svc.validate_case_for_tool(
            session,
            settings,
            case_ref=inv_a.investigation_id,
            pipeline=pipeline,
            registry=registry,
        )
        assert payload["validation"]["status"] == "valid"
        assert any(f["rule_id"] == "ADR-001" for f in payload["validation"]["findings"])
        assert payload["input"]["input_unchanged"] is True
        assert payload["input"]["identity_sha256"] == inv_a.input_hash

        # A case belonging to another organization is out of scope for this tool credential.
        inv_b = await svc.start_investigation(
            session,
            str(org_b.id),
            "pacs008-valid",
            settings=settings,
            pipeline=pipeline,
            registry=registry,
            evolus_client=evolus,
        )
        with pytest.raises(PermissionError):
            await svc.validate_case_for_tool(
                session,
                settings,
                case_ref=inv_b.investigation_id,
                pipeline=pipeline,
                registry=registry,
            )

        # Unknown case reference is not found.
        with pytest.raises(LookupError):
            await svc.validate_case_for_tool(
                session,
                settings,
                case_ref="inv-does-not-exist",
                pipeline=pipeline,
                registry=registry,
            )

    await engine.dispose()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
async def test_prepare_only_does_not_start_workflow():
    """Prepare-only mode persists deterministic findings but never starts the workflow."""
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        app_environment="test",
        metrics_enabled=False,
        evolus_tool_api_key="tool-secret",
        evolus_demo_org_public_id="vt-org-prep",
    )

    class _MustNotStart:
        configured = True

        async def start_workflow(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("start_workflow must not be called in prepare-only mode")

    pipeline = _pipeline()
    registry = build_default_registry()
    async with session_factory() as session:
        org = Organization(name="Prep Org", public_id="vt-org-prep")
        session.add(org)
        await session.commit()
        await session.refresh(org)
        inv = await svc.start_investigation(
            session,
            str(org.id),
            "pacs008-missing-town",
            settings=settings,
            pipeline=pipeline,
            registry=registry,
            evolus_client=_MustNotStart(),  # type: ignore[arg-type]
            start_workflow=False,
        )
        assert inv.status == "PREPARED"
        assert inv.agent_status == "NOT_STARTED"
        assert inv.evolus_execution_id is None
        assert inv.deterministic_findings is not None

    await engine.dispose()
