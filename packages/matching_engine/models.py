"""Matching engine domain models (deterministic; never a decision on its own).

The matching engine produces *evidence* and a deterministic ``match_score`` + classification.
It is never the authoritative settlement/execution decision and never uses an LLM.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecordType(StrEnum):
    PAYMENT = "PAYMENT"
    EXPECTED_PAYMENT = "EXPECTED_PAYMENT"
    INVOICE = "INVOICE"
    LEDGER_ENTRY = "LEDGER_ENTRY"
    ACCOUNT_EVENT = "ACCOUNT_EVENT"


class FieldStatus(StrEnum):
    """Result of comparing a single field between two records."""

    EXACT = "EXACT"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"  # one/both sides absent -> cannot compare
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComparisonType(StrEnum):
    EXACT = "EXACT"
    FUZZY = "FUZZY"
    RANGE = "RANGE"  # date/amount tolerance
    NONE = "NONE"


class MatchClassification(StrEnum):
    MATCHED = "MATCHED"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    UNMATCHED = "UNMATCHED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DUPLICATE_CANDIDATE = "DUPLICATE_CANDIDATE"


class MatchStatus(StrEnum):
    """Lifecycle of a match run / reconciliation job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class MatchingPolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class MatchRecord(BaseModel):
    """Canonical match record.

    Carries the original evidence (never mutated). ``source_hash`` ties it to immutable
    source evidence; no raw payload is stored here.
    """

    model_config = ConfigDict(extra="ignore")

    record_id: str
    record_type: RecordType
    organization_id: str
    profile_id: str | None = None
    source_system: str | None = None
    message_type: str | None = None

    instruction_id: str | None = None
    end_to_end_id: str | None = None
    transaction_id: str | None = None

    amount: Decimal | None = None
    currency: str | None = None

    booking_date: date | None = None
    value_date: date | None = None

    debtor_name: str | None = None
    creditor_name: str | None = None
    debtor_account: str | None = None
    creditor_account: str | None = None
    debtor_agent: str | None = None
    creditor_agent: str | None = None

    remittance_reference: str | None = None
    external_reference: str | None = None
    country: str | None = None

    source_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FieldMatchResult(BaseModel):
    """Structured result of comparing one field between two records.

    Sensitive values (IBANs, names, accounts) are intentionally not logged; this model is
    for API responses under authorization and for persistence as evidence.
    """

    field: str
    comparison_type: ComparisonType
    original_a: Any = None
    original_b: Any = None
    normalized_a: Any = None
    normalized_b: Any = None
    similarity: float = 0.0  # 0..100 (RapidFuzz scale) or 100 for exact/range
    weight: float = 0.0
    critical: bool = False
    status: FieldStatus = FieldStatus.MISSING
    explanation_code: str | None = None


class CriticalConflict(BaseModel):
    """A critical-field conflict that may override a high fuzzy score."""

    code: str
    field: str
    detail: str


class MatchDecision(BaseModel):
    """Deterministic match evaluation result between exactly two records."""

    record_a_id: str
    record_b_id: str
    classification: MatchClassification
    match_score: float = 0.0  # 0..100, NOT a probability
    critical_conflicts: list[CriticalConflict] = Field(default_factory=list)
    field_results: list[FieldMatchResult] = Field(default_factory=list)
    explanation_codes: list[str] = Field(default_factory=list)
    policy_version: str | None = None
    engine_version: str | None = None
    integration_profile_version: str | None = None


class CandidateMatch(BaseModel):
    """A ranked candidate from candidate retrieval."""

    candidate_id: str
    match_score: float
    classification: MatchClassification
    top_evidence: list[FieldMatchResult] = Field(default_factory=list)
    critical_conflicts: list[CriticalConflict] = Field(default_factory=list)


class MatchingPolicy(BaseModel):
    """Versioned, configurable deterministic matching policy.

    Weights are NOT probabilities. They are relative contributions to a 0..100 score that
    is normalized by the policy's total weight. Published policies are immutable.
    """

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    organization_id: str
    name: str
    version: int = 1
    status: MatchingPolicyStatus = MatchingPolicyStatus.DRAFT

    field_weights: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    date_tolerances: dict[str, int] = Field(default_factory=dict)
    amount_tolerances: dict[str, float] = Field(default_factory=dict)
    critical_fields: list[str] = Field(default_factory=list)
    fuzzy_algorithms: dict[str, str] = Field(default_factory=dict)

    created_at: datetime | None = None
    published_at: datetime | None = None


class NormalizedRecord(BaseModel):
    """Deterministically normalized record. Original evidence is never modified."""

    record_id: str
    record_type: RecordType
    organization_id: str
    values: dict[str, Any] = Field(default_factory=dict)
    normalized_meta: dict[str, Any] = Field(default_factory=dict)
