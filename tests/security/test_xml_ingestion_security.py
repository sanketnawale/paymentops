"""Security-focused tests: XXE/DTD, oversized payload, no raw payload in logs/errors.

These prove untrusted XML is handled safely and no payload content leaks into responses.
"""

from __future__ import annotations

import pytest
from tests.conftest import load_fixture

from iso_engine.xml_errors import MalformedXmlError, PayloadTooLargeError, ProhibitedEntityError
from iso_engine.xml_security import secure_parse


def test_xxe_external_entity_rejected():
    payload = load_fixture("dtd_xxe")
    with pytest.raises(ProhibitedEntityError):
        secure_parse(payload)


def test_external_entity_not_resolved():
    payload = load_fixture("dtd_xxe")
    # Even if parsing were allowed, entities must never be resolved to files.
    from iso_engine.xml_security import secure_parse as sp

    try:
        sp(payload)
        assert False, "should have raised"
    except ProhibitedEntityError:
        pass


def test_oversized_payload_rejected():
    payload = load_fixture("valid_structured") + b" " * 2000
    with pytest.raises(PayloadTooLargeError):
        secure_parse(payload, max_bytes=100)


def test_malformed_xml_rejected_without_leak():
    with pytest.raises(MalformedXmlError) as exc:
        secure_parse(b"<Document><broken")
    # Error message must not echo the payload fragment.
    assert "Document" not in exc.value.message


def test_raw_payload_absent_from_analyze_error_response(client):
    payload = load_fixture("dtd_xxe").decode()
    r = client.post("/api/v1/payments/analyze", json={"xml": payload, "persist": False})
    assert r.status_code == 400
    body = r.json()
    assert "file:///etc/passwd" not in r.text
    assert body["error"]["code"] == "XML-003"


def test_zero_retention_no_raw_xml_persisted(client):
    # persist=false -> the response contains only metadata + hash, no raw XML echo.
    xml = load_fixture("valid_structured").decode()
    r = client.post(
        "/api/v1/payments/analyze",
        json={"xml": xml, "persist": False, "include_candidate_xml": False},
    )
    body = r.json()
    assert "<Document" not in r.text  # no raw XML echoed back
    assert body["input_hash"]


def test_no_raw_address_in_analyze_response(client):
    xml = load_fixture("address_adrline_only").decode()
    r = client.post(
        "/api/v1/payments/analyze",
        json={"xml": xml, "persist": False, "include_candidate_xml": False},
    )
    assert r.status_code == 200
    # The raw AdrLine content must not be echoed back when candidate XML is excluded.
    assert "Main Street 10, 20121 Milano, Italy" not in r.text
    # No IBANs in the response.
    assert "DE89370400440532013000" not in r.text


def test_swift_fallback_does_not_leak_address():
    from address_engine.providers import SwiftDerivedAddressProvider
    from payment_domain.models import PostalAddress

    provider = SwiftDerivedAddressProvider(
        "http://127.0.0.1:59999", timeout_seconds=0.2, max_retries=0
    )
    analysis = provider.analyze(PostalAddress(address_lines=["Via Confidenziale 7, Roma, Italy"]))
    # The fallback analysis must not carry the raw address in its evidence.
    assert all("Confidenziale" not in e for e in analysis.evidence)
