"""Unit tests for API client auth hashing and geography coverage."""

from __future__ import annotations

from paymentops_api.auth import hash_secret, verify_secret
from paymentops_api.services.integration_analysis_service import compute_coverage

from payment_domain.models import (
    Party,
    PaymentMessage,
    PaymentTransaction,
    PostalAddress,
)


def test_secret_hash_roundtrip():
    stored = hash_secret("s3cret")
    assert stored != "s3cret"
    assert verify_secret("s3cret", stored) is True
    assert verify_secret("wrong", stored) is False


def test_coverage_supported():
    msg = PaymentMessage(
        transactions=[
            PaymentTransaction(creditor=Party(postal_address=PostalAddress(country="IT")))
        ]
    )
    assert compute_coverage(msg) == "SUPPORTED"


def test_coverage_unsupported_geography():
    msg = PaymentMessage(
        transactions=[
            PaymentTransaction(creditor=Party(postal_address=PostalAddress(country="US")))
        ]
    )
    assert compute_coverage(msg) == "UNSUPPORTED_GEOGRAPHY"


def test_coverage_unknown_when_no_address():
    msg = PaymentMessage(transactions=[PaymentTransaction()])
    assert compute_coverage(msg) == "UNKNOWN"
