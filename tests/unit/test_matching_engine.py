"""Deterministic matching engine unit tests (no DB/broker).

Covers the Week 4 synthetic scenarios (Task 27) at the pair-evaluation level. Reconciliation
one-to-many/many-to-one ambiguity and duplicate detection are covered separately.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from matching_engine import (
    MatchClassification,
    MatchRecord,
    RecordType,
    default_policy,
    evaluate_pair,
    normalize_record,
)
from matching_engine.normalization import (
    normalize_iban,
    normalize_name,
    normalize_reference,
)


def _inv(**kw) -> MatchRecord:
    base = {
        "record_id": "inv-1",
        "record_type": RecordType.INVOICE,
        "organization_id": "org-1",
        "amount": Decimal("12500"),
        "currency": "EUR",
        "remittance_reference": "INV-92881",
        "creditor_name": "ACME INDUSTRIA SPA",
        "value_date": date(2026, 1, 10),
    }
    base.update(kw)
    return MatchRecord(**base)


def _pay(**kw) -> MatchRecord:
    base = {
        "record_id": "pay-1",
        "record_type": RecordType.PAYMENT,
        "organization_id": "org-1",
        "amount": Decimal("12500"),
        "currency": "EUR",
        "remittance_reference": "INV92881",
        "creditor_name": "ACME INDUSTRIA S.P.A.",
        "value_date": date(2026, 1, 10),
    }
    base.update(kw)
    return MatchRecord(**base)


P = default_policy("org-1")


def test_exact_match_classified_matched():
    d = evaluate_pair(_inv(), _pay(), P)
    assert d.classification == MatchClassification.MATCHED
    assert d.match_score >= 85
    assert "MATCH-AMOUNT-EXACT" in d.explanation_codes
    assert "MATCH-CURRENCY-EXACT" in d.explanation_codes
    assert "MATCH-REF-EXACT" in d.explanation_codes
    assert not d.critical_conflicts


def test_punctuation_name_difference_scores_high():
    d = evaluate_pair(_inv(), _pay(), P)
    name_result = next(f for f in d.field_results if f.field == "creditor_name")
    assert name_result.similarity >= 85


def test_reference_formatting_difference_matches():
    # INV-92881 vs INV92881 -> normalized identical.
    assert normalize_reference("INV-92881") == normalize_reference("INV92881")
    d = evaluate_pair(_inv(), _pay(), P)
    ref_result = next(f for f in d.field_results if f.field == "remittance_reference")
    assert ref_result.status.value == "EXACT"
    assert ref_result.explanation_code == "MATCH-REF-EXACT"


def test_same_amount_currency_different_party_review_required():
    d = evaluate_pair(_inv(), _pay(creditor_name="GLOBEX GLOBAL SERVICES", record_id="pay-2"), P)
    assert d.classification == MatchClassification.REVIEW_REQUIRED
    assert any(c.field == "creditor_name" for c in d.critical_conflicts)


def test_same_party_wrong_amount_review_required():
    d = evaluate_pair(_inv(), _pay(amount=Decimal("500"), record_id="pay-3"), P)
    assert d.classification == MatchClassification.REVIEW_REQUIRED
    assert any(c.field == "amount" for c in d.critical_conflicts)


def test_date_within_tolerance_matches():
    d = evaluate_pair(
        _inv(),
        _pay(value_date=date(2026, 1, 11), record_id="pay-4"),  # +1 day
        P,
    )
    assert d.classification == MatchClassification.MATCHED
    assert "MATCH-DATE-WITHIN-TOLERANCE" in d.explanation_codes


def test_date_outside_tolerance_reported():
    d = evaluate_pair(
        _inv(),
        _pay(value_date=date(2026, 2, 1), record_id="pay-5"),  # 22 days
        P,
    )
    date_result = next(f for f in d.field_results if f.field == "value_date")
    assert date_result.status.value == "MISMATCH"


def test_currency_conflict_review_required():
    d = evaluate_pair(_inv(), _pay(currency="USD", record_id="pay-6"), P)
    assert d.classification == MatchClassification.REVIEW_REQUIRED
    assert any(c.field == "currency" for c in d.critical_conflicts)


def test_unicode_name_high_similarity():
    d = evaluate_pair(
        _inv(creditor_name="Müller & Söhne GmbH"),
        _pay(creditor_name="Müller und Söhne GmbH", record_id="pay-7"),
        P,
    )
    name_result = next(f for f in d.field_results if f.field == "creditor_name")
    assert name_result.similarity >= 60


def test_similar_company_names_match():
    d = evaluate_pair(
        _inv(),
        _pay(creditor_name="ACME INDUSTRIA SPA (ITALY)", record_id="pay-8"),
        P,
    )
    assert d.classification in (MatchClassification.MATCHED, MatchClassification.POSSIBLE_MATCH)


def test_false_positive_trap_does_not_auto_match():
    # Same reference/amount/currency but genuinely different company -> routed to review.
    d = evaluate_pair(
        _inv(),
        _pay(creditor_name="ACME LOGISTICS SRL", record_id="pay-9"),
        P,
    )
    assert d.classification == MatchClassification.REVIEW_REQUIRED


def test_no_candidate_unmatched():
    d = evaluate_pair(
        _inv(),
        _pay(
            record_id="pay-10",
            remittance_reference="ZZZ-0001",
            amount=Decimal("9999"),
            currency="USD",
            creditor_name="UNRELATED PARTY INC",
        ),
        P,
    )
    assert d.classification == MatchClassification.UNMATCHED
    assert d.match_score < 40


def test_normalization_iban_removes_whitespace_and_case():
    assert normalize_iban("DE89 3704 0044 0532 0130 00") == "DE89370400440532013000"
    assert normalize_iban("IT60 X054 2811 1010 0000 0123 456") == "IT60X0542811101000000123456"


def test_normalization_name_canonicalizes_suffix():
    assert normalize_name("ACME INDUSTRIA S.P.A.") == normalize_name("ACME INDUSTRIA SPA")
    assert normalize_name("ACME INDUSTRIA S P A") == normalize_name("ACME INDUSTRIA SPA")


def test_normalize_record_preserves_original():
    inv = _inv()
    normalized = normalize_record(inv)
    assert inv.remittance_reference == "INV-92881"  # original untouched
    assert normalized.values["remittance_reference"] == "INV92881"


def test_score_not_a_probability():
    d = evaluate_pair(_inv(), _pay(), P)
    # match_score is a bounded deterministic score, never claimed as probability.
    assert 0 <= d.match_score <= 100
