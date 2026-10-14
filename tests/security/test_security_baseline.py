"""Security-focused baseline tests.

These prove that errors/config do not leak into client responses and that sensitive
settings are never exposed by the info endpoint even when the server is misconfigured.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from paymentops_api.app.factory import create_app
from paymentops_api.logging import REDACTED
from paymentops_api.settings import Settings


def test_unhandled_exception_does_not_leak_traceback_safe():
    """A forced internal error must return a generic message + correlation id, never config."""
    settings = Settings(
        app_environment="test", metrics_enabled=False, database_password="super-secret"
    )
    app = create_app(settings)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("internal detail with secret=super-secret")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
        assert r.status_code == 500
        body = r.json()
        assert "super-secret" not in r.text
        assert "internal_detail_with_secret" not in r.text
        assert body["error"]["code"] == "internal_error"
        assert body["error"]["message"] == "Internal server error."
        assert body.get("correlation_id")


def test_info_does_not_leak_configured_secret():
    settings = Settings(
        app_environment="test",
        metrics_enabled=False,
        database_password="my-very-secret-pw",
        redis_password="redis-pw-123",
        database_user="dbroot",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        r = c.get("/api/v1/info")
        assert r.status_code == 200
        for leak in ("my-very-secret-pw", "redis-pw-123", "dbroot"):
            assert leak not in r.text


def test_info_never_reports_raw_database_credentials():
    settings = Settings(app_environment="test", metrics_enabled=False, database_user="admin")
    info = settings.safe_info()
    for leak in ("admin", "sqlalchemy", "postgresql+", "://"):
        assert leak.lower() not in str(info).lower()


def test_logs_redact_sensitive_fields():
    """The redaction processor must neuter financial/identity keys in log events."""
    from paymentops_api.logging import _redact_processor

    event = {
        "event": "payment_seen",
        "iban": "DE89370400440532013000",
        "account_number": "1234567890",
        "name": "Alice Customer",
        "amount": 50000,
        "currency": "EUR",
    }
    out = _redact_processor(None, None, event)
    assert out["iban"] == REDACTED
    assert out["account_number"] == REDACTED
    assert out["name"] == REDACTED
    # Non-financial metadata must remain legible.
    assert out["event"] == "payment_seen"
    assert out["currency"] == "EUR"


def test_nested_payload_is_redacted_recursively():
    from paymentops_api.logging import _redact_processor

    event = {"event": "debug", "payload": {"debtor": {"account": "DE1234", "name": "X"}}}
    out = _redact_processor(None, None, event)
    assert out["payload"] == REDACTED
