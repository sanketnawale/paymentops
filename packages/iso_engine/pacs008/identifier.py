"""pacs.008 message identification.

Detects whether an already-securely-parsed XML document is a supported pacs.008 message and
returns its version identifier. Unsupported pacs.008 versions and non-pacs.008 documents
are rejected with structured errors.
"""

from __future__ import annotations

from lxml import etree

from iso_engine.pacs008.namespace import (
    KNOWN_PACS_008_NAMESPACES,
    SupportedVersion,
    supported_identifier_for_namespace,
)
from iso_engine.xml_errors import UnsupportedMessageTypeError

# pacs.008 Document root element is "Document" wrapping "FIToFICstmrCdtTrf".
_DOCUMENT_ROOT = "Document"
_PACS_008_MESSAGE_ELEMENT = "FIToFICstmrCdtTrf"


def identify_pacs008(root: etree._Element) -> SupportedVersion:
    """Return the supported pacs.008 version for ``root`` or raise a structured error."""

    tag = root.tag
    if not isinstance(tag, str):
        raise UnsupportedMessageTypeError("Message root is not a namespaced XML element")

    if "}" in tag:
        namespace, localname = tag[1:].split("}", 1)
    else:
        namespace, localname = "", tag

    if localname != _DOCUMENT_ROOT:
        raise UnsupportedMessageTypeError("Not a pacs.008 message (unexpected root element)")

    supported = supported_identifier_for_namespace(namespace)
    if supported is not None:
        return supported

    if namespace in KNOWN_PACS_008_NAMESPACES:
        raise UnsupportedMessageTypeError(f"Unsupported pacs.008 version: {namespace}")

    raise UnsupportedMessageTypeError("Unsupported message namespace")


def root_namespace(root: etree._Element) -> str | None:
    tag = root.tag
    if isinstance(tag, str) and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None
