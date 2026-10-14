"""ISO 20022 analysis + payment lifecycle API (tenant-scoped).

Non-transactional: analyzing a message never executes or settles a payment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from analysis.models import IsoAnalysisResult
from analysis.pipeline import AnalysisPipeline
from iso_engine.registry import IsoMessageRegistry, UnsupportedMessageError
from iso_engine.xml_errors import XmlError
from paymentops_api.auth import AuthenticatedClient, get_actor_identity, get_api_client, get_db
from paymentops_api.db.models import (
    IsoMessage,
    MessageCorrelation,
    PaymentLifecycleEventRow,
    PaymentLifecycleRow,
)
from paymentops_api.observability import (
    iso_messages_total,
    iso_unsupported_versions_total,
    iso_validation_failures_total,
)
from paymentops_api.services import iso_analysis_service, lifecycle_service

router = APIRouter(tags=["iso"])


class IsoAnalyzeRequest(BaseModel):
    xml: str = Field(..., description="Raw ISO 20022 XML payload")


class DecideCorrelationRequest(BaseModel):
    action: str
    operator: str | None = None
    note: str | None = None


@router.post("/api/v1/iso/analyze")
async def analyze_iso(
    body: IsoAnalyzeRequest,
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    pipeline: AnalysisPipeline = request.app.state.analysis_pipeline
    registry: IsoMessageRegistry = request.app.state.iso_registry
    try:
        result = await iso_analysis_service.analyze_iso_message(
            session,
            client.organization_id,
            body.xml.encode("utf-8"),
            registry=registry,
            pipeline=pipeline,
        )
    except UnsupportedMessageError as exc:
        iso_unsupported_versions_total.labels(family=_family_of(exc.identifier)).inc()
        raise HTTPException(
            status_code=422, detail=f"unsupported ISO version: {exc.identifier}"
        ) from None
    except XmlError as exc:
        iso_validation_failures_total.labels(family="unknown", version="unknown").inc()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    iso_messages_total.labels(
        family=result.message_family or "unknown",
        version=result.message_version or "unknown",
        status=result.original_validation_status,
    ).inc()
    return _iso_result_dict(result)


@router.get("/api/v1/iso/messages")
async def list_iso_messages(
    request: Request,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
    family: str | None = None,
    definition: str | None = None,
    version: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    rows = await lifecycle_service.list_iso_messages(
        session,
        client.organization_id,
        family=family,
        definition=definition,
        version=version,
        status=status,
        limit=limit,
    )
    return [_iso_message_dict(r) for r in rows]


@router.get("/api/v1/iso/messages/{message_id}")
async def get_iso_message(
    message_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        row = await lifecycle_service.get_iso_message(session, client.organization_id, message_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="iso message not found") from None
    return _iso_message_dict(row)


@router.get("/api/v1/lifecycles")
async def list_lifecycles(
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await lifecycle_service.list_lifecycles(session, client.organization_id)
    return [_lifecycle_dict(r) for r in rows]


@router.get("/api/v1/lifecycles/{lifecycle_id}")
async def get_lifecycle(
    lifecycle_id: str,
    client: AuthenticatedClient = Depends(get_api_client),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        row, events = await lifecycle_service.get_lifecycle(
            session, client.organization_id, lifecycle_id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="lifecycle not found") from None
    correlations = await lifecycle_service.list_correlations(
        session, client.organization_id, lifecycle_id
    )
    data = _lifecycle_dict(row)
    data["events"] = [_event_dict(e) for e in events]
    data["correlations"] = [_correlation_dict(c) for c in correlations]
    return data


@router.post("/api/v1/lifecycles/{lifecycle_id}/correlations/{correlation_id}/decide")
async def decide_correlation(
    lifecycle_id: str,
    correlation_id: str,
    body: DecideCorrelationRequest,
    client: AuthenticatedClient = Depends(get_api_client),
    actor: str | None = Depends(get_actor_identity),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        corr = await lifecycle_service.decide_correlation(
            session,
            client.organization_id,
            correlation_id,
            body.action,
            operator=actor or body.operator,
            note=body.note,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="correlation not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        "correlation_id": str(corr.id),
        "status": corr.correlation_status,
        "action": body.action,
    }


# ---------------------------------------------------------------- serializers


def _family_of(identifier: str) -> str:
    return identifier.split(".")[0] if identifier else "unknown"


def _iso_result_dict(result: IsoAnalysisResult) -> dict[str, object]:
    data = result.model_dump(mode="json")
    return data


def _iso_message_dict(r: IsoMessage) -> dict[str, object]:
    return {
        "id": str(r.id),
        "message_id": r.message_id,
        "message_family": r.message_family,
        "message_definition": r.message_definition,
        "message_version": r.message_version,
        "namespace": r.namespace,
        "schema_validation": r.schema_validation,
        "status": r.status,
        "raw_status": r.raw_status,
        "normalized_status": r.normalized_status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _lifecycle_dict(r: PaymentLifecycleRow) -> dict[str, object]:
    return {
        "lifecycle_id": r.lifecycle_id,
        "organization_id": str(r.organization_id),
        "primary_reference": r.primary_reference,
        "end_to_end_id": r.end_to_end_id,
        "instruction_id": r.instruction_id,
        "transaction_id": r.transaction_id,
        "original_message_id": r.original_message_id,
        "amount_minor": r.amount_minor,
        "currency": r.currency,
        "current_status": r.current_status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _event_dict(e: PaymentLifecycleEventRow) -> dict[str, object]:
    return {
        "id": str(e.id),
        "event_type": e.event_type,
        "message_family": e.message_family,
        "message_definition": e.message_definition,
        "message_version": e.message_version,
        "message_id": e.message_id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "status": e.status,
        "raw_status_code": e.raw_status_code,
        "reasons": e.reasons,
        "correlation_evidence": e.correlation_evidence,
    }


def _correlation_dict(c: MessageCorrelation) -> dict[str, object]:
    return {
        "id": str(c.id),
        "source_message_id": c.source_message_id,
        "candidate_message_id": c.candidate_message_id,
        "correlation_status": c.correlation_status,
        "evidence": c.evidence,
        "conflicts": c.conflicts,
        "operator": c.operator,
        "note": c.note,
    }
