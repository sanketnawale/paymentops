"""Minimal foundational tables for Week 1.

These tables are deliberately minimal and represent platform infrastructure only.
The full PaymentOps domain schema is designed in Week 2 and will be added through new
Alembic migrations. Do not add speculative tables here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from paymentops_api.db.models import Base
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    """A tenant. Every customer/tenant query must eventually be scoped to an org."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AppMetadata(Base):
    """Application-level metadata (e.g. schema/version markers used by migrations)."""

    __tablename__ = "app_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
