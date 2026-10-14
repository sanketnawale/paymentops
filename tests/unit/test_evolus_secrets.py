"""Ensure Evolus/AMD secrets never leak to public info or logs."""

from __future__ import annotations

from paymentops_api.logging import _redact_processor
from paymentops_api.settings import Settings


def test_safe_info_never_exposes_evolus_secrets():
    settings = Settings(
        evolus_enabled=True,
        evolus_api_key="sk-super-secret",
        evolus_application_id="app-1",
        evolus_workflow_id="wf-1",
        evolus_tool_api_key="tool-super-secret",
        database_password="db-secret",
    )
    info = settings.safe_info()
    joined = str(info)
    for secret in ("sk-super-secret", "tool-super-secret", "db-secret"):
        assert secret not in joined
    assert info["evolus_configured"] is True
    assert info["evolus_tool_configured"] is True


def test_safe_info_reports_not_configured_without_secrets():
    info = Settings(evolus_enabled=True).safe_info()
    assert info["evolus_configured"] is False
    assert info["evolus_tool_configured"] is False


def test_logging_redacts_evolus_secret_fields():
    out = _redact_processor(
        None,
        "info",
        {
            "evolus_api_key": "sk-x",
            "X-ApiKey": "sk-y",
            "evolus_tool_api_key": "tool-z",
            "case_ref": "inv-1",
            "status": "RUNNING",
        },
    )
    assert out["evolus_api_key"] == "[REDACTED]"
    assert out["X-ApiKey"] == "[REDACTED]"
    assert out["evolus_tool_api_key"] == "[REDACTED]"
    # Non-secret operational fields are preserved.
    assert out["case_ref"] == "inv-1"
    assert out["status"] == "RUNNING"
