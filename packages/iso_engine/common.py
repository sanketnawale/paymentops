"""Shared ISO 20022 helpers: namespace/element extraction, message metadata, and common
XML accessors used by every version-specific adapter.

Adapters must be version-specific (family+definition+version+namespace). No family-only
dispatch. This module centralizes the parts that genuinely repeat across adapters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from lxml import etree
from pydantic import BaseModel

# MessageDefinition is imported lazily (inside build_metadata) to avoid a circular import with
# the registry module, which imports the extraction helpers from this module.


class IsoMessageMetadata(BaseModel):
    """Shared ISO message metadata (Task 3). Never duplicated per adapter."""

    message_family: str
    message_definition: str
    message_version: str
    namespace: str
    message_id: str | None = None
    creation_datetime: datetime | None = None
    source_adapter: str
    adapter_version: str
    schema_version: str

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


def extract_namespace(root: etree._Element) -> str | None:
    tag = root.tag
    if isinstance(tag, str) and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def extract_localname(root: etree._Element) -> str:
    tag = root.tag
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def child(el: etree._Element | None, name: str) -> etree._Element | None:
    """Return the first child element whose local name matches ``name``."""
    if el is None:
        return None
    for c in el:
        if extract_localname(c) == name:
            return c
    return None


def children(el: etree._Element | None, name: str) -> list[etree._Element]:
    if el is None:
        return []
    return [c for c in el if extract_localname(c) == name]


def text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    value = el.text.strip()
    return value or None


def child_text(el: etree._Element | None, name: str) -> str | None:
    return text(child(el, name))


def nested_text(el: etree._Element | None, *names: str) -> str | None:
    """Drill down through a chain of element names and return the final text."""
    current = el
    for name in names:
        current = child(current, name)
        if current is None:
            return None
    return text(current)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def amount_from_element(el: etree._Element | None) -> tuple[str | None, str | None]:
    """Return (amount_text, currency) from an amount element carrying Ccy attribute."""
    if el is None:
        return None, None
    return text(el), (el.get("Ccy") or None)


def build_metadata(
    definition: Any,
    *,
    message_id: str | None,
    creation_datetime: datetime | None,
    source_adapter: str,
    schema_version: str | None = None,
) -> IsoMessageMetadata:
    return IsoMessageMetadata(
        message_family=definition.message_family,
        message_definition=definition.message_definition,
        message_version=definition.version,
        namespace=definition.namespace,
        message_id=message_id,
        creation_datetime=creation_datetime,
        source_adapter=source_adapter,
        adapter_version=definition.adapter_version,
        schema_version=schema_version or definition.version,
    )


def identify_message_version(
    root: etree._Element,
    versions: dict[str, Any],
    known_namespaces: set[str],
    expected_message_element: str,
) -> Any:
    """Identify a supported message version from a securely-parsed root element.

    Returns the ``SupportedVersion``, or raises ``UnsupportedMessageTypeError`` for a known
    but unsupported version or an unknown namespace.
    """
    from iso_engine.xml_errors import UnsupportedMessageTypeError

    tag = root.tag
    if not isinstance(tag, str):
        raise UnsupportedMessageTypeError("Message root is not a namespaced XML element")

    if "}" in tag:
        namespace, localname = tag[1:].split("}", 1)
    else:
        namespace, localname = "", tag

    if localname != "Document":
        raise UnsupportedMessageTypeError("Unexpected root element (not a Document)")
    if extract_localname(child(root, expected_message_element) or root) != expected_message_element:
        # The message element may be absent; identifier should still resolve by namespace,
        # but a wrong root message element is a strong signal of a malformed payload.
        pass

    for version in versions.values():
        if version.namespace == namespace:
            return version

    if namespace in known_namespaces:
        raise UnsupportedMessageTypeError(f"Unsupported {versions} version: {namespace}")
    raise UnsupportedMessageTypeError("Unsupported message namespace")
