"""Supported pacs.002 namespaces/versions (Week 5)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedVersion:
    identifier: str
    message_name: str
    namespace: str
    root_element: str = "FIToFIPmtStsRpt"


SUPPORTED_PACS_002_VERSIONS: dict[str, SupportedVersion] = {
    "pacs.002.001.16": SupportedVersion(
        identifier="pacs.002.001.16",
        message_name="FIToFIPaymentStatusReportV16",
        namespace="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.16",
    ),
}

KNOWN_PACS_002_NAMESPACES: set[str] = {
    "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10",
    "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.12",
}


def supported_identifier_for_namespace(namespace: str) -> SupportedVersion | None:
    for version in SUPPORTED_PACS_002_VERSIONS.values():
        if version.namespace == namespace:
            return version
    return None
