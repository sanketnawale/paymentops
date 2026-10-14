"""Security tests for the legacy /analyze endpoint tenant behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient
from paymentops_api.app.factory import create_app
from paymentops_api.settings import Settings


def _app(environment: str):
    return create_app(
        Settings(
            app_environment=environment,
            metrics_enabled=False,
            ready_checks=[],
            database_password="x",
        )
    )


def test_legacy_analyze_disabled_in_production():
    app = _app("production")
    with TestClient(app) as c:
        r = c.post("/api/v1/payments/analyze", json={"xml": "<a/>", "persist": False})
        assert r.status_code == 404


def test_legacy_analyze_requires_auth_to_persist():
    # persist=true without client credentials -> 401 (cannot create unscoped data).
    app = _app("test")
    with TestClient(app) as c:
        r = c.post("/api/v1/payments/analyze", json={"xml": "<a/>", "persist": True})
        assert r.status_code == 401


def test_legacy_analyze_persist_false_no_auth_ok_in_dev():
    # persist=false is analysis-only (no case created), allowed in development.
    app = _app("test")
    with TestClient(app) as c:
        r = c.post("/api/v1/payments/analyze", json={"xml": "<not-xml>", "persist": False})
        assert r.status_code == 400  # malformed XML -> structured error, not auth failure
