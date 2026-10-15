"""Evolus REST client.

Verified against the public Evolus developer documentation (https://evolus.ai/developers):

- REST base URL: ``https://api.evolus.ai/api/v1``
- Auth headers: ``X-ApiKey`` (application API key) + ``X-Application-Id`` (space id)
- Start a workflow: ``POST /workflows/{workflowId}/execute`` (multipart/form-data with
  ``input`` and, optionally, ``parameters``); returns ``202 Accepted`` with
  ``{jobId, executionId, enqueuedAt, traceId}`` and the ``X-Workflow-Execution-Id`` header.
- Read a run: ``GET /workflows/{workflowId}/executions/{executionId}``; ``status`` is one of
  ``Pending`` | ``Running`` | ``Completed`` | ``Failed``.

The exact shape of the *completed* execution body is not fully documented publicly (the full
schema lives in the workspace's interactive API reference). This client therefore parses the
result defensively and always preserves the raw body, so nothing is fabricated.

Design rules (Phase 1):

- Workflow *start* requests are never retried automatically: a retry could create a duplicate
  run. Only read/poll requests are retried, honouring ``Retry-After`` with bounded backoff.
- Secrets are never logged. Only event names, HTTP status and opaque run identifiers.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from paymentops_api.settings import Settings

logger = structlog.get_logger("paymentops.evolus")

# Evolus execution statuses -> PaymentOps investigation statuses.
_STATUS_MAP = {
    "pending": "PENDING",
    "queued": "PENDING",
    "running": "RUNNING",
    "completed": "COMPLETED",
    "succeeded": "COMPLETED",
    "success": "COMPLETED",
    "failed": "FAILED",
    "error": "FAILED",
    "cancelled": "FAILED",
    "canceled": "FAILED",
}

# Keys that may carry the agent's textual output in a completed execution body.
_OUTPUT_KEYS = ("output", "result", "data", "answer", "content", "text", "message")


class EvolusError(Exception):
    """Base class for Evolus integration errors (safe to surface to the operator)."""


class EvolusNotConfiguredError(EvolusError):
    """Raised when the Evolus integration is not configured."""


class EvolusRequestError(EvolusError):
    """A transport/server error talking to Evolus."""


class EvolusRateLimitedError(EvolusError):
    """Evolus returned 429. ``retry_after`` is the advertised wait, in seconds."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class EvolusProtocolError(EvolusError):
    """Evolus returned an unexpected/incomplete response body."""


@dataclass(frozen=True)
class WorkflowRun:
    execution_id: str
    job_id: str | None = None
    trace_id: str | None = None
    enqueued_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowExecution:
    status: str  # PENDING | RUNNING | COMPLETED | FAILED
    raw_status: str
    output_text: str | None = None
    result: dict[str, Any] | None = None
    error_text: str | None = None
    trace_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def normalize_execution_status(raw_status: str | None) -> str:
    """Map an Evolus status string to a PaymentOps investigation status."""
    if not raw_status:
        return "PENDING"
    return _STATUS_MAP.get(raw_status.strip().lower(), "RUNNING")


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - a non-JSON body must not crash the client
        return {}
    return body if isinstance(body, dict) else {"value": body}


