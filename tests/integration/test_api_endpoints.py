"""Integration tests for the health, readiness and info endpoints.

Uses the ``safe_client`` fixture which stubs dependency checks so no real DB/Redis is
required. Asserts the response contract and correlation-id behaviour.
"""

from __future__ import annotations


def test_health_returns_ok(safe_client):
    r = safe_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_returns_ready_when_deps_healthy(safe_client):
    r = safe_client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert {"database", "redis"} <= {c["name"] for c in body["checks"]}
    assert all(c["ok"] for c in body["checks"])


def test_ready_returns_503_when_dependency_down(app):
    from fastapi.testclient import TestClient

    # No stubbing: with no DB/Redis running, readiness must be 503 (never a false positive).
    with TestClient(app) as c:
        r = c.get("/ready")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "not_ready"
        assert any(not c["ok"] for c in body["checks"])


def test_info_endpoint_exposes_only_safe_fields(safe_client):
    r = safe_client.get("/api/v1/info")
    assert r.status_code == 200
    body = r.json()
    assert body["product"] == "CloudNova PaymentOps"
    assert body["environment"] == "test"
    assert "ai_enabled" in body
    # Never expose credentials or internal endpoints.
    joined = str(body)
    for leaked in ("password", "postgresql", "redis://", "database_user", "secret"):
        assert leaked.lower() not in joined.lower()


def test_correlation_id_header_present(safe_client):
    r = safe_client.get("/health")
    assert r.headers.get("x-correlation-id")


def test_security_headers_present(safe_client):
    r = safe_client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"
