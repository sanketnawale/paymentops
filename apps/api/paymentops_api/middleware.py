"""HTTP middleware: correlation ids, security headers, and request metrics.

All middleware is applied in the app factory. Metrics are low-cardinality (no labels
derived from request payloads or user-controlled values that could leak data).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from paymentops_api.settings import Settings

logger = structlog.get_logger("paymentops.http")

CallNext = Callable[[Request], Awaitable[Response]]

# Metrics are defined once at module scope to avoid registry collisions.
requests_total = Counter(
    "paymentops_http_requests_total",
    "Total HTTP requests",
    ("service", "method", "status", "version"),
)
request_duration = Histogram(
    "paymentops_http_request_duration_seconds",
    "HTTP request duration",
    ("service", "method", "status", "version"),
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns/forwards a correlation id and binds it to the log context (redacted)."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = cid
        structlog.contextvars.bind_contextvars(correlation_id=cid)
        response = await call_next(request)
        response.headers["x-correlation-id"] = cid
        structlog.contextvars.unbind_contextvars("correlation_id")
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Sets safe production defaults for common security headers."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'",
        )
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records request count, status, and duration with low-cardinality labels."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        if not self.settings.metrics_enabled:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Coerce status labels to generic buckets to avoid unbounded cardinality.
        status_bucket = str(response.status_code // 100 * 100)
        requests_total.labels(
            service="paymentops-api",
            method=request.method,
            status=status_bucket,
            version=self.settings.app_version,
        ).inc()
        request_duration.labels(
            service="paymentops-api",
            method=request.method,
            status=status_bucket,
            version=self.settings.app_version,
        ).observe(duration)
        return response
