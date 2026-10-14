"""Phase 1 investigation persistence (tenant-scoped; metadata + structured results only).

No raw payment payload is stored: the investigation references a bundled synthetic demo case
by key and stores its SHA-256 identity. Deterministic findings and the agent result are stored
as structured JSONB. See ``docs/PHASE1.md``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from paymentops_api.db.models import Base
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Investigation(Base):
    """A single analyst-triggered investigation of a synthetic demo case."""

    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Server-side reference to a bundled synthetic demo case (never a client-supplied path).
    demo_case_key: Mapped[str] = mapped_column(String(64), nullable=False)
    message_version: Mapped[str] = mapped_column(String(64), nullable=False)
    # SHA-256 of the synthetic payload (immutable input identity).
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # PENDING | RUNNING | COMPLETED | FAILED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    evolus_execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    evolus_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Deterministic engine output (schema issues, rule findings, address readiness).
    deterministic_findings: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    # Parsed agent result: explanation, cited rules, missing evidence, next step (+ raw).
    agent_result: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    agent_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
