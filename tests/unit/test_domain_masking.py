"""Unit tests for the canonical payment domain model and masking helpers."""

from __future__ import annotations

from masking import mask_account, mask_iban
from payment_domain.models import PaymentEnvelope, PaymentIntent, SourceFormat


def test_canonical_envelope_defaults():
    env = PaymentEnvelope()
    assert env.intent == PaymentIntent.UNSPECIFIED
    assert env.source_format == SourceFormat.UNKNOWN
    assert env.raw_payload is None


def test_repr_redacts_financial_fields():
    env = PaymentEnvelope(
        source_format=SourceFormat.XML_PACS_008,
        raw_payload="<PmtInf><DbtrAcct>DE89370400440532013000</DbtrAcct></PmtInf>",
    )
    # repr must not contain the account number.
    assert "DE89370400440532013000" not in repr(env)
    assert "raw_payload" in repr(env)


def test_zero_retention_envelope_allows_none_payload():
    env = PaymentEnvelope(raw_payload=None)
    assert env.raw_payload is None


def test_mask_iban_and_account():
    assert mask_iban("DE89370400440532013000").endswith("3000")
    assert mask_iban("DE89370400440532013000").startswith("DE89")
    assert mask_iban("") == "[REDACTED]"
    assert mask_account("1234567890").endswith("7890")
    assert mask_account("12") == "**"
    assert mask_account("") == "[REDACTED]"
