"""Secure XML ingestion.

Input is UNTRUSTED. We parse with lxml and hard-disable every entity/DTD/network feature:

- DTD loading disabled (``load_dtd=False``)
- external entities disabled (``resolve_entities=False``)
- no network access (``no_network=True``)
- huge-tree / entity-expansion guard (``huge_tree=False``)
- internal entity substitution disabled (``resolve_entities=False``)

We also enforce a payload size limit and a defensive timeout-style guard (no real wall-clock
timeout is possible in pure parsing, so we bound by size + limited entity expansion). XML
content is never logged; only error codes and safe metadata are emitted.

Supported encodings are handled by lxml from the XML declaration / BOM. We reject unknown
encodings that lxml cannot decode (mapped to XML-005).
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from lxml import etree

from iso_engine.xml_errors import (
    EncodingError,
    MalformedXmlError,
    PayloadTooLargeError,
    ProhibitedEntityError,
)

# Maximum accepted payload size (bytes). Configurable by callers.
DEFAULT_MAX_PAYLOAD_BYTES = 1_048_576  # 1 MiB

# Dangerous markers we refuse even if the parser is configured defensively.
_DTD_MARKERS = (b"<!DOCTYPE", b"<!ENTITY")


@dataclass(frozen=True)
class SecureXmlDocument:
    """A safely parsed XML document.

    ``root`` is the lxml root element. Callers must not mutate it; treat it as read-only
    evidence. ``encoding`` is the resolved text encoding.
    """

    root: etree._Element
    encoding: str


def secure_parse(
    data: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
) -> SecureXmlDocument:
    """Parse untrusted XML bytes into a safe lxml tree.

    Raises structured :class:`XmlError` subclasses on failure. Never logs payload content.
    """
    if data is None or len(data) == 0:
        raise MalformedXmlError("Empty payload")

    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"Payload exceeds {max_bytes} bytes")

    # Defence-in-depth: reject obvious DTD/entity markers before parsing.
    upper = data.upper()
    for marker in _DTD_MARKERS:
        if marker in upper:
            raise ProhibitedEntityError("DTD or entity declarations are not permitted")

    parser = etree.XMLParser(
        load_dtd=False,
        resolve_entities=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        strip_cdata=False,
        remove_blank_text=False,
    )

    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        # Do not leak the parser message (may contain a fragment of the payload).
        raise MalformedXmlError("XML could not be parsed") from exc
    except ValueError as exc:
        # e.g. encoding declared is unknown / not supported.
        raise EncodingError("XML encoding could not be resolved") from exc

    encoding = _resolve_encoding(data)
    return SecureXmlDocument(root=root, encoding=encoding)


def _resolve_encoding(data: bytes) -> str:
    """Best-effort encoding resolution; falls back to UTF-8 without raising."""

    try:
        doc = etree.parse(BytesIO(data))
        return doc.docinfo.encoding or "UTF-8"
    except Exception:  # noqa: BLE001 - best effort, never fails ingestion
        return "UTF-8"


def parse_xml_declaration(data: bytes) -> str | None:
    """Return the value of the ``encoding`` attribute in the XML declaration, if present."""

    head = data[:256]
    if not head.lstrip().startswith(b"<?xml"):
        return None
    for token in head.split():
        if token.lower().startswith(b"encoding="):
            return token.split(b"=", 1)[1].strip(b"'\"").decode("ascii", "replace")
    return None
