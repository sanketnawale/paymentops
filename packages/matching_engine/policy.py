"""Default matching policy and helpers.

A ``MatchingPolicy`` is versioned configuration. This module provides a deterministic default
policy for development baseline. Weights are relative, NOT probabilities, and are normalized
to a 0..100 ``match_score``.

``MATCH_SCORE = 100 * sum(weight_i * similarity_i) / sum(weight_i)``

Similarity for exact fields is 100 (or 0 on mismatch); fuzzy fields use RapidFuzz 0..100.
"""

from __future__ import annotations

from matching_engine.models import MatchingPolicy, MatchingPolicyStatus

# field -> weight. Weight 0 means the field contributes nothing (still reported).
DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "transaction_id": 30.0,
    "end_to_end_id": 25.0,
    "debtor_account": 20.0,
    "creditor_account": 20.0,
    "amount": 15.0,
    "currency": 10.0,
    "remittance_reference": 15.0,
    "external_reference": 10.0,
    "debtor_name": 10.0,
    "creditor_name": 10.0,
    "booking_date": 5.0,
    "value_date": 5.0,
    "debtor_agent": 5.0,
    "creditor_agent": 5.0,
    "country": 5.0,
}

# classification thresholds (score >= x). DEVELOPMENT BASELINE (see docs/calibration).
DEFAULT_THRESHOLDS: dict[str, float] = {
    "matched": 85.0,
    "possible_match": 60.0,
    "review": 40.0,
}

# date tolerance in days per field.
DEFAULT_DATE_TOLERANCES: dict[str, int] = {
    "booking_date": 3,
    "value_date": 3,
}

# amount tolerance: absolute (minor units or currency units) and relative (fraction).
# Empty by default -> exact Decimal equality is required unless explicitly enabled.
DEFAULT_AMOUNT_TOLERANCES: dict[str, float] = {}

# fields whose mismatch overrides a high fuzzy score.
DEFAULT_CRITICAL_FIELDS: list[str] = [
    "currency",
    "amount",
    "transaction_id",
    "debtor_account",
    "creditor_account",
]

# field -> fuzzy algorithm (controlled, never random).
DEFAULT_FUZZY_ALGORITHMS: dict[str, str] = {
    "debtor_name": "token_set_ratio",
    "creditor_name": "token_set_ratio",
    "remittance_reference": "token_sort_ratio",
    "external_reference": "token_sort_ratio",
}


def default_policy(
    organization_id: str, name: str = "Development Baseline", version: int = 1
) -> MatchingPolicy:
    """Return a development-baseline matching policy."""
    return MatchingPolicy(
        organization_id=organization_id,
        name=name,
        version=version,
        status=MatchingPolicyStatus.PUBLISHED,
        field_weights=dict(DEFAULT_FIELD_WEIGHTS),
        thresholds=dict(DEFAULT_THRESHOLDS),
        date_tolerances=dict(DEFAULT_DATE_TOLERANCES),
        amount_tolerances=dict(DEFAULT_AMOUNT_TOLERANCES),
        critical_fields=list(DEFAULT_CRITICAL_FIELDS),
        fuzzy_algorithms=dict(DEFAULT_FUZZY_ALGORITHMS),
    )
