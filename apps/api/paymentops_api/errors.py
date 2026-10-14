"""Exception hierarchy and safe HTTP exception handlers.

Guarantees:
- Clients never receive raw exception messages or stack traces.
- Configuration/secrets never leak into error responses.
- Every error carries a correlation id.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from paymentops_api.logging import get_logger

logger = get_logger("paymentops.errors")


class PaymentOpsError(Exception):
    """Base application error. ``message`` may be shown to clients only if safe."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "internal_error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class ValidationFailure(PaymentOpsError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code="validation_failure"
        )


class NotFoundError(PaymentOpsError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, code="not_found")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", None) or str(uuid.uuid4())


def register_exception_handlers(app: FastAPI) -> None:
    from iso_engine.xml_errors import XmlError

    @app.exception_handler(XmlError)
    async def handle_xml_error(request: Request, exc: XmlError) -> JSONResponse:
        cid = _correlation_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.as_dict(),
                "correlation_id": cid,
            },
        )

    @app.exception_handler(PaymentOpsError)
    async def handle_paymentops_error(request: Request, exc: PaymentOpsError) -> JSONResponse:
        cid = _correlation_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": exc.code, "message": exc.message},
                "correlation_id": cid,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        cid = _correlation_id(request)
        # Log the real error internally; never expose it to the client.
        logger.exception("unhandled_exception", correlation_id=cid)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {"code": "internal_error", "message": "Internal server error."},
                "correlation_id": cid,
            },
        )


def log_unhandled_payload_error(exc: Exception, correlation_id: str) -> None:
    """Utility to log a payload-processing error without the payload itself."""
    logger.warning(
        "payload_processing_error",
        error_type=type(exc).__name__,
        correlation_id=correlation_id,
        message=str(exc)[:256],
    )


def redacted_exc_info(exc: BaseException) -> dict[str, Any]:
    """Safe exception summary for internal logs (no message body of payloads)."""
    return {
        "error_type": type(exc).__name__,
        "detail": str(exc)[:256],
    }
