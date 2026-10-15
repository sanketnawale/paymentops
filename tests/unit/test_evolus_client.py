"""Unit tests for the Evolus REST client (mocked transport; no live AMD/Evolus calls).

These are MOCKED tests: they verify request shape and response parsing against the documented
public contract. They do not prove live Evolus behaviour.
"""

from __future__ import annotations

import httpx
import pytest
from paymentops_api.evolus.client import (
    EvolusClient,
    EvolusNotConfiguredError,
    EvolusProtocolError,
    EvolusRateLimitedError,
    EvolusRequestError,
    normalize_execution_status,
)
from paymentops_api.settings import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_environment": "test",
        "metrics_enabled": False,
        "evolus_enabled": True,
        "evolus_api_key": "test-key",
        "evolus_application_id": "app-1",
        "evolus_workflow_id": "wf-1",
        "evolus_max_retries": 1,
    }
    base.update(overrides)
    return Settings(**base)


def _client(handler, settings: Settings | None = None) -> EvolusClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return EvolusClient(settings or _settings(), http_client=http)


async def test_not_configured_raises():
    client = EvolusClient(Settings(app_environment="test", metrics_enabled=False))
    assert client.configured is False
    with pytest.raises(EvolusNotConfiguredError):
        await client.start_workflow("hello")


async def test_start_workflow_sends_headers_and_parses_execution_id():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["apikey"] = request.headers.get("X-ApiKey")
        seen["appid"] = request.headers.get("X-Application-Id")
        seen["path"] = request.url.path
        seen["body"] = request.content.decode("utf-8", errors="replace")
        return httpx.Response(
            202,
            json={"jobId": "job-1", "executionId": "exec-1", "traceId": "trace-1"},
            headers={"X-Workflow-Execution-Id": "exec-1"},
        )

    run = await _client(handler).start_workflow("investigate case inv-1")
    assert run.execution_id == "exec-1"
    assert run.job_id == "job-1"
    assert run.trace_id == "trace-1"
    assert seen["apikey"] == "test-key"
    assert seen["appid"] == "app-1"
    assert str(seen["path"]).endswith("/workflows/wf-1/execute")
    assert "inv-1" in str(seen["body"])


async def test_start_workflow_conflict_is_visible_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "workflow disabled"})

    with pytest.raises(EvolusRequestError):
        await _client(handler).start_workflow("x")


async def test_start_workflow_rate_limit_reports_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"})

    with pytest.raises(EvolusRateLimitedError) as exc:
        await _client(handler).start_workflow("x")
    assert exc.value.retry_after == 7.0


async def test_start_workflow_missing_execution_id_is_protocol_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"jobId": "job-1"})

    with pytest.raises(EvolusProtocolError):
        await _client(handler).start_workflow("x")


async def test_get_execution_completed_with_structured_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "Completed",
                "result": {"summary": "Reviewed", "cited_rules": ["ADR-001"]},
            },
        )

    execution = await _client(handler).get_execution("exec-1")
    assert execution.status == "COMPLETED"
    assert execution.raw_status == "Completed"
    assert execution.result == {"summary": "Reviewed", "cited_rules": ["ADR-001"]}
    assert execution.output_text == "Reviewed"


async def test_get_execution_completed_with_text_output():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "Completed", "output": "plain answer"})

    execution = await _client(handler).get_execution("exec-1")
    assert execution.status == "COMPLETED"
    assert execution.output_text == "plain answer"


async def test_get_execution_retries_server_error_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"status": "Running"})

    execution = await _client(handler).get_execution("exec-1")
    assert execution.status == "RUNNING"
    assert calls["n"] == 2


async def test_get_execution_not_found_is_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with pytest.raises(EvolusRequestError):
        await _client(handler).get_execution("missing")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pending", "PENDING"),
        ("Running", "RUNNING"),
        ("Completed", "COMPLETED"),
        ("Failed", "FAILED"),
        ("something-new", "RUNNING"),
        (None, "PENDING"),
    ],
)
def test_normalize_execution_status(raw, expected):
    assert normalize_execution_status(raw) == expected


# --- Regression tests against the OBSERVED real Evolus execution body shape ---
# Captured from a completed run (execution ac6ad082-c3c8-f111-bf5b-000d3aae6dc8):
#   top-level ``output`` is the agent text (string); ``stepOutputs`` is an object keyed by
#   step number whose values repeat ``output``; ``error`` is a list (``[]`` on success);
#   ``status`` is "Completed"; ``traceId`` is present on the execution.
_REAL_COMPLETED = {
    "id": "ac6ad082-c3c8-f111-bf5b-000d3aae6dc8",
    "applicationId": "115a7a88-a2c9-4951-b280-80b104a2f4a3",
    "workflowId": "af52e17d-4f3c-4c57-817c-fe50c624ccb7",
    "output": "Reasoning...\n\n### Findings\n- `ADR-001` at Dbtr/PstlAdr\n",
    "stepOutputs": {
        "1": "Reasoning...\n\n### Findings\n- `ADR-001` at Dbtr/PstlAdr\n",
        "2": "Reasoning...\n\n### Findings\n- `ADR-001` at Dbtr/PstlAdr\n",
    },
    "status": "Completed",
    "error": [],
    "traceId": "00-trace-abc",
    "totalStepsExecuted": 2,
}


async def test_get_execution_real_completed_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_REAL_COMPLETED)

    execution = await _client(handler).get_execution("ac6ad082-c3c8-f111-bf5b-000d3aae6dc8")
    assert execution.status == "COMPLETED"
    assert execution.raw_status == "Completed"
    assert execution.output_text and "ADR-001" in execution.output_text
    assert execution.error_text is None
    assert execution.trace_id == "00-trace-abc"


async def test_get_execution_failed_surfaces_error_array():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "Failed", "error": ["tool unavailable", "aborted"], "traceId": "t2"},
        )

    execution = await _client(handler).get_execution("x")
    assert execution.status == "FAILED"
    assert execution.error_text == "tool unavailable | aborted"


async def test_get_execution_stepoutputs_fallback_when_output_absent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "Completed", "stepOutputs": {"1": "only step text"}, "error": []}
        )

    execution = await _client(handler).get_execution("x")
    assert execution.status == "COMPLETED"
    assert execution.output_text == "only step text"
