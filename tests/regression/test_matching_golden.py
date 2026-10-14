"""Golden match outcomes (Task 28) - deterministic, development baseline.

These encode the expected classification for curated scenarios. Thresholds are DEVELOPMENT
BASELINE (see docs/matching-calibration.md) and must be re-validated with customer historical
data before production use.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from matching_engine import (
    MatchClassification,
    MatchRecord,
    RecordType,
    default_policy,
    evaluate_pair,
)

P = default_policy("org-1")


def _rec(rid: str, **kw) -> MatchRecord:
    base = {
        "record_id": rid,
        "record_type": RecordType.PAYMENT,
        "organization_id": "org-1",
        "amount": Decimal("12500"),
        "currency": "EUR",
        "remittance_reference": "INV92881",
        "creditor_name": "ACME INDUSTRIA SPA",
        "value_date": date(2026, 1, 10),
    }
    base.update(kw)
    return MatchRecord(**base)


CASES = [
    # (name, a, b, expected_classification, expected_min_score)
    (
        "A-exact",
        _rec("a1"),
        _rec("b1"),
        MatchClassification.MATCHED,
        85,
    ),
    (
        "B-fuzzy-party",
        _rec("a2", creditor_name="ACME INDUSTRIA S.P.A."),
        _rec("b2", creditor_name="ACME INDUSTRIA SPA"),
        MatchClassification.MATCHED,
        85,
    ),
    (
        "C-currency-conflict",
        _rec("a3", currency="EUR"),
        _rec("b3", currency="USD"),
        MatchClassification.REVIEW_REQUIRED,
        0,
    ),
    (
        "D-amount-conflict",
        _rec("a4", amount=Decimal("12500")),
        _rec("b4", amount=Decimal("400")),
        MatchClassification.REVIEW_REQUIRED,
        0,
    ),
    (
        "E-uncorrelated",
        _rec(
            "a5",
            remittance_reference="INV1",
            amount=Decimal("10"),
            currency="USD",
            creditor_name="ALPHA CORP",
            value_date=date(2026, 1, 1),
        ),
        _rec(
            "b5",
            remittance_reference="INV2",
            amount=Decimal("20"),
            currency="GBP",
            creditor_name="BETA GROUP",
            value_date=date(2026, 3, 1),
        ),
        MatchClassification.UNMATCHED,
        0,
    ),
    (
        "F-date-within-tolerance",
        _rec("a6", value_date=date(2026, 1, 10)),
        _rec("b6", value_date=date(2026, 1, 11)),
        MatchClassification.MATCHED,
        85,
    ),
    (
        "G-false-positive-name-trap",
        _rec("a7", creditor_name="ACME INDUSTRIA SPA"),
        _rec("b7", creditor_name="ACME LOGISTICS SRL"),
        MatchClassification.REVIEW_REQUIRED,
        0,
    ),
]


@pytest.mark.parametrize("name,a,b,expected,min_score", CASES)
def test_golden_case(name, a, b, expected, min_score):
    d = evaluate_pair(a, b, P)
    assert d.classification == expected, f"{name}: {d.classification} (score={d.match_score})"
    assert d.match_score >= min_score
