"""Unit tests for the canonical payment domain models."""

from __future__ import annotations

from payment_domain.models import (
    AddressReadiness,
    CandidateStatus,
    FieldStatus,
    FieldValue,
    MonetaryAmount,
    PaymentMessage,
    PaymentTransaction,
    PostalAddress,
)


def test_canonical_message_defaults():
    msg = PaymentMessage()
    assert msg.transactions == []
    assert msg.validation_status.value == "pending"
    assert msg.source_format.value == "unknown"


def test_field_value_distinguishes_original_from_normalized():
    fv = FieldValue(original="Italy", normalized="IT", status=FieldStatus.NORMALIZED)
    assert fv.original == "Italy"
    assert fv.normalized == "IT"
    assert fv.value == "IT"


def test_postal_address_preserves_original_fields():
    addr = PostalAddress(
        country="IT",
        town_name="Milano",
        original_fields={"Ctry": "IT", "TwnNm": "Milano"},
        normalized_fields={"country": "IT"},
    )
    assert addr.original_fields["Ctry"] == "IT"
    assert addr.normalized_fields["country"] == "IT"
    # Original evidence is never overwritten.
    assert addr.country == "IT"


def test_repr_redacts_financial_fields():
    tx = PaymentTransaction(
        instruction_id="X",
        amount=MonetaryAmount(amount_minor=1000, currency="EUR"),
        debtor_account=None,
        creditor_account=None,
    )
    r = repr(tx)
    assert "amount_minor=1000" not in r
    assert "instruction_id" in r


def test_readiness_and_candidate_status_enums():
    assert AddressReadiness.READY.value == "READY"
    assert CandidateStatus.VALIDATED.value == "VALIDATED"
