"""Week 5 persistence models: ISO messages, payment lifecycles, events, correlations.

Analytical state only. No raw XML payloads are stored; hashes + structured metadata only.
All rows are tenant-scoped by ``organization_id``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from paymentops_api.db.models import Base
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class IsoMessage(Base):
    __tablename__ = "iso_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message_family: Mapped[str] = mapped_column(String(16), nullable=False)
    message_definition: Mapped[str] = mapped_column(String(64), nullable=False)
    message_version: Mapped[str] = mapped_column(String(32), nullable=False)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    source_adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_validation: Mapped[bool] = mapped_column(nullable=False, default=False)
    message_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ANALYZED")
    raw_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    normalized_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PaymentLifecycleRow(Base):
    __tablename__ = "payment_lifecycles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    lifecycle_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    primary_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_to_end_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instruction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uetr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    debtor_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creditor_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_minor: Mapped[int | None] = mapped_column(nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PaymentLifecycleEventRow(Base):
    __tablename__ = "payment_lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    lifecycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_lifecycles.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message_family: Mapped[str | None] = mapped_column(String(16), nullable=True)
    message_definition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_status_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reasons: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False, default=list)
    correlation_evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class MessageCorrelation(Base):
    __tablename__ = "message_correlations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    lifecycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_lifecycles.id"), nullable=False, index=True
    )
    source_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    candidate_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    conflicts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
