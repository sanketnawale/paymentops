"""Deterministic matching engine (pair evaluation).

Produces evidence, a normalized ``match_score`` (0..100), critical conflicts, and a
classification. This is the authoritative matching path (deterministic only). No LLM.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from rapidfuzz import fuzz

from matching_engine.models import (
    ComparisonType,
    CriticalConflict,
    FieldMatchResult,
    FieldStatus,
    MatchClassification,
    MatchDecision,
    MatchingPolicy,
    MatchRecord,
)
from matching_engine.normalization import normalize_record

# Max length of a string fed to fuzzy similarity (DoS guard). Evidence is never truncated;
# only the similarity input is capped.
MAX_FUZZY_LEN = 512

# A party-name similarity below this (when both names are present) is a review signal that
# blocks automatic MATCHED. Deterministic, documented in calibration. Tuned so punctuation
# /legal-form variants (e.g. 'ACME INDUSTRIA S.P.A.' vs 'ACME INDUSTRIA SPA') score ~100 and
# pass, while a genuinely different company ('... LOGISTICS SRL') is routed to review.
NAME_MISMATCH_THRESHOLD = 70.0

_ALGORITHMS: dict[str, Callable[[str, str], float]] = {
    "ratio": fuzz.ratio,
    "partial_ratio": fuzz.partial_ratio,
    "token_sort_ratio": fuzz.token_sort_ratio,
    "token_set_ratio": fuzz.token_set_ratio,
}


def _clamp_sim(value: float) -> float:
    return min(100.0, max(0.0, value))


def _sim(a: str | None, b: str | None, algorithm: str) -> float:
    if not a or not b:
        return 0.0
    fn = _ALGORITHMS.get(algorithm, fuzz.token_sort_ratio)
    a_capped = a[:MAX_FUZZY_LEN]
    b_capped = b[:MAX_FUZZY_LEN]
    return _clamp_sim(float(fn(a_capped, b_capped)))


def _field_status(na: Any, nb: Any) -> FieldStatus:
    if na is None or nb is None:
        return FieldStatus.MISSING
    return FieldStatus.EXACT


def _exact_result(
    field: str,
    na: Any,
    nb: Any,
    weight: float,
    critical: bool,
    ok_code: str,
) -> FieldMatchResult:
    if na is None or nb is None:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.EXACT,
            normalized_a=na,
            normalized_b=nb,
            similarity=0.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.MISSING,
            explanation_code="MATCH-FIELD-MISSING",
        )
    equal = str(na) == str(nb)
    return FieldMatchResult(
        field=field,
        comparison_type=ComparisonType.EXACT,
        normalized_a=na,
        normalized_b=nb,
        similarity=100.0 if equal else 0.0,
        weight=weight,
        critical=critical,
        status=FieldStatus.EXACT if equal else FieldStatus.MISMATCH,
        explanation_code=ok_code if equal else _conflict_code(field),
    )


def _conflict_code(field: str) -> str:
    mapping = {
        "currency": "MATCH-CRITICAL-CURRENCY-CONFLICT",
        "transaction_id": "MATCH-CRITICAL-TXID-CONFLICT",
        "debtor_account": "MATCH-CRITICAL-IBAN-CONFLICT",
        "creditor_account": "MATCH-CRITICAL-IBAN-CONFLICT",
        "amount": "MATCH-CRITICAL-AMOUNT-CONFLICT",
    }
    return mapping.get(field, "MATCH-CRITICAL-CONFLICT")


def _amount_result(
    field: str,
    na: Decimal | None,
    nb: Decimal | None,
    weight: float,
    critical: bool,
    policy: MatchingPolicy,
) -> FieldMatchResult:
    if na is None or nb is None:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.RANGE,
            normalized_a=na,
            normalized_b=nb,
            similarity=0.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.MISSING,
            explanation_code="MATCH-FIELD-MISSING",
        )
    if na == nb:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.RANGE,
            normalized_a=str(na),
            normalized_b=str(nb),
            similarity=100.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.EXACT,
            explanation_code="MATCH-AMOUNT-EXACT",
        )
    tolerance = policy.amount_tolerances.get(field)
    within = False
    if tolerance is not None:
        diff = abs(na - nb)
        base = max(abs(na), abs(nb), Decimal("1"))
        within = diff <= (base * (Decimal(str(tolerance)) / Decimal("100")))
        # Also allow absolute tolerance if configured as such (fraction of base).
    if within:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.RANGE,
            normalized_a=str(na),
            normalized_b=str(nb),
            similarity=100.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.EXACT,
            explanation_code="MATCH-AMOUNT-WITHIN-TOLERANCE",
        )
    return FieldMatchResult(
        field=field,
        comparison_type=ComparisonType.RANGE,
        normalized_a=str(na),
        normalized_b=str(nb),
        similarity=0.0,
        weight=weight,
        critical=critical,
        status=FieldStatus.MISMATCH,
        explanation_code="MATCH-CRITICAL-AMOUNT-CONFLICT" if critical else "MATCH-AMOUNT-MISMATCH",
    )


def _date_result(
    field: str,
    na: str | None,
    nb: str | None,
    weight: float,
    critical: bool,
    policy: MatchingPolicy,
) -> FieldMatchResult:
    if na is None or nb is None:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.RANGE,
            normalized_a=na,
            normalized_b=nb,
            similarity=0.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.MISSING,
            explanation_code="MATCH-FIELD-MISSING",
        )
    try:
        da = date.fromisoformat(str(na)[:10])
        db = date.fromisoformat(str(nb)[:10])
    except ValueError:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.RANGE,
            normalized_a=na,
            normalized_b=nb,
            similarity=0.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.MISMATCH,
            explanation_code="MATCH-DATE-INVALID",
        )
    tolerance = policy.date_tolerances.get(field, 0)
    delta = abs((da - db).days)
    if delta <= tolerance:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.RANGE,
            normalized_a=str(da),
            normalized_b=str(db),
            similarity=100.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.EXACT,
            explanation_code="MATCH-DATE-WITHIN-TOLERANCE",
        )
    return FieldMatchResult(
        field=field,
        comparison_type=ComparisonType.RANGE,
        normalized_a=str(da),
        normalized_b=str(db),
        similarity=0.0,
        weight=weight,
        critical=critical,
        status=FieldStatus.MISMATCH,
        explanation_code="MATCH-DATE-OUTSIDE-TOLERANCE",
    )


def _fuzzy_result(
    field: str,
    na: str | None,
    nb: str | None,
    weight: float,
    critical: bool,
    algorithm: str,
    exact_code: str,
) -> FieldMatchResult:
    if na is None or nb is None:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.FUZZY,
            normalized_a=na,
            normalized_b=nb,
            similarity=0.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.MISSING,
            explanation_code="MATCH-FIELD-MISSING",
        )
    if na == nb:
        return FieldMatchResult(
            field=field,
            comparison_type=ComparisonType.FUZZY,
            normalized_a=na,
            normalized_b=nb,
            similarity=100.0,
            weight=weight,
            critical=critical,
            status=FieldStatus.EXACT,
            explanation_code=exact_code,
        )
    sim = _sim(na, nb, algorithm)
    code = (
        "MATCH-NAME-HIGH-SIMILARITY"
        if sim >= 85
        else "MATCH-NAME-MEDIUM-SIMILARITY"
        if sim >= 60
        else "MATCH-NAME-LOW-SIMILARITY"
    )
    return FieldMatchResult(
        field=field,
        comparison_type=ComparisonType.FUZZY,
        normalized_a=na,
        normalized_b=nb,
        similarity=sim,
        weight=weight,
        critical=critical,
        status=FieldStatus.EXACT if sim >= 85 else FieldStatus.MISMATCH,
        explanation_code=code,
    )


# Field comparison configuration.
#   (extractor, compare_kind, exact_code)
_FIELD_SPECS: dict[str, tuple[str, str]] = {
    "transaction_id": ("transaction_id", "exact"),
    "end_to_end_id": ("end_to_end_id", "exact"),
    "debtor_account": ("debtor_account", "exact"),
    "creditor_account": ("creditor_account", "exact"),
    "debtor_agent": ("debtor_agent", "exact"),
    "creditor_agent": ("creditor_agent", "exact"),
    "currency": ("currency", "exact"),
    "country": ("country", "exact"),
    "amount": ("amount", "amount"),
    "booking_date": ("booking_date", "date"),
    "value_date": ("value_date", "date"),
    "remittance_reference": ("remittance_reference", "fuzzy"),
    "external_reference": ("external_reference", "fuzzy"),
    "debtor_name": ("debtor_name", "fuzzy"),
    "creditor_name": ("creditor_name", "fuzzy"),
}


def evaluate_pair(
    record_a: MatchRecord,
    record_b: MatchRecord,
    policy: MatchingPolicy,
    *,
    engine_version: str = "0.1.0",
) -> MatchDecision:
    """Evaluate a single record pair against a policy."""
    na = normalize_record(record_a)
    nb = normalize_record(record_b)

    field_results: list[FieldMatchResult] = []
    for field, (key, kind) in _FIELD_SPECS.items():
        weight = policy.field_weights.get(field, 0.0)
        critical = field in policy.critical_fields
        va = na.values.get(key)
        vb = nb.values.get(key)
        if kind == "exact":
            field_results.append(_exact_result(field, va, vb, weight, critical, _exact_code(field)))
        elif kind == "amount":
            field_results.append(_amount_result(field, va, vb, weight, critical, policy))
        elif kind == "date":
            field_results.append(_date_result(field, va, vb, weight, critical, policy))
        elif kind == "fuzzy":
            algorithm = policy.fuzzy_algorithms.get(field, "token_sort_ratio")
            field_results.append(
                _fuzzy_result(field, va, vb, weight, critical, algorithm, _exact_code(field))
            )

    critical_conflicts = _critical_conflicts(field_results, policy.critical_fields)
    score = _score(field_results, policy)
    classification = _classify(score, critical_conflicts, policy)

    codes: list[str] = []
    for fr in field_results:
        if fr.explanation_code and fr.explanation_code not in codes:
            codes.append(fr.explanation_code)

    return MatchDecision(
        record_a_id=record_a.record_id,
        record_b_id=record_b.record_id,
        classification=classification,
        match_score=score,
        critical_conflicts=critical_conflicts,
        field_results=field_results,
        explanation_codes=codes,
        policy_version=str(policy.version),
        engine_version=engine_version,
    )


def _exact_code(field: str) -> str:
    mapping = {
        "transaction_id": "MATCH-TXID-EXACT",
        "end_to_end_id": "MATCH-E2E-EXACT",
        "debtor_account": "MATCH-IBAN-EXACT",
        "creditor_account": "MATCH-IBAN-EXACT",
        "debtor_agent": "MATCH-BIC-EXACT",
        "creditor_agent": "MATCH-BIC-EXACT",
        "currency": "MATCH-CURRENCY-EXACT",
        "country": "MATCH-COUNTRY-EXACT",
        "remittance_reference": "MATCH-REF-EXACT",
        "external_reference": "MATCH-REF-EXACT",
        "debtor_name": "MATCH-NAME-HIGH-SIMILARITY",
        "creditor_name": "MATCH-NAME-HIGH-SIMILARITY",
    }
    return mapping.get(field, "MATCH-FIELD-EXACT")


def _critical_conflicts(
    results: list[FieldMatchResult], critical_fields: list[str]
) -> list[CriticalConflict]:
    conflicts: list[CriticalConflict] = []
    for fr in results:
        if fr.field in critical_fields and fr.status == FieldStatus.MISMATCH:
            conflicts.append(
                CriticalConflict(
                    code=_conflict_code(fr.field),
                    field=fr.field,
                    detail=f"critical field '{fr.field}' mismatch",
                )
            )
        # Party-name mismatch below threshold is a review signal (false-positive trap guard).
        if fr.field in ("debtor_name", "creditor_name") and fr.status == FieldStatus.MISMATCH:
            if fr.similarity < NAME_MISMATCH_THRESHOLD and fr.normalized_a and fr.normalized_b:
                conflicts.append(
                    CriticalConflict(
                        code="MATCH-CRITICAL-NAME-CONFLICT",
                        field=fr.field,
                        detail=f"party name '{fr.field}' differs materially",
                    )
                )
    return conflicts


def _score(results: list[FieldMatchResult], policy: MatchingPolicy) -> float:
    total_weight = 0.0
    weighted = 0.0
    for fr in results:
        if fr.weight <= 0 or fr.status == FieldStatus.MISSING:
            continue
        total_weight += fr.weight
        # similarity is 0..100, so this yields a 0..100 score directly.
        weighted += fr.weight * fr.similarity
    if total_weight <= 0:
        return 0.0
    return round(weighted / total_weight, 2)


def _classify(
    score: float, conflicts: list[CriticalConflict], policy: MatchingPolicy
) -> MatchClassification:
    matched_t = policy.thresholds.get("matched", 85.0)
    possible_t = policy.thresholds.get("possible_match", 60.0)
    review_t = policy.thresholds.get("review", 40.0)
    if conflicts:
        # Critical conflict overrides a high fuzzy score -> human review required.
        if score >= review_t:
            return MatchClassification.REVIEW_REQUIRED
        return MatchClassification.UNMATCHED
    if score >= matched_t:
        return MatchClassification.MATCHED
    if score >= possible_t:
        return MatchClassification.POSSIBLE_MATCH
    if score >= review_t:
        return MatchClassification.REVIEW_REQUIRED
    return MatchClassification.UNMATCHED
