"""ISO 20022 engine: secure XML ingestion, message identification, XSD validation, and the
pacs.008 adapter.

Everything here is deterministic. The XML/XSD validator is authoritative; it is never
overridden by AI or heuristic output (ADR-005).
"""

from __future__ import annotations

from iso_engine.camt053.adapter import map_camt053_to_account_report
from iso_engine.camt053.identifier import identify_camt053
from iso_engine.camt053.namespace import SUPPORTED_CAMT_053_VERSIONS
from iso_engine.camt054.adapter import map_camt054_to_account_report
from iso_engine.camt054.identifier import identify_camt054
from iso_engine.camt054.namespace import SUPPORTED_CAMT_054_VERSIONS
from iso_engine.common import IsoMessageMetadata
from iso_engine.pacs002.adapter import map_pacs002_to_status
from iso_engine.pacs002.identifier import identify_pacs002
from iso_engine.pacs002.namespace import SUPPORTED_PACS_002_VERSIONS
from iso_engine.pacs008.adapter import map_pacs008_to_canonical
from iso_engine.pacs008.identifier import identify_pacs008
from iso_engine.pacs008.namespace import SUPPORTED_PACS_008_VERSIONS, SupportedVersion
from iso_engine.pacs009.adapter import map_pacs009_to_canonical
from iso_engine.pacs009.identifier import identify_pacs009
from iso_engine.pacs009.namespace import SUPPORTED_PACS_009_VERSIONS
from iso_engine.pain001.adapter import map_pain001_to_canonical
from iso_engine.pain001.identifier import identify_pain001
from iso_engine.pain001.namespace import SUPPORTED_PAIN_001_VERSIONS
from iso_engine.registry import (
    IsoMessageRegistry,
    MessageDefinition,
    RegisteredMessage,
    UnsupportedMessageError,
    build_default_registry,
)
from iso_engine.xml_errors import (
    EncodingError,
    MalformedXmlError,
    PayloadTooLargeError,
    ProhibitedEntityError,
    UnsupportedMessageTypeError,
    XmlError,
)
from iso_engine.xml_security import SecureXmlDocument, secure_parse
from iso_engine.xsd_validator import SchemaIssue, SchemaValidationResult, validate_message

__all__ = [
    "EncodingError",
    "IsoMessageMetadata",
    "IsoMessageRegistry",
    "MalformedXmlError",
    "MessageDefinition",
    "PayloadTooLargeError",
    "ProhibitedEntityError",
    "RegisteredMessage",
    "SchemaIssue",
    "SchemaValidationResult",
    "SUPPORTED_CAMT_053_VERSIONS",
    "SUPPORTED_CAMT_054_VERSIONS",
    "SUPPORTED_PACS_002_VERSIONS",
    "SUPPORTED_PACS_008_VERSIONS",
    "SUPPORTED_PACS_009_VERSIONS",
    "SUPPORTED_PAIN_001_VERSIONS",
    "SecureXmlDocument",
    "SupportedVersion",
    "UnsupportedMessageError",
    "UnsupportedMessageTypeError",
    "XmlError",
    "build_default_registry",
    "identify_camt053",
    "identify_camt054",
    "identify_pacs002",
    "identify_pacs008",
    "identify_pacs009",
    "identify_pain001",
    "map_camt053_to_account_report",
    "map_camt054_to_account_report",
    "map_pacs002_to_status",
    "map_pacs008_to_canonical",
    "map_pacs009_to_canonical",
    "map_pain001_to_canonical",
    "secure_parse",
    "validate_message",
]
