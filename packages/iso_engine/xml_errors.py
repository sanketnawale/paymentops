"""Structured XML ingestion error taxonomy.

Every XML processing failure is mapped to a stable, machine-readable code. We never catch
``Exception`` and return a generic success/failure. Codes are safe to surface to clients
(they never contain payload content).
"""

from __future__ import annotations


class XmlError(Exception):
    """Base class for structured XML ingestion errors."""

    code = "XML-000"
    default_message = "XML processing error"
    status_code = 400

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class MalformedXmlError(XmlError):
    code = "XML-001"
    default_message = "Malformed XML"
    status_code = 400


class PayloadTooLargeError(XmlError):
    code = "XML-002"
    default_message = "Payload too large"
    status_code = 413


class ProhibitedEntityError(XmlError):
    code = "XML-003"
    default_message = "Prohibited DTD or entity usage"
    status_code = 400


class UnsupportedMessageTypeError(XmlError):
    code = "XML-004"
    default_message = "Unsupported message type"
    status_code = 422


class EncodingError(XmlError):
    code = "XML-005"
    default_message = "Encoding/parsing error"
    status_code = 400
