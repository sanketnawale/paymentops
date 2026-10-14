"""Supported pain.001 namespaces/versions (Week 5).

We deliberately support a small, explicit set of versions. Unsupported versions are rejected
with a structured ``UnsupportedMessageTypeError``, never silently parsed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedVersion:
    identifier: str
    message_name: str
    namespace: str
    root_element: str = "CstmrCdtTrfInitn"


SUPPORTED_PAIN_001_VERSIONS: dict[str, SupportedVersion] = {
    "pain.001.001.13": SupportedVersion(
        identifier="pain.001.001.13",
        message_name="CustomerCreditTransferInitiationV13",
        namespace="urn:iso:std:iso:20022:tech:xsd:pain.001.001.13",
    ),
}

# Namespaces that are pain.001 but NOT in our supported set -> structured "unsupported version".
KNOWN_PAIN_001_NAMESPACES: set[str] = {
    "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03",
    "urn:iso:std:iso:20022:tech:xsd:pain.001.001.07",
    "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09",
    "urn:iso:std:iso:20022:tech:xsd:pain.001.001.12",
}


def supported_identifier_for_namespace(namespace: str) -> SupportedVersion | None:
    for version in SUPPORTED_PAIN_001_VERSIONS.values():
        if version.namespace == namespace:
            return version
    return None
