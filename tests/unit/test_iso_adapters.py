"""ISO 20022 adapter tests for pain.001.001.13, pacs.009.001.13, pacs.002.001.16."""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_engine import (
    build_default_registry,
    map_pacs002_to_status,
    map_pacs009_to_canonical,
    map_pain001_to_canonical,
    secure_parse,
    validate_message,
)
from iso_engine.pacs002.namespace import SUPPORTED_PACS_002_VERSIONS
from iso_engine.pacs009.namespace import SUPPORTED_PACS_009_VERSIONS
from iso_engine.pain001.namespace import SUPPORTED_PAIN_001_VERSIONS
from payment_domain.models import LifecycleStatusReport, PaymentMessage

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "iso"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_pain001_adapter_maps_canonical():
    doc = secure_parse(_load("pain001-00113-valid-single.xml"))
    msg = map_pain001_to_canonical(doc.root, SUPPORTED_PAIN_001_VERSIONS["pain.001.001.13"])
    assert isinstance(msg, PaymentMessage)
    assert msg.message_type == "pain.001.001.13"
    assert msg.message_id == "PAIN-2026-0001"
    assert len(msg.transactions) == 1
    tx = msg.transactions[0]
    assert tx.end_to_end_id == "E2E-0001"
    assert tx.instruction_id == "INSTR-0001"
    assert tx.amount.amount_minor == 1250000
    assert tx.amount.currency == "EUR"
    assert tx.creditor.name == "Acme Industria SPA"
    assert tx.creditor.postal_address.town_name == "Berlin"
    assert tx.creditor_account.iban == "DE89370400440532013000"


def test_pain001_validation_passes():
    doc = secure_parse(_load("pain001-00113-valid-single.xml"))
    xsd = validate_message(doc.root, "pain.001.001.13")
    assert xsd.valid


def test_pacs009_adapter_maps_fi_transfer():
    doc = secure_parse(_load("pacs009-00113-valid.xml"))
    msg = map_pacs009_to_canonical(doc.root, SUPPORTED_PACS_009_VERSIONS["pacs.009.001.13"])
    assert isinstance(msg, PaymentMessage)
    assert msg.message_type == "pacs.009.001.13"
    tx = msg.transactions[0]
    assert tx.debtor_agent.bic == "ITBIC12345"
    assert tx.creditor_agent.bic == "DEBIC54321"
    assert tx.debtor.financial_institution.bic == "ITBIC12345"
    assert msg.source_metadata["settlement_method"] == "INDA"
    assert msg.source_metadata["variants"] == "CORE"


def test_pacs009_validation_passes():
    doc = secure_parse(_load("pacs009-00113-valid.xml"))
    xsd = validate_message(doc.root, "pacs.009.001.13")
    assert xsd.valid


def test_pacs002_maps_status_not_payment():
    doc = secure_parse(_load("pacs002-00116-accepted.xml"))
    report = map_pacs002_to_status(doc.root, SUPPORTED_PACS_002_VERSIONS["pacs.002.001.16"])
    assert isinstance(report, LifecycleStatusReport)
    assert not isinstance(report, PaymentMessage)
    assert report.original_message_id == "PAIN-2026-0001"
    assert report.original_message_definition == "pain.001.001.13"
    assert report.group_status_raw == "ACCP"
    assert report.group_status.value == "ACCEPTED"
    tx = report.transaction_statuses[0]
    assert tx.raw_iso_status == "ACCP"
    assert tx.normalized_status.value == "ACCEPTED"
    assert tx.original_end_to_end_id == "E2E-0001"


def test_pacs002_validation_passes():
    doc = secure_parse(_load("pacs002-00116-accepted.xml"))
    xsd = validate_message(doc.root, "pacs.002.001.16")
    assert xsd.valid


def test_unsupported_version_rejected():
    reg = build_default_registry()
    assert "pacs.008.001.09" not in reg
    with pytest.raises(Exception):
        reg.resolve("pacs.008.001.09")
