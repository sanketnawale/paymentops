"""Supported pacs.008 namespaces/versions.

We deliberately support a small, explicit set of versions. Unsupported versions are
rejected with a structured ``UnsupportedMessageTypeError`` (XML-004), never silently parsed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedVersion:
    # Fully-qualified identifier, e.g. "pacs.008.001.08"
    identifier: str
    # ISO 20022 message definition name
    message_name: str
    # XML targetNamespace
    namespace: str
    # Root element under Document, e.g. "FIToFICstmrCdtTrf"
    root_element: str = "FIToFICstmrCdtTrf"


SUPPORTED_PACS_008_VERSIONS: dict[str, SupportedVersion] = {
    "pacs.008.001.08": SupportedVersion(
        identifier="pacs.008.001.08",
        message_name="FIToFICustomerCreditTransferV08",
        namespace="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
    ),
}

# Namespaces that are pacs.008 but NOT in our supported set -> structured "unsupported version".
KNOWN_PACS_008_NAMESPACES: set[str] = {
    "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.02",
    "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.04",
    "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.05",
    "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.09",
    "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.11",
    "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.12",
}


def supported_identifier_for_namespace(namespace: str) -> SupportedVersion | None:
    for version in SUPPORTED_PACS_008_VERSIONS.values():
        if version.namespace == namespace:
            return version
    return None
