"""ISO 20022 message registry.

Maps a fully-qualified message identifier / namespace to its version-specific parser adapter +
canonical mapper. Registered messages (Week 5): pacs.008.001.08, pain.001.001.13,
pacs.002.001.16, pacs.009.001.13. Future messages (camt.053, camt.054) can be added without
changing the core engine.

Unsupported versions fail clearly (never silently parsed). Dispatch is never family-only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lxml import etree

from iso_engine.common import extract_namespace


@dataclass(frozen=True)
class MessageDefinition:
    """Explicit metadata for a supported ISO message/version."""

    message_family: str  # e.g. "pacs", "pain", "camt"
    message_definition: str  # e.g. "FIToFICustomerCreditTransferV08"
    version: str  # fully-qualified, e.g. "pacs.008.001.08"
    namespace: str  # targetNamespace
    adapter_version: str  # implementation version of the adapter
    root_element: str = "Document"


@dataclass(frozen=True)
class RegisteredMessage:
    definition: MessageDefinition
    # Parses a secure XML tree -> canonical artifact (PaymentMessage or lifecycle payload).
    adapter: Callable[[etree._Element, Any], Any]
    # Maps the adapter output -> canonical model (often the same as adapter).
    canonical_mapper: Callable[..., Any]
    # Identifies the message version from a root element (raises structured error).
    identifier: Callable[..., Any] | None = None
    # The version object the adapter expects as its second argument.
    version_obj: Any = None


class IsoMessageRegistry:
    """Registry of supported ISO messages keyed by identifier, namespace, and root."""

    def __init__(self) -> None:
        self._by_identifier: dict[str, RegisteredMessage] = {}
        self._by_namespace: dict[str, RegisteredMessage] = {}

    def register(self, message: RegisteredMessage) -> None:
        self._by_identifier[message.definition.version] = message
        self._by_namespace[message.definition.namespace] = message

    def resolve(self, identifier: str) -> RegisteredMessage:
        try:
            return self._by_identifier[identifier]
        except KeyError:
            raise UnsupportedMessageError(identifier) from None

    def resolve_namespace(self, namespace: str) -> RegisteredMessage:
        try:
            return self._by_namespace[namespace]
        except KeyError:
            raise UnsupportedMessageError(namespace) from None

    def resolve_root(self, root: etree._Element) -> RegisteredMessage:
        """Resolve a securely-parsed document by its targetNamespace."""
        namespace = extract_namespace(root)
        if not namespace:
            raise UnsupportedMessageError("message has no namespace")
        return self.resolve_namespace(namespace)

    def supported(self) -> list[MessageDefinition]:
        return [m.definition for m in self._by_identifier.values()]

    def __contains__(self, identifier: str) -> bool:
        return identifier in self._by_identifier


class UnsupportedMessageError(Exception):
    """Raised for a known-but-unsupported or unknown ISO version (never silently parsed)."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"unsupported ISO message/version: {identifier}")


def build_default_registry() -> IsoMessageRegistry:
    """Build the registry with the currently supported messages."""
    from iso_engine.camt053.adapter import map_camt053_to_account_report
    from iso_engine.camt053.identifier import identify_camt053
    from iso_engine.camt053.namespace import SUPPORTED_CAMT_053_VERSIONS
    from iso_engine.camt054.adapter import map_camt054_to_account_report
    from iso_engine.camt054.identifier import identify_camt054
    from iso_engine.camt054.namespace import SUPPORTED_CAMT_054_VERSIONS
    from iso_engine.pacs002.adapter import map_pacs002_to_status
    from iso_engine.pacs002.identifier import identify_pacs002
    from iso_engine.pacs002.namespace import SUPPORTED_PACS_002_VERSIONS
    from iso_engine.pacs008.adapter import map_pacs008_to_canonical
    from iso_engine.pacs008.identifier import identify_pacs008
    from iso_engine.pacs008.namespace import SUPPORTED_PACS_008_VERSIONS
    from iso_engine.pacs009.adapter import map_pacs009_to_canonical
    from iso_engine.pacs009.identifier import identify_pacs009
    from iso_engine.pacs009.namespace import SUPPORTED_PACS_009_VERSIONS
    from iso_engine.pain001.adapter import map_pain001_to_canonical
    from iso_engine.pain001.identifier import identify_pain001
    from iso_engine.pain001.namespace import SUPPORTED_PAIN_001_VERSIONS

    registry = IsoMessageRegistry()

    def _register(
        versions: dict[str, Any],
        adapter: Callable[[etree._Element, Any], Any],
        identifier: Callable[..., Any],
        family: str,
        definition: str,
    ) -> None:
        for version in versions.values():
            registry.register(
                RegisteredMessage(
                    definition=MessageDefinition(
                        message_family=family,
                        message_definition=version.message_name,
                        version=version.identifier,
                        namespace=version.namespace,
                        adapter_version="0.1.0",
                        root_element=version.root_element,
                    ),
                    adapter=adapter,
                    canonical_mapper=adapter,
                    identifier=identifier,
                    version_obj=version,
                )
            )

    _register(SUPPORTED_PACS_008_VERSIONS, map_pacs008_to_canonical, identify_pacs008, "pacs", "")
    _register(SUPPORTED_PAIN_001_VERSIONS, map_pain001_to_canonical, identify_pain001, "pain", "")
    _register(SUPPORTED_PACS_002_VERSIONS, map_pacs002_to_status, identify_pacs002, "pacs", "")
    _register(SUPPORTED_PACS_009_VERSIONS, map_pacs009_to_canonical, identify_pacs009, "pacs", "")
    _register(
        SUPPORTED_CAMT_053_VERSIONS, map_camt053_to_account_report, identify_camt053, "camt", ""
    )
    _register(
        SUPPORTED_CAMT_054_VERSIONS, map_camt054_to_account_report, identify_camt054, "camt", ""
    )
    return registry
