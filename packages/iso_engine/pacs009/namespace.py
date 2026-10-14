"""Supported pacs.009 namespaces/versions (Week 5)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedVersion:
    identifier: str
    message_name: str
    namespace: str
    root_element: str = "FICdtTrf"


SUPPORTED_PACS_009_VERSIONS: dict[str, SupportedVersion] = {
    "pacs.009.001.13": SupportedVersion(
        identifier="pacs.009.001.13",
        message_name="FinancialInstitutionCreditTransferV13",
        namespace="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.13",
    ),
}

KNOWN_PACS_009_NAMESPACES: set[str] = {
    "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08",
    "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.10",
}


def supported_identifier_for_namespace(namespace: str) -> SupportedVersion | None:
    for version in SUPPORTED_PACS_009_VERSIONS.values():
        if version.namespace == namespace:
            return version
    return None
