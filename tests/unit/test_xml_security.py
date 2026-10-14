"""Unit tests for secure XML ingestion (DTD/XXE, size limits, error taxonomy)."""

from __future__ import annotations

import pytest

from iso_engine.xml_errors import (
    MalformedXmlError,
    PayloadTooLargeError,
    ProhibitedEntityError,
    UnsupportedMessageTypeError,
)
from iso_engine.xml_security import secure_parse

VALID = (
    b'<?xml version="1.0"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">'
    b"<FIToFICstmrCdtTrf/></Document>"
)


def test_secure_parse_valid():
    doc = secure_parse(VALID)
    assert doc.root.tag.endswith("Document")


def test_secure_parse_malformed():
    with pytest.raises(MalformedXmlError):
        secure_parse(b"<Document><unclosed</Document>")


def test_secure_parse_empty():
    with pytest.raises(MalformedXmlError):
        secure_parse(b"")


def test_secure_parse_payload_too_large():
    with pytest.raises(PayloadTooLargeError):
        secure_parse(VALID, max_bytes=10)


def test_dtd_rejected():
    dtd = b"<!DOCTYPE Document [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>" + VALID
    with pytest.raises(ProhibitedEntityError):
        secure_parse(dtd)


def test_entity_declaration_rejected():
    entity = b'<!ENTITY xxe "boom">' + VALID
    with pytest.raises(ProhibitedEntityError):
        secure_parse(entity)


def test_no_network_resolution():
    # A DTD with an external SYSTEM reference must never be resolved.
    payload = b'<!DOCTYPE Document [<!ENTITY ext SYSTEM "http://example.com/x">]>' + VALID
    with pytest.raises(ProhibitedEntityError):
        secure_parse(payload)


def test_unsupported_namespace_identified():
    from iso_engine.pacs008.identifier import identify_pacs008

    doc = secure_parse(
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.11">'
        b"<FIToFICstmrCdtTrf/></Document>"
    )
    with pytest.raises(UnsupportedMessageTypeError):
        identify_pacs008(doc.root)


def test_encoding_resolution():
    doc = secure_parse(
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Document xmlns="urn:x"><FIToFICstmrCdtTrf/></Document>'
    )
    assert doc.encoding.upper() == "UTF-8"
