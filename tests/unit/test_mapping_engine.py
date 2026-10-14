"""Unit tests for the mapping engine (JSON/CSV/custom XML -> canonical)."""

from __future__ import annotations

from lxml import etree

from mapping_engine import (
    FieldMapping,
    FieldRequirement,
    MappingDefinition,
    SourceFormat,
    map_to_canonical,
    validate_mapping,
)


def test_map_json_to_canonical():
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.JSON,
        record_selector="$.payments[*]",
        fields=[
            FieldMapping(
                source="$.id", target="instruction_id", required=FieldRequirement.REQUIRED
            ),
            FieldMapping(
                source="$.amount", target="amount.amount_minor", transforms=["parse_decimal"]
            ),
            FieldMapping(source="$.ccy", target="amount.currency"),
            FieldMapping(source="$.beneficiary.name", target="creditor.name"),
            FieldMapping(source="$.beneficiary.city", target="creditor.postal_address.town_name"),
            FieldMapping(source="$.beneficiary.country", target="creditor.postal_address.country"),
        ],
    )
    data = {
        "payments": [
            {
                "id": "P1",
                "amount": "100.00",
                "ccy": "EUR",
                "beneficiary": {"name": "ACME", "city": "Milano", "country": "IT"},
            }
        ]
    }
    res = map_to_canonical(m, data)
    tx = res.message.transactions[0]
    assert tx.instruction_id == "P1"
    assert tx.amount.amount_minor == 10000
    assert tx.amount.currency == "EUR"
    assert tx.creditor.name == "ACME"
    assert tx.creditor.postal_address.town_name == "Milano"
    assert tx.creditor.postal_address.country == "IT"
    assert res.issues == []


def test_map_csv_to_canonical():
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.CSV,
        fields=[
            FieldMapping(source="beneficiary_name", target="creditor.name"),
            FieldMapping(source="beneficiary_city", target="creditor.postal_address.town_name"),
            FieldMapping(
                source="amount", target="amount.amount_minor", transforms=["parse_decimal"]
            ),
        ],
    )
    rows = [
        {"beneficiary_name": "Acme", "beneficiary_city": "Milano", "amount": "50.00"},
        {"beneficiary_name": "Beta", "beneficiary_city": "Roma", "amount": "25.00"},
    ]
    res = map_to_canonical(m, rows)
    assert len(res.message.transactions) == 2
    assert res.message.transactions[0].creditor.name == "Acme"
    assert res.message.transactions[0].amount.amount_minor == 5000


def test_map_custom_xml_to_canonical():
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.CUSTOM_XML,
        record_selector="//Payment",
        fields=[
            FieldMapping(source="Beneficiary/Name", target="creditor.name"),
            FieldMapping(source="Beneficiary/City", target="creditor.postal_address.town_name"),
            FieldMapping(
                source="Amount", target="amount.amount_minor", transforms=["parse_decimal"]
            ),
        ],
    )
    xml = etree.fromstring(
        b"<Root><Payment><Beneficiary><Name>ACME</Name><City>Milano</City></Beneficiary><Amount>75.00</Amount></Payment></Root>"
    )
    res = map_to_canonical(m, xml)
    tx = res.message.transactions[0]
    assert tx.creditor.name == "ACME"
    assert tx.creditor.postal_address.town_name == "Milano"
    assert tx.amount.amount_minor == 7500


def test_required_missing_produces_mapping_finding():
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.JSON,
        record_selector="$.payments[*]",
        fields=[
            FieldMapping(source="$.id", target="instruction_id", required=FieldRequirement.REQUIRED)
        ],
    )
    res = map_to_canonical(m, {"payments": [{}]})
    assert any(i.code == "MAP-001" for i in res.issues)


def test_validation_rejects_unknown_target_and_unsupported_transform():
    m = MappingDefinition(
        mapping_version="v1",
        source_format=SourceFormat.JSON,
        record_selector="$.p[*]",
        fields=[
            FieldMapping(source="$.x", target="not_a_field"),
            FieldMapping(source="$.y", target="creditor.name", transforms=["eval("]),
        ],
    )
    v = validate_mapping(m)
    assert v.valid is False
    codes = {e.code for e in v.errors}
    assert "MAP-004" in codes and "MAP-006" in codes
