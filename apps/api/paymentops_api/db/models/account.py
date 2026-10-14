"""Week 6 persistence models: account reports, entries, balances, reconciliations.

Account reporting is ANALYTICAL evidence only. No raw XML payloads are stored. Every row is
tenant-scoped by ``organization_id``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from paymentops_api.db.models import Base
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class AccountReportRow(Base):
    __tablename__ = "account_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    iso_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iso_messages.id"), nullable=True, index=True
    )
    message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message_definition: Mapped[str] = mapped_column(String(64), nullable=False)
    message_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    account_iban: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    account_other_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    account_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    servicer_bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    statement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notification_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AccountEntryRow(Base):
    __tablename__ = "account_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_reports.id"), nullable=False, index=True
    )
    entry_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    account_servicer_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instruction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_to_end_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uetr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_minor: Mapped[int | None] = mapped_column(nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    credit_debit: Mapped[str | None] = mapped_column(String(4), nullable=True)
    booking_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bank_tx_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    bank_tx_family: Mapped[str | None] = mapped_column(String(8), nullable=True)
    bank_tx_sub_family: Mapped[str | None] = mapped_column(String(8), nullable=True)
    remittance_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reconciliation_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    match_score: Mapped[float | None] = mapped_column(nullable=True)
    lifecycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_lifecycles.id"), nullable=True, index=True
    )
    evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    conflicts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AccountBalanceRow(Base):
    __tablename__ = "account_balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_reports.id"), nullable=False, index=True
    )
    balance_type: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_minor: Mapped[int] = mapped_column(nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    credit_debit: Mapped[str] = mapped_column(String(4), nullable=False, default="CRDT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AccountReconciliationRow(Base):
    __tablename__ = "account_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    account_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_entries.id"), nullable=False, index=True
    )
    lifecycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_lifecycles.id"), nullable=True, index=True
    )
    classification: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    match_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    conflicts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
