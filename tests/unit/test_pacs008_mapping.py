"""Unit tests for pacs.008 -> canonical mapping and XSD validation."""

from __future__ import annotations

import pytest
from tests.conftest import load_fixture

from iso_engine.pacs008.adapter import map_pacs008_to_canonical
from iso_engine.pacs008.identifier import identify_pacs008
from iso_engine.xml_errors import UnsupportedMessageTypeError
from iso_engine.xml_security import secure_parse
from iso_engine.xsd_validator import validate_pacs008


def test_mapping_valid_complete_message():
    doc = secure_parse(load_fixture("valid_structured"))
    version = identify_pacs008(doc.root)
    msg = map_pacs008_to_canonical(doc.root, version)
    assert msg.message_type == "pacs.008.001.08"
    assert msg.message_id == "MSGID-VALID-001"
    assert len(msg.transactions) == 1
    tx = msg.transactions[0]
    assert tx.instruction_id == "INST001"
    assert tx.amount.amount_minor == 100000
    assert tx.amount.currency == "EUR"
    assert tx.debtor.name == "Acme GmbH"
    assert tx.debtor.postal_address.country == "IT"
    assert tx.debtor.postal_address.town_name == "Milano"
    assert tx.debtor_account.iban == "DE89370400440532013000"
    assert tx.debtor_agent.bic == "DEUTDEFF"
    assert tx.remittance.unstructured == ["Invoice 123"]


def test_mapping_multiple_transactions():
    doc = secure_parse(load_fixture("multiple_txns"))
    version = identify_pacs008(doc.root)
    msg = map_pacs008_to_canonical(doc.root, version)
    assert len(msg.transactions) == 2
    assert msg.transactions[1].creditor.name == "Bianchi S.p.A."


def test_mapping_missing_optional_fields():
    doc = secure_parse(load_fixture("missing_country"))
    version = identify_pacs008(doc.root)
    msg = map_pacs008_to_canonical(doc.root, version)
    tx = msg.transactions[0]
    assert tx.debtor.postal_address.country is None
    assert tx.debtor.postal_address.town_name == "Milano"


def test_xsd_valid_on_valid():
    doc = secure_parse(load_fixture("valid_structured"))
    version = identify_pacs008(doc.root)
    result = validate_pacs008(doc.root, version)
    assert result.valid is True
    assert result.issues == []


def test_xsd_invalid_on_country_full_name():
    doc = secure_parse(load_fixture("country_full_name"))
    version = identify_pacs008(doc.root)
    result = validate_pacs008(doc.root, version)
    assert result.valid is False
    assert any(i.code == "ISO-XSD-001" for i in result.issues)


def test_unsupported_version_rejected():
    doc = secure_parse(load_fixture("unsupported_namespace"))
    with pytest.raises(UnsupportedMessageTypeError):
        identify_pacs008(doc.root)


def test_malformed_address_structure_handled():
    # An address with AdrLine only maps without error.
    doc = secure_parse(load_fixture("address_adrline_only"))
    version = identify_pacs008(doc.root)
    msg = map_pacs008_to_canonical(doc.root, version)
    tx = msg.transactions[0]
    assert tx.debtor.postal_address.address_lines
