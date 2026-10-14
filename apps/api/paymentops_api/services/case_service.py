"""Operator case workflow service.

APPROVED in PaymentOps approves the data-repair candidate ONLY. It does NOT authorize or
release a payment. Every state transition is audited and append-oriented.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from paymentops_api.db.models import AuditEvent, CaseAction, PaymentCase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CaseStatus(StrEnum):
    NEW = "NEW"
    ANALYZED = "ANALYZED"
    REPAIR_PROPOSED = "REPAIR_PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


_ALLOWED = {
    "approve": CaseStatus.APPROVED,
    "reject": CaseStatus.REJECTED,
    "close": CaseStatus.CLOSED,
}


async def get_case(session: AsyncSession, organization_id: str, case_id: str) -> PaymentCase:
    result = await session.execute(
        select(PaymentCase).where(
            PaymentCase.case_id == case_id, PaymentCase.organization_id == organization_id
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise LookupError("case not found")
    return case


async def transition_case(
    session: AsyncSession,
    organization_id: str,
    case_id: str,
    action: str,
    *,
    operator: str | None,
    note: str | None,
) -> PaymentCase:
    """Apply an operator action; record a CaseAction + AuditEvent (transactional)."""
    case = await get_case(session, organization_id, case_id)
    if action not in _ALLOWED:
        raise ValueError(f"unsupported action '{action}'")

    new_status = _ALLOWED[action]
    if case.status in ("APPROVED", "REJECTED", "CLOSED") and case.status != new_status:
        raise ValueError("case already closed")

    case.status = new_status.value
    session.add(
        CaseAction(
            organization_id=organization_id,
            case_id=case_id,
            action=action,
            operator=operator,
            note=note,
            created_at=datetime.now(UTC),
        )
    )
    session.add(
        AuditEvent(
            organization_id=organization_id,
            case_id=case_id,
            event_type=f"case.{action}",
            user_identity=operator,
            action_metadata={"action": action, "note": note},
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    await session.refresh(case)
    return case
