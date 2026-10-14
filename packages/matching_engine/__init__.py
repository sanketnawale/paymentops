"""Fuzzy/entity matching engine.

Deterministic reconciliation and matching intelligence. Produces *evidence*, a normalized
``match_score`` (0..100, NOT a probability), and a classification. Never a decision on its
own and never uses an LLM as the matcher.

The authoritative path is:
    deterministic matching -> normalization -> fuzzy similarity -> weighted scoring
    -> threshold-based classification -> human review where ambiguous
"""

from __future__ import annotations

from matching_engine.candidates import narrowing_criteria
from matching_engine.matcher import evaluate_pair
from matching_engine.models import (
    CandidateMatch,
    ComparisonType,
    CriticalConflict,
    FieldMatchResult,
    FieldStatus,
    MatchClassification,
    MatchDecision,
    MatchingPolicy,
    MatchingPolicyStatus,
    MatchRecord,
    MatchStatus,
    NormalizedRecord,
    RecordType,
)
from matching_engine.normalization import normalize_record
from matching_engine.policy import DEFAULT_FIELD_WEIGHTS, default_policy

__all__ = [
    "CandidateMatch",
    "ComparisonType",
    "CriticalConflict",
    "DEFAULT_FIELD_WEIGHTS",
    "FieldMatchResult",
    "FieldStatus",
    "MatchClassification",
    "MatchDecision",
    "MatchRecord",
    "MatchStatus",
    "MatchingPolicy",
    "MatchingPolicyStatus",
    "NormalizedRecord",
    "RecordType",
    "default_policy",
    "evaluate_pair",
    "normalize_record",
    "narrowing_criteria",
]
