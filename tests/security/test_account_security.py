"""Security tests for camt account-report ingestion (Week 6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from paymentops_api.routers.account import _safe_csv

from address_engine.providers import CloudNovaAddressProvider
from analysis.pipeline import AnalysisPipeline
from iso_engine import build_default_registry, secure_parse
from iso_engine.xml_errors import PayloadTooLargeError, ProhibitedEntityError
from rules_engine import build_address_ruleset

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "iso"
REG = build_default_registry()
PIPELINE = AnalysisPipeline(
    address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
)


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_camt054_dtd_rejected():
    payload = (
        b'<?xml version="1.0"?><!DOCTYPE Document [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.14">'
        b"<BkToCstmrDbtCdtNtfctn><GrpHdr><MsgId>&xxe;</MsgId></GrpHdr></BkToCstmrDbtCdtNtfctrn></Document>"
    )
    with pytest.raises(ProhibitedEntityError):
        secure_parse(payload)


def test_camt053_oversized_rejected():
    big = _load("camt053-00114-valid.xml") + b" " * (1_200_000)
    with pytest.raises(PayloadTooLargeError):
        secure_parse(big)


def test_camt_unsupported_version_rejected():
    xml = (
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08">'
        b"<BkToCstmrStmt/></Document>"
    )
    doc = secure_parse(xml)
    with pytest.raises(Exception):
        REG.resolve_root(doc.root)


def test_camt_entry_count_limit():
    entries = "".join(
        f'<Ntry><Amt Ccy="EUR">10.00</Amt><CdtDbtInd>DBIT</CdtDbtInd>'
        f"<NtryDtls><TxDtls><Refs><EndToEndId>E{i}</EndToEndId></Refs></TxDtls></NtryDtls></Ntry>"
        for i in range(5)
    )
    xml = (
        '<?xml version="1.0"?>'
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.14">'
        "<BkToCstmrDbtCdtNtfctn><GrpHdr><MsgId>M</MsgId><CreDtTm>2026-01-01T00:00:00Z</CreDtTm></GrpHdr>"
        f"<Ntfctn><Id>N</Id>{entries}</Ntfctn></BkToCstmrDbtCdtNtfctn></Document>"
    ).encode()
    with pytest.raises(PayloadTooLargeError):
        PIPELINE.analyze_iso(xml, REG, max_transactions=2)


def test_camt_csv_formula_injection_neutralized():
    assert _safe_csv("=cmd|' /C calc'!A0").startswith("'")
    assert _safe_csv("+1").startswith("'")
    assert _safe_csv("@import").startswith("'")
    assert _safe_csv("plain") == "plain"


def test_camt_negative_amount_parses_safely():
    xml = (
        b'<?xml version="1.0"?>'
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.14">'
        b"<BkToCstmrDbtCdtNtfctn><GrpHdr><MsgId>M</MsgId>"
        b"<CreDtTm>2026-01-01T00:00:00Z</CreDtTm></GrpHdr>"
        b'<Ntfctn><Id>N</Id><Ntry><Amt Ccy="EUR">-10.00</Amt>'
        b"<CdtDbtInd>DBIT</CdtDbtInd></Ntry></Ntfctn>"
        b"</BkToCstmrDbtCdtNtfctn></Document>"
    )
    result = PIPELINE.analyze_iso(xml, REG)
    assert result.message_version == "camt.054.001.14"