def _extract_output(body: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Best-effort extraction of the agent output from a completed execution body.

    Observed Evolus shape (real run): the agent text is at top-level ``output`` (a string);
    ``stepOutputs`` is an object keyed by step number whose values may repeat ``output``.
    Returns ``(text, structured)``. Never raises; unknown shapes yield ``(None, None)``.
    """
    for key in _OUTPUT_KEYS:
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value, None
        if isinstance(value, dict):
            text = _deep_text(value)
            return text, value
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False), {"items": value}
    # Fall back to per-step outputs (observed: {"1": "...", "2": "..."}).
    steps = body.get("stepOutputs")
    if isinstance(steps, dict):
        texts = [v for v in steps.values() if isinstance(v, str) and v.strip()]
        if texts:
            merged = texts[-1] if len(set(texts)) == 1 else "\n\n".join(texts)
            return merged, {"stepOutputs": steps}
    return None, None


def _extract_error(body: dict[str, Any]) -> str | None:
    """Extract a failure message from the observed top-level ``error`` field.

    Observed: ``error`` is a list (``[]`` on success). Falls back to ``detail``.
    """
    error = body.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()[:1000]
    if isinstance(error, list):
        parts = [str(item).strip() for item in error if str(item).strip()]
        if parts:
            return " | ".join(parts)[:1000]
    detail = body.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail.strip()[:1000]
    return None


def _deep_text(value: dict[str, Any]) -> str | None:
    for key in ("output", "text", "content", "answer", "message", "summary", "explanation"):
        inner = value.get(key)
        if isinstance(inner, str) and inner.strip():
            return inner
    return None


class EvolusClient:
    """Thin async client for the Evolus REST API (workflows)."""

    def __init__(self, settings: Settings, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http_client

    @property
    def configured(self) -> bool:
        return self._settings.evolus_configured

    def _auth_headers(self) -> dict[str, str]:
        # These values are never logged (see logging.SENSITIVE_FIELD_NAMES).
        return {
            "X-ApiKey": self._settings.evolus_api_key or "",
            "X-Application-Id": self._settings.evolus_application_id or "",
            "Accept": "application/json",
        }

    @contextlib.asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._http is not None:
            yield self._http
            return
        timeout = httpx.Timeout(self._settings.evolus_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            yield client

    def _workflow_url(self, suffix: str = "") -> str:
        base = self._settings.evolus_api_base_url.rstrip("/")
        workflow = self._settings.evolus_workflow_id or ""
        return f"{base}/workflows/{workflow}{suffix}"

    async def start_workflow(
        self,
        input_text: str,
        parameters: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Start an investigation workflow. Never retried (avoids duplicate runs)."""
        if not self.configured:
            raise EvolusNotConfiguredError("Evolus is not configured")

        data: dict[str, str] = {"input": input_text}
        if parameters:
            # Evolus expects `parameters` as a flat JSON object in the multipart form.
            data["parameters"] = json.dumps(parameters)

        url = self._workflow_url("/execute")
        try:
            async with self._client() as client:
                response = await client.post(url, headers=self._auth_headers(), data=data)
        except httpx.HTTPError as exc:
            logger.warning("evolus_workflow_start_transport_error", error_type=type(exc).__name__)
            raise EvolusRequestError(
                "Could not reach the Evolus workflow service. No run was started."
            ) from exc

        if response.status_code == 429:
            raise EvolusRateLimitedError(
                "Evolus rate limit reached while starting the workflow.",
                retry_after=_retry_after_seconds(response),
            )
        if response.status_code == 409:
            raise EvolusRequestError(
                "The Evolus workflow is not enabled (409 Conflict). Enable it in the workspace."
            )
        if response.status_code not in (200, 201, 202):
            logger.warning("evolus_workflow_start_http_error", status=response.status_code)
            raise EvolusRequestError(f"Evolus workflow start failed (HTTP {response.status_code}).")

        body = _safe_json(response)
        execution_id = _opt_str(body.get("executionId")) or _opt_str(
            response.headers.get("X-Workflow-Execution-Id")
        )
        if not execution_id:
            raise EvolusProtocolError("Evolus did not return an executionId for the run.")

        logger.info("evolus_workflow_started", status_code=response.status_code)
        return WorkflowRun(
            execution_id=execution_id,
            job_id=_opt_str(body.get("jobId")),
            trace_id=_opt_str(body.get("traceId")),
            enqueued_at=_opt_str(body.get("enqueuedAt")),
            raw=body,
        )

    async def get_execution(self, execution_id: str) -> WorkflowExecution:
        """Read a workflow run, retrying transient failures with bounded backoff."""
        if not self.configured:
            raise EvolusNotConfiguredError("Evolus is not configured")

        url = self._workflow_url(f"/executions/{execution_id}")
        attempts = max(1, self._settings.evolus_max_retries + 1)
        last_error: EvolusError | None = None

        for attempt in range(attempts):
            try:
                async with self._client() as client:
                    response = await client.get(url, headers=self._auth_headers())
            except httpx.HTTPError as exc:
                last_error = EvolusRequestError("Could not reach the Evolus workflow service.")
                logger.warning(
                    "evolus_execution_poll_transport_error",
                    error_type=type(exc).__name__,
                    attempt=attempt,
                )
                await self._backoff(attempt, None)
                continue

            if response.status_code == 429:
                retry_after = _retry_after_seconds(response)
                last_error = EvolusRateLimitedError(
                    "Evolus rate limit reached while polling the run.", retry_after=retry_after
                )
                await self._backoff(attempt, retry_after)
                continue
            if response.status_code >= 500:
                last_error = EvolusRequestError(
                    f"Evolus returned a server error (HTTP {response.status_code})."
                )
                await self._backoff(attempt, None)
                continue
            if response.status_code == 404:
                raise EvolusRequestError("Evolus run not found.")
            if response.status_code >= 400:
                raise EvolusRequestError(
                    f"Evolus execution poll failed (HTTP {response.status_code})."
                )

            body = _safe_json(response)
            return self._parse_execution(body)

        raise last_error or EvolusRequestError("Evolus execution poll failed.")

    async def _backoff(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            delay = min(retry_after, 30.0)
        else:
            delay = min(0.5 * (2**attempt), 5.0)
        await asyncio.sleep(delay)

    def _parse_execution(self, body: dict[str, Any]) -> WorkflowExecution:
        raw_status = _opt_str(body.get("status")) or ""
        status = normalize_execution_status(raw_status)
        output_text: str | None = None
        result: dict[str, Any] | None = None
        if status == "COMPLETED":
            output_text, result = _extract_output(body)
        return WorkflowExecution(
            status=status,
            raw_status=raw_status,
            output_text=output_text,
            result=result,
            error_text=_extract_error(body),
            trace_id=_opt_str(body.get("traceId")),
            raw=body,
        )
