"""Phase 3A: bounded Batch Exception Desk persistence (tenant-scoped).

A small batch wrapper around the WORKING investigation pipeline (not the legacy Celery batch
module). Each batch has at most five items; each item is a single-transaction pacs.008.001.08
payload with its own optional evidence JSON. Progress is persisted so a restart can resume
without duplicating external runs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from paymentops_api.db.models import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class BatchRun(Base):
    """A bounded batch of synthetic single-transaction cases."""

    __tablename__ = "batch_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_batch_run_org_idem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # PENDING | RUNNING | COMPLETED | PARTIAL | FAILED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BatchItem(Base):
    """A single synthetic case within a batch (XML + optional evidence)."""

    __tablename__ = "batch_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batch_runs.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    item_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Display metadata only; never used as a storage path.
    display_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Uploaded synthetic payload (base64, immutable evidence) + validated evidence record.
    payload_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_evidence: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    # PENDING | STARTING | RUNNING | COMPLETED | FAILED | REJECTED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    investigation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    evolus_execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Restart/duplicate-start guards for the durable runner.
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
