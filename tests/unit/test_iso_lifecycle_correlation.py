"""Deterministic ISO lifecycle correlation tests (Task 33 golden cases)."""

from __future__ import annotations

from iso_engine.lifecycle.correlation import (
    CorrelationProfile,
    correlate_profiles,
    profile_from_status_report,
)
from payment_domain.models import CorrelationStatus


def _tx(e2e=None, instr=None, txid=None, amount=1250000, ccy="EUR", ref=None):
    from payment_domain.models import (
        MonetaryAmount,
        PaymentTransaction,
        RemittanceInformation,
    )

    return PaymentTransaction(
        end_to_end_id=e2e,
        instruction_id=instr,
        transaction_id=txid,
        amount=MonetaryAmount(amount_minor=amount, currency=ccy),
        remittance=RemittanceInformation(reference=ref) if ref else None,
    )


def _profile(**kw):
    base = {
        "message_id": None,
        "original_message_id": None,
        "instruction_id": "INSTR-0001",
        "end_to_end_id": "E2E-0001",
        "transaction_id": "TX-0001",
        "amount": 1250000,
        "currency": "EUR",
        "reference": None,
        "account": None,
    }
    base.update(kw)
    return CorrelationProfile(**base)


def test_correlated_via_end_to_end_and_amount():
    a = _profile(end_to_end_id="E2E-0001", message_id="MSG-A")
    b = _profile(end_to_end_id="E2E-0001", original_message_id="MSG-A")
    r = correlate_profiles(a, b)
    assert r.status == CorrelationStatus.CORRELATED
    assert "END_TO_END_ID_EXACT" in r.evidence
    assert "ORIGINAL_MESSAGE_ID_EXACT" in r.evidence


def test_possible_correlation_via_amount_currency():
    a = _profile(end_to_end_id=None, instruction_id=None, transaction_id=None)
    b = _profile(end_to_end_id=None, instruction_id=None, transaction_id=None)
    r = correlate_profiles(a, b)
    assert r.status == CorrelationStatus.POSSIBLE_CORRELATION
    assert "AMOUNT_EXACT" in r.evidence and "CURRENCY_EXACT" in r.evidence


def test_conflict_on_different_end_to_end_id():
    a = _profile(end_to_end_id="E2E-0001")
    b = _profile(end_to_end_id="E2E-DIFFERENT")
    r = correlate_profiles(a, b)
    assert r.status == CorrelationStatus.CONFLICT
    assert "END_TO_END_ID_CONFLICT" in r.conflicts


def test_no_fuzzy_name_correlation():
    # Same fuzzy party but different end-to-end id -> not correlated.
    a = _profile(end_to_end_id="E2E-0001", amount=None, currency=None)
    b = _profile(end_to_end_id="E2E-OTHER", amount=None, currency=None)
    r = correlate_profiles(a, b)
    assert r.status in (CorrelationStatus.UNRESOLVED, CorrelationStatus.CONFLICT)
    assert "REFERENCE" not in " ".join(r.evidence)


def test_unresolved_when_no_identifiers():
    a = CorrelationProfile()
    b = CorrelationProfile()
    r = correlate_profiles(a, b)
    assert r.status == CorrelationStatus.UNRESOLVED


def test_status_report_profiles_include_original_message_id():
    from payment_domain.models import (
        LifecycleStatusReport,
        RelatedPaymentReference,
        TransactionStatus,
    )

    report = LifecycleStatusReport(
        message_id="STS-1",
        original_message_id="PAIN-1",
        original_message_definition="pain.001.001.13",
        group_status_raw="ACCP",
        transaction_statuses=[
            TransactionStatus(
                original_end_to_end_id="E2E-1",
                original_instruction_id="INSTR-1",
                raw_iso_status="ACCP",
                reference=RelatedPaymentReference(transaction_id="TX-1"),
            )
        ],
    )
    profiles = profile_from_status_report(report)
    assert profiles[0].original_message_id == "PAIN-1"
    assert profiles[0].end_to_end_id == "E2E-1"
