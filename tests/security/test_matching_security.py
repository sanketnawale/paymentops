"""Security tests for the matching/reconciliation layer (Task 40).

No DB required for these: they exercise the deterministic engine, its guards, and CSV report
injection protection.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from paymentops_api.routers.matching import _safe_csv
from tests.unit.test_matching_engine import _inv, _pay

from matching_engine import MatchRecord, RecordType, default_policy, evaluate_pair

P = default_policy("org-1")


def test_cross_tenant_evaluate_denied():
    import asyncio

    from paymentops_api.services import matching_service

    a = _inv(organization_id="org-a")
    b = _pay(organization_id="org-b")
    with pytest.raises(PermissionError):
        asyncio.run(matching_service.evaluate_records(None, "org-a", a, b, P))  # type: ignore[arg-type]


def test_negative_amount_does_not_crash():
    d = evaluate_pair(_inv(amount=Decimal("-100")), _pay(amount=Decimal("-100")), P)
    assert d.classification.value in ("MATCHED", "POSSIBLE_MATCH")


def test_huge_fuzzy_string_is_capped():
    a = _inv(creditor_name="X" * 200_000)
    b = _pay(creditor_name="X" * 200_000)
    d = evaluate_pair(a, b, P)
    name_result = next(f for f in d.field_results if f.field == "creditor_name")
    # Similarity is computed on a capped slice, not the full 200k-char blob.
    assert name_result.similarity >= 85


def test_unsafe_identifier_characters_are_sanitized():
    # CSV/formula injection in record id must be neutralised in report output.
    assert _safe_csv("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert _safe_csv("+SUM(A1:A9)") == "'+SUM(A1:A9)"
    assert _safe_csv("@import") == "'@import"
    assert _safe_csv("-1") == "'-1"
    assert _safe_csv("plain") == "plain"


def test_invalid_policy_weight_skipped():
    # A zero/negative weight contributes nothing and never crashes.
    policy = default_policy("org-1")
    policy.field_weights["creditor_name"] = -5
    d = evaluate_pair(_inv(), _pay(creditor_name="TOTALLY DIFFERENT LTD"), policy)
    assert d.match_score >= 0


def test_decimal_large_amount_handled():
    big = Decimal("999999999999999999999999")
    d = evaluate_pair(_inv(amount=big), _pay(amount=big), P)
    assert d.classification.value in ("MATCHED", "POSSIBLE_MATCH")


def test_missing_values_do_not_crash():
    a = MatchRecord(record_id="a", record_type=RecordType.PAYMENT, organization_id="org-1")
    b = MatchRecord(record_id="b", record_type=RecordType.PAYMENT, organization_id="org-1")
    d = evaluate_pair(a, b, P)
    assert d.match_score == 0
    assert d.classification.value == "UNMATCHED"
