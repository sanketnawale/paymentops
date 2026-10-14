"""Supported camt.053 namespaces/versions (Week 6).

Exact versions only. Unsupported versions are rejected with a structured error.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedVersion:
    identifier: str
    message_name: str
    namespace: str
    root_element: str = "Stmt"


SUPPORTED_CAMT_053_VERSIONS: dict[str, SupportedVersion] = {
    "camt.053.001.14": SupportedVersion(
        identifier="camt.053.001.14",
        message_name="BankToCustomerStatementV14",
        namespace="urn:iso:std:iso:20022:tech:xsd:camt.053.001.14",
    ),
}

KNOWN_CAMT_053_NAMESPACES: set[str] = {
    "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
    "urn:iso:std:iso:20022:tech:xsd:camt.053.001.13",
}


def supported_identifier_for_namespace(namespace: str) -> SupportedVersion | None:
    for version in SUPPORTED_CAMT_053_VERSIONS.values():
        if version.namespace == namespace:
            return version
    return None
