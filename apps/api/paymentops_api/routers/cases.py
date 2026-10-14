"""Operator case workflow API (tenant-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.auth import (
    AuthenticatedClient,
    get_actor_identity,
    get_api_client,
    get_db,
)
from paymentops_api.db.models import PaymentCase
from paymentops_api.services import case_service

router = APIRouter(tags=["cases"])


class CaseActionRequest(BaseModel):
    action: str = Field(..., description="approve | reject | close")
    operator: str | None = None
    note: str | None = None


@router.get("/api/v1/cases")
async def list_cases(
    limit: int = Query(50, le=200),
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    result = await session.execute(
        select(PaymentCase)
        .where(PaymentCase.organization_id == client.organization_id)
        .order_by(PaymentCase.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "case_id": c.case_id,
            "status": c.status,
            "message_type": c.message_type,
            "message_version": c.message_version,
            "validation_status": c.validation_status,
            "address_readiness": c.address_readiness,
            "repair_status": c.repair_status,
            "address_provider_coverage": c.address_provider_coverage,
            "mapping_version": c.mapping_version,
            "integration_profile_version": c.integration_profile_version,
            "ruleset_version": c.ruleset_version,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in result.scalars().all()
    ]


@router.get("/api/v1/cases/{case_id}")
async def get_case(
    case_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        case = await case_service.get_case(session, client.organization_id, case_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="case not found") from None
    findings = await _rule_findings(session, case_id)
    audit = await _audit_events(session, case_id)
    return {
        "case_id": case.case_id,
        "organization_id": str(case.organization_id),
        "message_type": case.message_type,
        "message_version": case.message_version,
        "validation_status": case.validation_status,
        "address_readiness": case.address_readiness,
        "repair_status": case.repair_status,
        "status": case.status,
        "address_provider": case.address_provider,
        "address_provider_coverage": case.address_provider_coverage,
        "ruleset_version": case.ruleset_version,
        "mapping_version": case.mapping_version,
        "integration_profile_version": case.integration_profile_version,
        "input_hash": case.input_hash,
        "output_hash": case.output_hash,
        "findings": findings,
        "audit": audit,
        "disclaimer": (
            "Approval in PaymentOps approves the data-repair candidate only. It does not "
            "authorize, release, settle, or execute the payment."
        ),
    }


async def _rule_findings(session: AsyncSession, case_id: str) -> list[dict[str, object]]:
    from paymentops_api.db.models import RuleFinding

    result = await session.execute(select(RuleFinding).where(RuleFinding.case_id == case_id))
    return [
        {"rule_id": r.rule_id, "severity": r.severity, "target": r.target, "message": r.message}
        for r in result.scalars().all()
    ]


async def _audit_events(session: AsyncSession, case_id: str) -> list[dict[str, object]]:
    from paymentops_api.db.models import AuditEvent

    result = await session.execute(
        select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.created_at)
    )
    return [
        {
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "actor": e.user_identity,
            "event": e.event_type,
        }
        for e in result.scalars().all()
    ]


@router.post("/api/v1/cases/{case_id}/actions")
async def case_action(
    case_id: str,
    body: CaseActionRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    actor: str | None = Depends(get_actor_identity),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        case = await case_service.transition_case(
            session,
            client.organization_id,
            case_id,
            body.action,
            operator=actor or body.operator,
            note=body.note,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="case not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"case_id": case.case_id, "status": case.status, "action": body.action}
