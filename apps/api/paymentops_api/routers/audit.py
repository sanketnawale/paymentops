"""Audit trail API (tenant-scoped, read-only, non-sensitive metadata only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import AuthenticatedClient, get_api_client, get_db
from paymentops_api.db.models import AuditEvent

router = APIRouter(tags=["audit"])


@router.get("/api/v1/audit")
async def list_audit_events(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
    limit: int = 200,
    case_id: str | None = None,
) -> list[dict[str, object]]:
    """List audit events for the authenticated organization (append-oriented)."""
    limit = max(1, min(limit, 1000))
    stmt = select(AuditEvent).where(AuditEvent.organization_id == client.organization_id)
    if case_id:
        stmt = stmt.where(AuditEvent.case_id == case_id)
    stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [_audit_dict(e) for e in result.scalars().all()]


def _audit_dict(e: AuditEvent) -> dict[str, object]:
    metadata = e.action_metadata or {}
    result = metadata.get("classification") or metadata.get("action") or e.event_type
    return {
        "id": str(e.id),
        "timestamp": e.created_at.isoformat() if e.created_at else None,
        "actor": e.user_identity,
        "event": e.event_type,
        "resource": e.profile_id or e.case_id,
        "case_id": e.case_id,
        "profile_version": e.profile_version,
        "result": str(result) if result is not None else None,
    }
