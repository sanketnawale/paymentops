"""Lifecycle read/decision service (analytical state, tenant-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime

from paymentops_api.db.models import (
    IsoMessage,
    MessageCorrelation,
    PaymentLifecycleEventRow,
    PaymentLifecycleRow,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_iso_messages(
    session: AsyncSession,
    org: str,
    *,
    family: str | None = None,
    definition: str | None = None,
    version: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[IsoMessage]:
    stmt = select(IsoMessage).where(IsoMessage.organization_id == org)
    if family:
        stmt = stmt.where(IsoMessage.message_family == family)
    if definition:
        stmt = stmt.where(IsoMessage.message_definition == definition)
    if version:
        stmt = stmt.where(IsoMessage.message_version == version)
    if status:
        stmt = stmt.where(IsoMessage.status == status)
    stmt = stmt.order_by(IsoMessage.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_iso_message(session: AsyncSession, org: str, message_id: str) -> IsoMessage:
    result = await session.execute(
        select(IsoMessage).where(IsoMessage.organization_id == org, IsoMessage.id == message_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise LookupError("iso message not found")
    return row


async def list_lifecycles(session: AsyncSession, org: str) -> list[PaymentLifecycleRow]:
    result = await session.execute(
        select(PaymentLifecycleRow)
        .where(PaymentLifecycleRow.organization_id == org)
        .order_by(PaymentLifecycleRow.created_at.desc())
    )
    return list(result.scalars().all())


async def get_lifecycle(
    session: AsyncSession, org: str, lifecycle_id: str
) -> tuple[PaymentLifecycleRow, list[PaymentLifecycleEventRow]]:
    row_result = await session.execute(
        select(PaymentLifecycleRow).where(
            PaymentLifecycleRow.organization_id == org,
            PaymentLifecycleRow.lifecycle_id == lifecycle_id,
        )
    )
    row = row_result.scalar_one_or_none()
    if row is None:
        raise LookupError("lifecycle not found")
    ev_result = await session.execute(
        select(PaymentLifecycleEventRow)
        .where(PaymentLifecycleEventRow.lifecycle_id == row.id)
        .order_by(PaymentLifecycleEventRow.created_at)
    )
    return row, list(ev_result.scalars().all())


async def list_correlations(
    session: AsyncSession, org: str, lifecycle_id: str
) -> list[MessageCorrelation]:
    result = await session.execute(
        select(MessageCorrelation)
        .join(PaymentLifecycleRow, MessageCorrelation.lifecycle_id == PaymentLifecycleRow.id)
        .where(
            PaymentLifecycleRow.organization_id == org,
            PaymentLifecycleRow.lifecycle_id == lifecycle_id,
        )
    )
    return list(result.scalars().all())


async def decide_correlation(
    session: AsyncSession,
    org: str,
    correlation_id: str,
    action: str,
    *,
    operator: str | None,
    note: str | None,
) -> MessageCorrelation:
    result = await session.execute(
        select(MessageCorrelation).where(
            MessageCorrelation.id == correlation_id, MessageCorrelation.organization_id == org
        )
    )
    corr = result.scalar_one_or_none()
    if corr is None:
        raise LookupError("correlation not found")
    if action not in ("confirm", "reject", "leave"):
        raise ValueError(f"unsupported action '{action}'")
    status_map = {"confirm": "CORRELATED", "reject": "UNRESOLVED", "leave": "UNRESOLVED"}
    corr.correlation_status = status_map[action]
    corr.operator = operator
    corr.note = note
    corr.decided_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(corr)
    return corr
