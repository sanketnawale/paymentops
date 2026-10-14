"""Week 4 persistence models: matching records, policies, runs, and candidates.

Evidence is stored (field results, critical conflicts) as JSONB for audit/reproduction. Raw
payloads are never stored. All rows are tenant-scoped by ``organization_id``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from paymentops_api.db.models import Base
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class MatchRecordRow(Base):
    __tablename__ = "match_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    instruction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_to_end_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    booking_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    debtor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    creditor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    debtor_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    creditor_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    debtor_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creditor_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)

    remittance_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class MatchingPolicyRow(Base):
    __tablename__ = "matching_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchingPolicyVersion(Base):
    __tablename__ = "matching_policy_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matching_policies.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    field_weights: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    date_tolerances: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    amount_tolerances: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    critical_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fuzzy_algorithms: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class MatchRun(Base):
    __tablename__ = "match_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_dataset: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    candidate_dataset: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    total: Mapped[int] = mapped_column(nullable=False, default=0)
    matched: Mapped[int] = mapped_column(nullable=False, default=0)
    possible_match: Mapped[int] = mapped_column(nullable=False, default=0)
    review_required: Mapped[int] = mapped_column(nullable=False, default=0)
    unmatched: Mapped[int] = mapped_column(nullable=False, default=0)
    duplicate_candidate: Mapped[int] = mapped_column(nullable=False, default=0)
    failed: Mapped[int] = mapped_column(nullable=False, default=0)

    report: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_runs.id"), nullable=False, index=True
    )
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_record_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    match_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    critical_conflicts: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    field_results: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    explanation_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
