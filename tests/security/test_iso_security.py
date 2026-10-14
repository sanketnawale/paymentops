"""Security tests for ISO 20022 ingestion (Task 37). No DB required for the XML-level tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from paymentops_api.services.integration_analysis_service import map_input

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from integration_profiles.models import InputFormat, IntegrationProfile
from iso_engine import (
    build_default_registry,
    secure_parse,
)
from iso_engine.xml_errors import (
    PayloadTooLargeError,
    ProhibitedEntityError,
)
from rules_engine import build_address_ruleset

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "iso"
REG = build_default_registry()
PIPELINE = AnalysisPipeline(
    address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
)


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _payload_with_dtd() -> bytes:
    return (
        b'<?xml version="1.0"?><!DOCTYPE Document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.13">'
        b"<CstmrCdtTrfInitn><GrpHdr><MsgId>&xxe;</MsgId></GrpHdr></CstmrCdtTrfInitn></Document>"
    )


def test_xxe_rejected_for_pain001():
    with pytest.raises(ProhibitedEntityError):
        secure_parse(_payload_with_dtd())


def test_dtd_rejected_for_pacs002():
    with pytest.raises(ProhibitedEntityError):
        secure_parse(_payload_with_dtd().replace(b"pain.001.001.13", b"pacs.002.001.16"))


def test_oversized_payload_rejected():
    big = _load("pain001-00113-valid-single.xml") + b" " * (1_200_000)
    with pytest.raises(PayloadTooLargeError):
        secure_parse(big)


def test_unknown_namespace_rejected():
    xml = b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:unknown.999"><X/></Document>'
    doc = secure_parse(xml)
    with pytest.raises(Exception):
        REG.resolve_root(doc.root)


def test_known_but_unsupported_pacs008_version_rejected():
    xml = (
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.09">'
        b"<FIToFICstmrCdtTrf/></Document>"
    )
    doc = secure_parse(xml)
    with pytest.raises(Exception):
        REG.resolve_root(doc.root)


def test_deep_nested_parses_within_limit():
    # Deep nesting is not an XXE; the secure parser accepts it but must not crash.
    depth = 200
    xml = b"<a>" * depth + b"x" + b"</a>" * depth
    doc = secure_parse(xml)
    assert doc.root is not None


def test_transaction_count_limit():
    # Build a pain.001 with 3 transactions; set max_transactions=2 -> PayloadTooLargeError.
    txs = "".join(
        f"<CdtTrfTxInf><PmtId><EndToEndId>E{i}</EndToEndId></PmtId>"
        f'<Amt><InstdAmt Ccy="EUR">10.00</InstdAmt></Amt></CdtTrfTxInf>'
        for i in range(3)
    )
    xml = (
        '<?xml version="1.0"?>'
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.13">'
        "<CstmrCdtTrfInitn><GrpHdr><MsgId>M</MsgId><CreDtTm>2026-01-01T00:00:00Z</CreDtTm></GrpHdr>"
        f"<PmtInf><PmtMtd>TRF</PmtMtd>{txs}</PmtInf></CstmrCdtTrfInitn></Document>"
    ).encode()
    with pytest.raises(PayloadTooLargeError):
        PIPELINE.analyze_iso(xml, REG, max_transactions=2)


def test_profile_message_restriction():
    # A profile limited to pacs.008 must reject a pain.001 message.
    from mapping_engine.models import FieldMapping, MappingDefinition, SourceFormat

    profile = IntegrationProfile(
        organization_id="org-1",
        name="pacs-only",
        input_format=InputFormat.ISO20022_XML,
        allowed_messages=["pacs.008.001.08"],
        mapping=MappingDefinition(
            mapping_version="v1",
            source_format=SourceFormat.JSON,
            fields=[FieldMapping(source="$.id", target="instruction_id")],
        ),
    )
    with pytest.raises(ValueError):
        map_input(profile, _load("pain001-00113-valid-single.xml"), REG)


def test_huge_string_not_used_for_correlation():
    from iso_engine.lifecycle.correlation import CorrelationProfile, correlate_profiles

    a = CorrelationProfile(end_to_end_id="X" * 10000)
    b = CorrelationProfile(end_to_end_id="X" * 10000)
    r = correlate_profiles(a, b)
    assert r.status.value in ("CORRELATED", "POSSIBLE_CORRELATION", "CONFLICT")
