"""Structured JSON logging for PaymentOps.

Logging is deterministic and JSON-based. A ``redact_processor`` removes sensitive field
names (IBAN/account/name/address/payload/etc.) from every log record before it is emitted,
so accidental payload logging cannot leak to the output stream. Financial payloads must
never be passed to a logger in the first place; this is defence in depth.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

# Field names that must never be serialized into logs.
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "iban",
        "account",
        "account_number",
        "iban_number",
        "name",
        "customer_name",
        "address",
        "payload",
        "body",
        "creditor",
        "debtor",
        "raw",
        "raw_payload",
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "bic",
        "swift",
        "pan",
        "card_number",
        "balance",
        "api_key",
        "apikey",
        "x-apikey",
        "x-application-id",
        "x-tool-key",
        "authorization",
        "evolus_api_key",
        "evolus_tool_api_key",
    }
)

REDACTED = "[REDACTED]"


def _redact(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return {
            k: _redact(v, k)
            if isinstance(v, (dict, list))
            else (REDACTED if str(k).lower() in SENSITIVE_FIELD_NAMES else v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v, key) if isinstance(v, (dict, list)) else v for v in value]
    return value


def _redact_processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a log event dict in place, mutating a copy."""
    sanitized: dict[str, Any] = {}
    for key, value in event_dict.items():
        if str(key).lower() in SENSITIVE_FIELD_NAMES:
            sanitized[key] = REDACTED
        else:
            sanitized[key] = _redact(value, key)
    return sanitized


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structlog-based structured logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, stream=sys.stdout, format="%(message)s")

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_processor,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib loggers through structlog so third-party logs are structured too.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
